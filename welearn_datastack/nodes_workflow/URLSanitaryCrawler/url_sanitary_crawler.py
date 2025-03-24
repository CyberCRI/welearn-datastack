import logging
import os
import uuid
from typing import List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from welearn_datastack.data.db_models import (
    ErrorRetrieval,
    ProcessState,
    WeLearnDocument,
)
from welearn_datastack.data.enumerations import Step, URLStatus
from welearn_datastack.modules.retrieve_data_from_files import retrieve_ids_from_csv
from welearn_datastack.modules.url_checker import check_url
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
    logger.info("URL Sanitary Crawler starting...")
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
        db_session.query(WeLearnDocument)
        .filter(WeLearnDocument.id.in_(docids))
        .order_by(WeLearnDocument.id)
        .all()
    )
    logger.info("'%s' WeLearnDocuments were retrieved", len(welearn_documents))

    wlds_ids_to_update: List[Tuple[UUID, int]] = []
    wlds_ids_to_delete: List[Tuple[UUID, int]] = []

    # Check url
    logger.info("Check URL state")

    wld: WeLearnDocument
    for i, wld in enumerate(welearn_documents):
        check_ret = check_url(wld.url)

        if i % 10 == 0:
            logger.info(f"Checked {i}/{len(welearn_documents)} URLs")

        info_error_ret = ""
        match check_ret[0]:
            case URLStatus.UPDATE:
                info_error_ret = f"{wld.url} gonna be updated soon"
                db_session.add(
                    ProcessState(
                        id=uuid.uuid4(),
                        document_id=wld.id,
                        title=Step.URL_RETRIEVED.value,
                    )
                )
            case URLStatus.DELETE:
                info_error_ret = f"{wld.url} gonna be deleted soon"
                db_session.add(
                    ProcessState(
                        id=uuid.uuid4(),
                        document_id=wld.id,
                        title=Step.DOCUMENT_IS_IRRETRIEVABLE.value,
                    )
                )
        db_session.add(
            ErrorRetrieval(
                id=uuid.uuid4(),
                document_id=wld.id,
                http_error_code=check_ret[1],
                error_info=info_error_ret,
            )
        )

    db_session.commit()
    db_session.close()


if __name__ == "__main__":
    load_dotenv_local()
    main()
