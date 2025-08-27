import csv
import logging
import os
from uuid import UUID

from sqlalchemy.orm import Session

from welearn_datastack.data.db_models import WeLearnDocument
from welearn_datastack.utils_.database_utils import create_db_session
from welearn_datastack.utils_.path_utils import setup_local_path

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
    logger.info("DocumentPDFProcessor starting...")
    input_artifact_id_url = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")
    logger.info("Input artifact url csv name: %s", input_artifact_id_url)
    local_artifcat_input, local_artifcat_output = setup_local_path()

    # retrieve url data from files
    logger.info("Retrieve URLs from file")

    # Input IDs
    with (local_artifcat_input / input_artifact_id_url).open(
        "r"
    ) as artifact_file_input:
        spamreader = csv.reader(artifact_file_input, delimiter=",", quotechar='"')
        ids_urls: list[UUID] = [UUID(row[0]) for row in spamreader]
        logger.info("'%s' IDs URLs were retrieved", len(ids_urls))

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    # Retrieve WeLearnDocument from database
    logger.info("Retrieve WeLearnDocument from database")
    welearn_documents: list = (
        db_session.query(WeLearnDocument).filter(WeLearnDocument.id.in_(ids_urls)).all()
    )
    logger.info("'%s' WeLearnDocuments were retrieved", len(welearn_documents))

    if len(ids_urls) != len(welearn_documents):
        logger.warning(
            "'%s' IDs URLs were not found in the database",
            len(ids_urls) - len(welearn_documents),
        )

    if not welearn_documents:
        logger.info("No WeLearnDocuments were retrieved")
        return
