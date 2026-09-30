import os
import sqlite3

import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_FILE = os.getenv("DB_FILE", "work.db")
OPEN_ALEX_ID = "3ec75732-375f-4b50-9ce0-129c3e3221fb"
CATEGORY = "9cb400f0-ce10-4607-9a2e-abffa1a33eec"


def get_journals_from_work_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        docdatas = cursor.execute(
            """
            SELECT DISTINCT journal_id, journal_name
            FROM document_id
            WHERE journal_id IS NOT NULL AND journal_name IS NOT NULL
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


def write_new_corpus_to_pg():
    load_dotenv(verbose=True)
    journals = get_journals_from_work_db()

    journals = [j for j in journals if j[1] != ""]

    if not journals:
        print("Aucun corpus à insérer.")
        return 0

    sql = f"""
        INSERT INTO corpus_related.corpus (id, source_name, parent_corpus_id, is_fix, category_id)
        VALUES (%s, %s, '{OPEN_ALEX_ID}', true, '{CATEGORY}')
        ON CONFLICT DO NOTHING
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, journals)

    print(f"{len(journals)} corpus synchronisés dans corpus_related.corpus.")
    return len(journals)


def main():
    write_new_corpus_to_pg()


if __name__ == "__main__":
    main()
