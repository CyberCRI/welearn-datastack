import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def insert_batch_safely(
    session: Session,
    objects: list,
) -> list[UUID]:
    failed = []

    # Modified objects outside the batch (e.g. documents in error) would be
    # flushed by begin_nested() below, outside of any try block.
    batch_ids = {id(obj) for obj in objects}
    for pending in list(session.dirty) + list(session.new):
        if id(pending) not in batch_ids:
            session.expunge(pending)

    for obj in objects:
        if obj in session:
            session.expunge(obj)

    for obj in objects:
        try:
            with session.begin_nested():
                session.add(obj)
                session.flush([obj])

        except IntegrityError:
            logger.warning(
                "An error integrity error was raised, object (%s) removed",
                obj.id,
            )
            failed.append(obj.id)
            try:
                session.expunge(obj)
            except InvalidRequestError:
                pass

    return failed
