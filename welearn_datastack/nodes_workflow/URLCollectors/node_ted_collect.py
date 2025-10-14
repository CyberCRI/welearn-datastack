import logging
import os

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.ted_collector import TedURLCollector
from welearn_datastack.nodes_workflow.URLCollectors.nodes_helpers.collect import (
    insert_urls,
)
from welearn_datastack.utils_.database_utils import create_db_session

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
    logger.info("TED collector starting...")
    session = create_db_session()
    corpus: Corpus | None = (
        session.query(Corpus).filter_by(source_name="ted").one_or_none()
    )

    if corpus is None:
        raise ValueError(f"Corpus ted not found")

    ted_collector = TedURLCollector(corpus=corpus)

    urls = ted_collector.collect()

    logger.info("URLs retrieved : '%s'", len(urls))
    insert_urls(
        session=session,
        urls=urls,
    )

    logger.info("Ted collector ended")
