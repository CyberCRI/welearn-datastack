import logging
import os

from sqlalchemy.orm import Session
from welearn_database.data.enumeration import Step

from welearn_datastack.data.batch_generator import BatchGenerator
from welearn_datastack.data.enumerations import WeighedScope
from welearn_datastack.modules import retrieve_data_from_database
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
    logger.info("DocumentVectorizer generate batch ids starting...")
    output_batch_file = os.getenv("OUTPUT_FILE_NAME", "batch_ids.csv")

    # Environment variables
    logger.info("Load environment variables")
    parallelism_threshold: int = int(os.getenv("PARALLELISM_THRESHOLD", 100))
    parallelism_max: int = int(os.getenv("PARALLELISM_URL_MAX", 15))
    batch_urls_directory: str = os.getenv("BATCH_URLS_DIRECTORY", "batch_urls")
    corpus_name: str = os.getenv("PICK_CORPUS_NAME", "*")
    qty_max_str: str | None = os.getenv("PICK_QTY_MAX", None)

    qty_max: int | None = None
    if qty_max_str is not None:
        qty_max = int(qty_max_str)

    logger.info("Environment variables loaded")

    batch_generator = BatchGenerator(
        parallelism_threshold=parallelism_threshold,
        parallelism_max=parallelism_max,
        batch_urls_directory=batch_urls_directory,
        output_batch_file_name=output_batch_file,
    )

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    # Get URLs from DB
    logger.info("Retrieve ids from DB")
    ids_to_batch = (
        retrieve_data_from_database.retrieve_documents_ids_according_process_title(
            db_session,
            qty_max=qty_max,
            process_titles=[Step.DOCUMENT_VECTORIZED],
            weighed_scope=WeighedScope.DOCUMENT,
            corpus_name=corpus_name,
        )
    )
    logger.info("'%s' Docsids were retrieved", len(ids_to_batch))

    # Create batch
    logger.info("Create batch")
    batch_generator.create_ids_batch(ids_to_batch)
    logger.info("Batch created")

    logger.info("Write quantity")
    qty = batch_generator.write_quantity_to_file()

    logger.info("Quantity written")

    if qty:
        logger.info("Write batches to file")
        batch_generator.write_batches_to_file()
        logger.info("Batches written")
    logger.info(f"{__name__} generate batch ids finished")


if __name__ == "__main__":
    load_dotenv_local()
    main()
