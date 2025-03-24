import logging
import os

from welearn_datastack.collectors.rss_collector import RssURLCollector
from welearn_datastack.data.db_models import Corpus
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
    logger.info("RSS collector starting...")
    load_dotenv_local()
    session = create_db_session()
    rss_url = os.getenv("RSS_URL")
    corpus_name = os.getenv("CORPUS_NAME")

    if not rss_url:
        raise ValueError("RSS_URL is not defined")

    if not corpus_name:
        raise ValueError("CORPUS_NAME is not defined")

    corpus: Corpus | None = (
        session.query(Corpus).filter_by(source_name=corpus_name).one_or_none()
    )

    if corpus is None:
        raise ValueError(f"Corpus {corpus_name} not found")

    rss_collector = RssURLCollector(
        feed_url=rss_url,
        corpus=corpus,
    )

    urls = rss_collector.collect()

    logger.info("URLs retrieved : '%s'", len(urls))
    insert_urls(
        session=session,
        urls=urls,
    )

    logger.info("RSS collector ended")
