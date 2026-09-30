import os
import sqlite3

import psycopg2
from dotenv import load_dotenv

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
    load_dotenv(verbose=True)
    ids_n_journals = get_document_with_new_journals_ids()
    ids_n_journals = [j for j in ids_n_journals if j[0] != ""]

    if not ids_n_journals:
        print("Aucun doc à update.")
        return 0

    sql = """
     UPDATE document_related.welearn_document
    SET corpus_id = %s
    WHERE id = %s; 
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, ids_n_journals)

    print(
        f"{len(ids_n_journals)} corpus synchronisés dans document_related.welearn_document."
    )
    return len(ids_n_journals)


def main():
    update_documents()


if __name__ == "__main__":
    main()
