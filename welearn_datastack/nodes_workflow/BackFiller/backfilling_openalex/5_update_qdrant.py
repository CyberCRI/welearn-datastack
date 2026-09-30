import os
import sqlite3

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

load_dotenv()
DB_FILE = os.getenv("DB_FILE")


def get_document_with_new_journals_ids():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        docdatas = cursor.execute(
            """
            SELECT DISTINCT id, journal_name
            FROM document_id di
            WHERE length(di.journal_name) > 1
            """
        )
    return docdatas.fetchall()


def get_qdrant_connection():
    qdrant_client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        port=os.getenv("QDRANT_HTTP_PORT"),
        timeout=int(os.getenv("QDRANT_TIMEOUT")),
        https=True,
    )

    return qdrant_client


def update_documents():
    load_dotenv(verbose=True)
    ids_n_journals = get_document_with_new_journals_ids()
    if not ids_n_journals:
        print("Aucun doc à update.")
        return 0

    client = get_qdrant_connection()

    collection_name = "collection_welearn_mul_granite-embedding-107m-multilingual"

    for jid in ids_n_journals:
        client.set_payload(
            collection_name=f"{collection_name}",
            payload={
                "document_sub_corpus": jid[1],
            },
            points=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=jid[0]),
                    ),
                ],
            ),
        )

    print(f"{len(ids_n_journals)} docs synchronisés dans qdrant")
    return len(ids_n_journals)


def main():
    update_documents()


if __name__ == "__main__":
    main()
