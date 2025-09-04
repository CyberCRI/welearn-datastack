import logging
import os

from welearn_datastack.collectors.unccelearn_collector import UNCCeLearnURLCollector
from welearn_datastack.data.db_models import Corpus
from welearn_datastack.nodes_workflow.URLCollectors.nodes_helpers.collect import (
    insert_urls,
)
from welearn_datastack.utils_.database_utils import create_db_session

log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError(f"Log level is not recognized : '{log_level}'")

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("UNCCeLearn collector starting...")
    session = create_db_session()
    corpus: Corpus | None = (
        session.query(Corpus).filter_by(source_name="unccelearn").one_or_none()
    )

    if corpus is None:
        raise ValueError(f"Corpus unccelearn not found")

    unccelearn_collector = UNCCeLearnURLCollector(corpus=corpus)

    urls = unccelearn_collector.collect()

    logger.info("URLs retrieved : '%s'", len(urls))
    insert_urls(
        session=session,
        urls=urls,
    )

    logger.info("UNCCeLearn collector ended")
