import logging
import os
import sqlite3

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
DB_FILE = os.getenv("DB_FILE")


def get_document_with_new_journals_ids():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        docdatas = cursor.execute("""
            SELECT DISTINCT id, journal_name
            FROM document_id di
            WHERE length(di.journal_name) > 1
            """)
    return docdatas.fetchall()


def get_qdrant_connection():
    qdrant_timeout: int = int(os.getenv("QDRANT_TIMEOUT", "60"))
    qdrant_grpc_port: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
    qdrant_http_port: int = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
    qdrant_url: str = os.getenv("QDRANT_URL", "localhost")
    qdrant_prefers_grpc: bool = (
        os.getenv("QDRANT_PREFERS_GRPC", "False").lower() == "true"
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

    qdrant_client = QdrantClient(
        url=qdrant_url,
        port=qdrant_http_port,
        grpc_port=qdrant_grpc_port,
        prefer_grpc=qdrant_prefers_grpc,
        timeout=qdrant_timeout,
    )

    return qdrant_client


def update_documents():
    load_dotenv(verbose=True)

    logger.info("=" * 60)
    logger.info("UPDATING QDRANT PAYLOADS")
    logger.info("=" * 60)

    logger.info("Fetching documents with new journal IDs...")
    ids_n_journals = get_document_with_new_journals_ids()
    if not ids_n_journals:
        logger.info("No documents to update.")
        return 0

    logger.info(f"Found {len(ids_n_journals)} documents to update")

    try:
        client = get_qdrant_connection()
    except Exception as e:
        logger.error(f"❌ Failed to connect to Qdrant: {str(e)}")
        raise

    collection_name = "collection_welearn_mul_granite-embedding-107m-multilingual"

    updated_count = 0
    failed_count = 0

    for idx, jid in enumerate(ids_n_journals, 1):
        try:
            client.set_payload(
                wait=False,
                collection_name=collection_name,
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
            updated_count += 1

            # Log progress every 100 documents
            if idx % 100 == 0:
                logger.info(f"Progress: {idx}/{len(ids_n_journals)} documents updated")

        except Exception as e:
            failed_count += 1
            logger.error(f"Error updating document {jid[0]}: {str(e)}")

    logger.info("=" * 60)
    logger.info(f"SYNCHRONIZATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total: {len(ids_n_journals)} documents")
    logger.info(f"Updated: {updated_count} ✓")
    logger.info(f"Failed: {failed_count} ✗")
    logger.info("=" * 60)

    return updated_count


def main():
    update_documents()


if __name__ == "__main__":
    main()
