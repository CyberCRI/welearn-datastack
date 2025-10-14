import logging
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from welearn_database.data.models import ProcessState, WeLearnDocument

logger = logging.getLogger(__name__)


def insert_urls(session: Session, urls: List[WeLearnDocument]) -> None:
    """
    Insert URLs in the database and create a process state for each URL
    :param session: SQLAlchemy session
    :param urls: List of URLs to insert in the database
    :return: None
    """
    for url in urls:
        logger.info("URL : '%s'", url)
        p_state = ProcessState(
            document=url,
            title="url_retrieved",
        )
        try:
            session.add(url)
            session.add(p_state)
            session.commit()
        except IntegrityError as e:
            logger.warning("URL '%s' error : %s", url.url, str(e))
            session.rollback()
        except Exception as e:
            session.rollback()
            logger.error("Error while inserting URL : '%s'", url)
            logger.error(e)
            raise e
