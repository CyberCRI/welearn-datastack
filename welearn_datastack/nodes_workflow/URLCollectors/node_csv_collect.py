import logging
import os
from pathlib import Path
from typing import List

from sqlalchemy import and_, select

from welearn_datastack.collectors.csv_collector import CSVURLCollector
from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.nodes_workflow.URLCollectors.nodes_helpers.collect import (
    insert_urls,
)
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


if __name__ == "__main__":
    logger.info("CSV collector starting...")
    load_dotenv_local()
    session = create_db_session()
    csv_path = Path(os.getenv("CSV_PATH"))  # type: ignore
    corpus_name = os.getenv("CORPUS_NAME")
    url_column = int(os.getenv("URL_COLUMN"))  # type: ignore
    delimiter = os.getenv("CSV_DELIMITER", ",")

    if not csv_path.exists():
        raise FileNotFoundError(f"File {csv_path} does not exists")

    if not corpus_name:
        raise ValueError("CORPUS_NAME is not defined")

    if not corpus_name:
        raise ValueError("CORPUS_NAME is not defined")

    corpus: Corpus | None = (
        session.query(Corpus).filter_by(source_name=corpus_name).one_or_none()
    )

    if corpus is None:
        raise ValueError(f"Corpus {corpus_name} not found")

    csv_collector = CSVURLCollector(
        csv_fp=csv_path,
        corpus=corpus,
        url_column=url_column,
        delimiter=delimiter,
    )
    collected = csv_collector.collect()

    stmt = select(WeLearnDocument).where(
        and_(
            WeLearnDocument.url.in_([obj.url for obj in collected]),  # type: ignore
        )
    )
    url_ds_already_in_db: List[WeLearnDocument] = session.execute(stmt).scalars().all()

    url_already_in_db: List[str] = [obj.url for obj in url_ds_already_in_db]  # type: ignore

    logger.info("URLs collected: %s", len(collected))

    insert_urls(
        session=session,
        urls=collected,
    )

    logger.info("URLs inserted in DB")

    logger.info("CSV collector ended")
