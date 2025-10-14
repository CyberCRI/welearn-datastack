import logging
import os

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.press_books_collector import PressBooksURLCollector
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
    logger.info("Press Books collector starting...")
    load_dotenv_local()
    session = create_db_session()
    api_key = os.getenv("PRESSBOOKS_ALGOLIA_API_KEY")
    app_id = os.getenv("PRESSBOOKS_ALGOLIA_APPLICATION_ID")
    qty_books = 20

    corpus: Corpus | None = (
        session.query(Corpus).filter_by(source_name="press-books").one_or_none()
    )

    pb_collector = PressBooksURLCollector(
        corpus=corpus, api_key=api_key, application_id=app_id, qty_books=qty_books
    )

    urls = pb_collector.collect()

    logger.info("URLs retrieved : '%s'", len(urls))
    insert_urls(
        session=session,
        urls=urls,
    )

    logger.info("Press Books collector ended")
