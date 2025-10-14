import logging
import os
from datetime import datetime, timedelta

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.hal_collector import HALURLCollector
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
    logger.info("HAL collector starting...")

    session = create_db_session()
    date_a_week_ago: datetime = datetime.now() - timedelta(days=7)

    corpus: Corpus | None = (
        session.query(Corpus).filter_by(source_name="hal").one_or_none()
    )

    if corpus is None:
        raise ValueError(f"Corpus hal not found")

    hal_collector = HALURLCollector(
        corpus=corpus, date_last_insert=int(date_a_week_ago.timestamp())
    )

    urls = hal_collector.collect()

    logger.info("URLs retrieved : '%s'", len(urls))

    insert_urls(
        session=session,
        urls=urls,
    )
