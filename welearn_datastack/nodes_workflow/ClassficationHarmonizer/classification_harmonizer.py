import logging
import os
import uuid
from itertools import groupby
from typing import List, Set
from uuid import UUID

from sqlalchemy.orm import Session

from welearn_datastack.data.db_models import DocumentSlice, ProcessState, Sdg, WeLearnDocument
from welearn_datastack.data.enumerations import MLModelsType, Step
from welearn_datastack.modules.retrieve_data_from_database import retrieve_models
from welearn_datastack.modules.retrieve_data_from_files import retrieve_ids_from_csv
from welearn_datastack.modules.sdgs_classifiers import (
    bi_classify_slices,
    n_classify_slices,
)
from welearn_datastack.utils_.database_utils import create_db_session
from welearn_datastack.utils_.path_utils import setup_local_path
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
    logger.info("Classification Harmonizer starting...")
    input_artifact = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")
    logger.info("Input artifact url json name: %s", input_artifact)

    input_directory, local_artifcat_output = setup_local_path()

    docids = retrieve_ids_from_csv(
        input_artifact=input_artifact, input_directory=input_directory
    )

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    # Retrieve Slices from database
    logger.info("Retrieve Slices from database")
    slices = (
        db_session.query(DocumentSlice)
        .filter(DocumentSlice.document_id.in_(docids))
        .all()
    )
    logger.info("'%s' Slices were retrieved", len(slices))

