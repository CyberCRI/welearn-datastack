import logging
import os
import re

from sqlalchemy import text

from welearn_datastack.utils_.database_utils import create_db_session

# Set up logging configuration
log_level: int = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
log_format: str = os.getenv(
    "LOG_FORMAT", "[%(asctime)s][%(name)s][%(levelname)s] - %(message)s"
)

if not isinstance(log_level, int):
    raise ValueError(f"Log level is not recognized: '{log_level}'")

logging.basicConfig(
    level=logging.getLevelName(log_level),
    format=log_format,
)
logger = logging.getLogger(__name__)


def update_materialized_view(view_name: str) -> None:
    logger.info(f"Starting refresh of materialized view: {view_name}")
    # Security check: only allow alphanumeric, underscore, and dot
    if not re.match(r"^[\w.]+$", view_name):
        logger.error(f"Unsafe view name detected: {view_name}")
        raise ValueError(f"Unsafe view name: {view_name}")
    db_session = create_db_session()
    try:
        # Interpolate view name directly
        statement = text(f"REFRESH MATERIALIZED VIEW {view_name}")
        db_session.execute(statement)
        db_session.commit()
        logger.info(f"Successfully refreshed materialized view: {view_name}")
    except Exception as e:
        logger.error(f"Failed to refresh materialized view '{view_name}': {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()
        logger.debug("Database session closed.")


def main():
    view_name = os.getenv("VIEW_NAME", "document_related.qty_document_in_qdrant")
    if not view_name:
        logger.error("VIEW_NAME environment variable is not set.")
        raise ValueError("VIEW_NAME environment variable is required.")
    update_materialized_view(view_name)


if __name__ == "__main__":
    main()
