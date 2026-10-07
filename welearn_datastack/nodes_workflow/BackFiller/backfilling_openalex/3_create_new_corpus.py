import logging
import os
import sqlite3

import psycopg2
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
DB_FILE = os.getenv("DB_FILE", "work.db")
OPEN_ALEX_ID = "3ec75732-375f-4b50-9ce0-129c3e3221fb"
CATEGORY = "9cb400f0-ce10-4607-9a2e-abffa1a33eec"


def get_journals_from_work_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        docdatas = cursor.execute("""
            SELECT DISTINCT journal_id, journal_name
            FROM document_id
            WHERE journal_id IS NOT NULL AND journal_name IS NOT NULL
            """)
    return docdatas.fetchall()


def get_pg_connection():
    connection_params = {
        "host": os.getenv("PG_HOST", os.getenv("PGHOST", "localhost")),
        "port": os.getenv("PG_PORT", os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PG_DB", os.getenv("PGDATABASE")),
        "user": os.getenv("PG_USER", os.getenv("PGUSER")),
        "password": os.getenv("PG_PASSWORD", os.getenv("PGPASSWORD")),
    }

    missing_params = [
        key for key in ("dbname", "user", "password") if not connection_params[key]
    ]
    if missing_params:
        missing = ", ".join(missing_params)
        raise ValueError(
            "Configuration PostgreSQL incomplète. "
            f"Renseigne POSTGRES_DSN ou les variables suivantes: {missing}."
        )

    return psycopg2.connect(**connection_params)


def write_new_corpus_to_pg():
    logger.info("=" * 60)
    logger.info("CREATING NEW CORPUS IN POSTGRESQL")
    logger.info("=" * 60)

    load_dotenv(verbose=True)

    logger.info(f"Reading journals from {DB_FILE}...")
    journals = get_journals_from_work_db()
    logger.info(f"Found {len(journals)} journals")

    journals = [j for j in journals if j[1] != ""]
    logger.info(f"After filtering empty names: {len(journals)} journals")

    if not journals:
        logger.info("❌ No journals to insert.")
        return 0

    logger.info(f"Connecting to PostgreSQL...")
    sql = f"""
        INSERT INTO corpus_related.corpus (id, source_name, parent_corpus_id, is_fix, category_id)
        VALUES (%s, %s, '{OPEN_ALEX_ID}', true, '{CATEGORY}')
        ON CONFLICT DO NOTHING
    """

    inserted_count = 0
    conflict_count = 0

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cursor:
                for idx, journal in enumerate(journals, 1):
                    cursor.execute(sql, journal)
                    # Log progress every 100 journals
                    if idx % 100 == 0:
                        logger.info(
                            f"Progress: {idx}/{len(journals)} journals inserted"
                        )

                conn.commit()
                inserted_count = len(journals)
                logger.info(
                    f"✓ All {len(journals)} corpus rows processed in PostgreSQL"
                )

    except psycopg2.IntegrityError as e:
        logger.warning(f"Some journals already exist (conflict): {str(e)}")
        conflict_count += 1
    except Exception as e:
        logger.error(f"❌ Error inserting corpus: {str(e)}")
        raise

    logger.info("=" * 60)
    logger.info(f"CORPUS CREATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total journals: {len(journals)}")
    logger.info(f"Inserted: {inserted_count} ✓")
    logger.info(f"Conflicts: {conflict_count} ⚠")
    logger.info("=" * 60)

    return inserted_count


def main():
    write_new_corpus_to_pg()


if __name__ == "__main__":
    main()
