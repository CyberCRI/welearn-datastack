import logging
import os
import sqlite3

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from qdrant_client.conversions.common_types import Record

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    qdrant_timeout: int = int(os.getenv("QDRANT_TIMEOUT", "60"))
    qdrant_grpc_port: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
    qdrant_http_port: int = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
    qdrant_url: str = os.getenv("QDRANT_URL", "localhost")
    qdrant_prefers_grpc: bool = (
        os.getenv("QDRANT_PREFERS_GRPC", "False").lower() == "true"
    )

    client = QdrantClient(
        url=qdrant_url,
        port=qdrant_http_port,
        grpc_port=qdrant_grpc_port,
        prefer_grpc=qdrant_prefers_grpc,
        timeout=qdrant_timeout,
    )

    logger.info("=" * 60)
    logger.info("QDRANT CONNECTION PARAMETERS")
    logger.info("=" * 60)
    logger.info(f"URL: {qdrant_url}")
    logger.info(f"HTTP Port: {qdrant_http_port}")
    logger.info(f"gRPC Port: {qdrant_grpc_port}")
    logger.info(f"Prefer gRPC: {qdrant_prefers_grpc}")
    logger.info(f"Timeout: {qdrant_timeout}s")
    logger.info("=" * 60)

    logger.info(f"Fetching {QTY} documents from Qdrant...")
    create_work_db()
    hits = get_documents_id_from_qdrant(client, quantity=int(QTY))
    rows = extract_document_id_from_points(hits)
    logger.info(f"Extracted {len(rows)} document IDs, saving to database...")

    with sqlite3.connect(DB_FILE) as conn:
        for row in rows:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO document_id(id, document_url) VALUES (?, ?)", row
            )

        conn.commit()

    logger.info(f"✓ Successfully saved {len(rows)} documents to {DB_FILE}")


if __name__ == "__main__":
    main()
