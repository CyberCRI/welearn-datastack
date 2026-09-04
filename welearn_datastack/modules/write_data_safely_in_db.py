import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm.exc import UnmappedInstanceError

from welearn_datastack.exceptions import (
    DBIntegrityErrorObjectNotFound,
    DBIntegrityErrorParamKeyNotFound,
    InvalidIDFormat,
)

logger = logging.getLogger(__name__)


def extract_id_from_exception(integrity_error: IntegrityError, key_path: str) -> UUID:
    params = integrity_error.params
    if key_path not in params:
        raise DBIntegrityErrorParamKeyNotFound(key_path=key_path)

    ret = params[key_path]
    if isinstance(ret, UUID):
        return ret
    else:
        try:
            return UUID(ret)
        except ValueError as e:
            raise InvalidIDFormat(msg=f"Should be a valid UUID : {ret}") from e


def insert_batch_with_retry(
    session: Session,
    objects: list,
    key_path: str,
    max_retries: int,
) -> list:
    """
    Try to insert the data batch, if exception raised remove the object who cause it and retry
    :param session: Database session
    :param objects: list of objects to insert in the db
    :param key_path: Path for the key used by the method to find the id of the error object
    :param max_retries: Maximum number of retries
    """
    remaining = list(objects)
    failed = []
    objects_by_id = {
        obj_id: obj
        for obj in remaining
        if (obj_id := getattr(obj, "id", None)) is not None
    }

    for i in range(max_retries):
        logger.info("Try %s/%s for inserting objects", i, max_retries)
        try:
            with session.begin_nested():
                session.add_all(remaining)
                session.flush()
            return failed  # success

        except IntegrityError as e:
            logger.warning(
                "An error integrity error was raised, retrying without error object"
            )
            # Reset failed transaction state before any further session operation.
            session.rollback()
            conflicting_id = extract_id_from_exception(e, key_path)
            logger.warning(
                "Key of the error object (id=%s), remove it and retry",
                conflicting_id,
            )

            culprit = objects_by_id.get(conflicting_id)
            if culprit is None:
                logger.error(
                    "Error object cannot be find, critical error",
                )
                raise DBIntegrityErrorObjectNotFound

            # Preserve the primary key value on the ORM instance so callers can
            # still read it safely after the session rollback/expunge cycle.
            if hasattr(culprit, "_sa_instance_state"):
                set_committed_value(culprit, "id", conflicting_id)

            if culprit in remaining:
                remaining.remove(culprit)
            else:
                logger.error(
                    "Error object cannot be find in remaining batch, critical error",
                )
                raise DBIntegrityErrorObjectNotFound

            try:
                session.expunge(culprit)
            except UnmappedInstanceError:
                pass
            failed.append(culprit)

            if not remaining:
                return failed

    return failed
