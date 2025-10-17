import logging
import os
from datetime import datetime, timedelta

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.open_alex_collector import OpenAlexURLCollector
from welearn_datastack.exceptions import NoCorpusFoundInDb
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
    logger.info("OpenAlex collector starting...")
    load_dotenv_local()
    session = create_db_session()
    bound_time_limit_for_insert: datetime = datetime.now() - timedelta(days=7)

    corpus: Corpus | None = (
        session.query(Corpus).filter_by(source_name="openalex").one_or_none()
    )

    if not corpus:
        raise NoCorpusFoundInDb("OpenAlex not found in corpus available in database")

    oa_collector = OpenAlexURLCollector(
        corpus=corpus, date_last_insert=int(bound_time_limit_for_insert.timestamp())
    )

    urls = oa_collector.collect()

    logger.info("URLs retrieved : '%s'", len(urls))
    insert_urls(
        session=session,
        urls=urls,
    )

    logger.info("OpenAlex collector ended")
