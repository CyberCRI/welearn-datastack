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


def get_document_with_new_journals_ids():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        docdatas = cursor.execute(
            """
            SELECT DISTINCT journal_id, id
            FROM document_id
            """
        )
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


def update_documents():
    logger.info("=" * 60)
    logger.info("UPDATING WELEARN DOCUMENTS")
    logger.info("=" * 60)

    load_dotenv(verbose=True)

    logger.info(f"Reading document-journal mappings from {DB_FILE}...")
    ids_n_journals = get_document_with_new_journals_ids()
    logger.info(f"Found {len(ids_n_journals)} document-journal pairs")

    ids_n_journals = [j for j in ids_n_journals if j[0] != ""]
    logger.info(f"After filtering empty journal IDs: {len(ids_n_journals)} pairs")

    if not ids_n_journals:
        logger.info("❌ No documents to update.")
        return 0

    sql = """
     UPDATE document_related.welearn_document
    SET corpus_id = %s
    WHERE id = %s; 
    """

    logger.info(f"Connecting to PostgreSQL...")
    updated_count = 0
    error_count = 0

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cursor:
                for idx, (journal_id, doc_id) in enumerate(ids_n_journals, 1):
                    try:
                        cursor.execute(sql, (journal_id, doc_id))
                        updated_count += 1

                        # Log progress every 100 documents
                        if idx % 100 == 0:
                            logger.info(
                                f"Progress: {idx}/{len(ids_n_journals)} documents updated"
                            )

                    except psycopg2.Error as e:
                        error_count += 1
                        logger.error(f"Error updating document {doc_id}: {str(e)}")

                conn.commit()
                logger.info(f"✓ Commit successful: {updated_count} documents updated")

    except Exception as e:
        logger.error(f"❌ Error updating documents: {str(e)}")
        raise

    logger.info("=" * 60)
    logger.info(f"DOCUMENT UPDATE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total processed: {len(ids_n_journals)}")
    logger.info(f"Successfully updated: {updated_count} ✓")
    logger.info(f"Failed: {error_count} ✗")
    logger.info("=" * 60)

    return updated_count


def main():
    update_documents()


if __name__ == "__main__":
    main()
