import logging
import os
from datetime import datetime, timedelta

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.world_bank_okr import (
    WorldBankOpenKnowledgeRepositoryCollector,
)
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
    logger.info("World Bank Open Knowledge Repository collector starting...")

    session = create_db_session()
    date_a_week_ago: datetime = datetime.now() - timedelta(days=7)

    corpus: Corpus | None = (
        session.query(Corpus)
        .filter_by(source_name="world-bank-open-knowledge-repository")
        .one_or_none()
    )

    if corpus is None:
        raise ValueError("Corpus world-bank-open-knowledge-repository not found")

    collector = WorldBankOpenKnowledgeRepositoryCollector(
        corpus,
        date_last_insert=int(date_a_week_ago.timestamp()),
    )

    urls = collector.collect()

    logger.info("URLs retrieved : '%s'", len(urls))

    insert_urls(
        session=session,
        urls=urls,
    )
