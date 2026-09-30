import os
import sqlite3

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from qdrant_client.conversions.common_types import Record

load_dotenv()
COLLECTION_NAME = "collection_welearn_mul_granite-embedding-107m-multilingual"
DB_FILE = os.getenv("DB_FILE", "work.db")
QTY = os.getenv("PICK_QTY_MAX")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_HTTP_PORT = os.getenv("QDRANT_HTTP_PORT")


def create_work_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS document_id (id TEXT PRIMARY KEY, document_url TEXT UNIQUE)"""
        )


def extract_document_id_from_points(points: list[Record]):
    ret = set()
    for p in points:
        ret.add((p.payload["document_id"], p.payload["document_url"]))
    return ret


def get_documents_id_from_qdrant(client, quantity: int):
    qret = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_corpus", match=models.MatchValue(value="openalex")
                ),
            ]
        ),
        limit=quantity,
        with_payload=["document_id", "document_url"],
        with_vectors=False,
    )
    return qret[0]


def main():
    client = QdrantClient(url=f"{QDRANT_URL}:{QDRANT_HTTP_PORT}")
    create_work_db()
    hits = get_documents_id_from_qdrant(client, quantity=int(QTY))
    rows = extract_document_id_from_points(hits)

    with sqlite3.connect(DB_FILE) as conn:
        for row in rows:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO document_id(id, document_url) VALUES (?, ?)", row
            )

        conn.commit()


if __name__ == "__main__":
    main()
