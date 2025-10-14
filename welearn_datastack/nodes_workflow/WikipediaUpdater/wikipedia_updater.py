import logging
import os
from typing import List

from sqlalchemy.orm import Session
from welearn_database.data.enumeration import Step
from welearn_database.data.models import ProcessState, WeLearnDocument

from welearn_datastack.modules.retrieve_data_from_files import retrieve_ids_from_csv
from welearn_datastack.modules.wikipedia_updater import compare_with_current_version
from welearn_datastack.utils_.database_utils import create_db_session
from welearn_datastack.utils_.path_utils import setup_local_path
from welearn_datastack.utils_.virtual_environement_utils import load_dotenv_local

log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError(f"Log level is not recognized: '{log_level}'")

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("WikipediaUpdater starting...")
    input_artifact = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")
    logger.info("Input artifact url json name: %s", input_artifact)

    input_directory, _ = setup_local_path()

    docids = retrieve_ids_from_csv(
        input_artifact=input_artifact, input_directory=input_directory
    )

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    # Retrieve WeLearnDocument from database
    logger.info("Retrieve WeLearnDocument from database")
    welearn_documents: List = (
        db_session.query(WeLearnDocument).filter(WeLearnDocument.id.in_(docids)).all()
    )
    logger.info("'%s' WeLearnDocuments were retrieved", len(welearn_documents))

    # Comparing documents with current online version
    logger.info("Comparing documents with current online version")
    for wld in welearn_documents:
        try:
            if compare_with_current_version(wld):
                logger.info(
                    "Document '%s' has a size difference exceeding 5%%", wld.title
                )
                db_session.add(
                    ProcessState(
                        document_id=wld.id,
                        title=Step.URL_RETRIEVED.value,
                    )
                )
        except (ValueError, KeyError) as e:
            logger.error("Error while comparing document '%s': %s", wld.title, e)
            continue

    db_session.commit()
    db_session.close()


if __name__ == "__main__":
    load_dotenv_local()
    main()
