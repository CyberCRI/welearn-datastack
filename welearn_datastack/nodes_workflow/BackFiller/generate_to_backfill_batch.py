import logging
import os
from pathlib import Path

from sqlalchemy.orm import Session

from welearn_datastack.data.batch_generator import BatchGenerator
from welearn_datastack.modules.query_utils import resolve_batched_query
from welearn_datastack.utils_.database_utils import create_db_session
from welearn_datastack.utils_.virtual_environement_utils import load_dotenv_local

log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError("Log level is not recognized : '%s'", log_level)

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("BackFiller generate batch starting...")
    output_batch_file = os.getenv("OUTPUT_FILE_NAME", "batch_ids.csv")

    # Environment variables
    logger.info("Load environment variables")
    parallelism_threshold: int = int(os.getenv("PARALLELISM_THRESHOLD", 100))
    parallelism_max: int = int(os.getenv("PARALLELISM_URL_MAX", 15))
    batch_urls_directory: str = os.getenv("BATCH_URLS_DIRECTORY", "batch_urls")
    batch_size_str: str | None = os.getenv("BATCH_SIZE", None)
    revision_id: str | None = os.getenv("REVISION_ID", None)
    query_name = os.getenv("QUERY_NAME", None)

    batch_size: int | None = None
    if batch_size_str is not None:
        batch_size = int(batch_size_str)

    logger.info("Environment variables loaded")

    queries_folder_env = os.getenv("QUERY_FOLDER_PATH", None)
    if queries_folder_env:
        queries_folder = Path(queries_folder_env).resolve()
    else:
        queries_folder = Path(__file__).parent / "batch_generator_queries"
        queries_folder = queries_folder.resolve()
    logger.info(f"Query path used : {queries_folder}")

    batch_generator = BatchGenerator(
        parallelism_threshold=parallelism_threshold,
        parallelism_max=parallelism_max,
        batch_urls_directory=batch_urls_directory,
        output_batch_file_name=output_batch_file,
    )
    logger.info("Parallelism threshold: %s", parallelism_threshold)
    logger.info("Parallelism max: %s", parallelism_max)

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    stmt = resolve_batched_query(batch_size, queries_folder, query_name, revision_id)

    logger.info("Execute DB query")
    res = db_session.execute(stmt)
    logger.info("DB Query executed")
    rows = res.fetchall()
    ids_to_batch = [row[0] for row in rows]

    # Create batch
    logger.info("Create batch")
    batch_generator.create_ids_batch(ids_to_batch)
    logger.info("Batch created")
    logger.info("Write batch to file")
    batch_generator.write_batches_to_file()
    logger.info("Batch written to file")
    logger.info("Write quantity")
    batch_generator.write_quantity_to_file()
    logger.info("Quantity written")
    logger.info(f"{__name__} generate batch ids finished")


if __name__ == "__main__":
    load_dotenv_local()
    main()
