import logging
import os

from welearn_datastack.collectors.wikipedia_collector import WikipediaURLCollector
from welearn_datastack.constants import WIKIPEDIA_CONTAINERS
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
    raise ValueError("Log level is not recognized : '%s'", log_level)

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)

# Retrieve Batch variables
NB_BATCHES = os.getenv("NB_BATCHES")
BATCH_ID = os.getenv("BATCH_ID")

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Wikipedia collector starting...")
    session = create_db_session()

    corpus: Corpus | None = (
        session.query(Corpus).filter_by(source_name="wikipedia").one_or_none()
    )

    if corpus is None:
        raise ValueError(f"Corpus wikipedia not found")

    wikipedia_collector = WikipediaURLCollector(
        nb_batches=int(NB_BATCHES) if NB_BATCHES else None,
        corpus=corpus,
        wikipedia_containers=WIKIPEDIA_CONTAINERS,
    )

    batch_id: int | None = int(BATCH_ID) if BATCH_ID else None

    urls = wikipedia_collector.collect(batch_id=batch_id)

    logger.info("URLs retrieved : '%s'", len(urls))

    insert_urls(
        session=session,
        urls=urls,
    )

    logger.info("Wikipedia collector ended")
