import csv
import logging
import os
import uuid
from pathlib import Path
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from welearn_datastack.modules.query_utils import (
    resolve_query,
    resolve_query_on_given_ids,
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
    logger.info("Back filler starting...")

    revision_id: str | None = os.getenv("REVISION_ID", None)
    query_name = os.getenv("QUERY_NAME", None)
    logger.info("Environment variables loaded")

    input_artifact_id_url = os.getenv("ARTIFACT_ID_URL_CSV_NAME", "batch_ids.csv")
    logger.info("Input artifact url csv name: %s", input_artifact_id_url)

    local_artifcat_input, _ = setup_local_path()

    # Input IDs
    with (local_artifcat_input / input_artifact_id_url).open(
        "r"
    ) as artifact_file_input:
        spamreader = csv.reader(artifact_file_input, delimiter=",", quotechar='"')
        ids_urls: List[UUID] = [uuid.UUID(row[0]) for row in spamreader]
        logger.info("'%s' IDs URLs were retrieved", len(ids_urls))

    # Database management
    logger.info("Create DB session")
    db_session: Session = create_db_session()
    logger.info("DB session created")

    queries_folder = Path("back_filling_queries/")
    stmt = resolve_query_on_given_ids(ids_urls, queries_folder, query_name, revision_id)
    res = db_session.execute(stmt)
    db_session.commit()  # N'oublie pas de commit pour une mise à jour !
    nb_modifies = res.rowcount
    logger.info("DB query executed")
    logger.info(f"{nb_modifies} rows were modified")


if __name__ == "__main__":
    load_dotenv_local()
    main()
