import logging
import os
from pathlib import Path

from sqlalchemy import BindParameter, TextClause, bindparam, text
from sqlalchemy.dialects import postgresql

from welearn_datastack.modules.validation import validate_sql_query_param

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


def _resolve_query_util(
    queries_folder: Path,
    query_name: str,
    params: tuple[BindParameter, ...],
    mandatory_params: list,
) -> TextClause:
    """
    Private function used for generating SQL query from file with a validation of the parameters needed for the execution of the query

    :param queries_folder: Path to the folder where the queries are stored
    :param query_name: Name of the query
    :param params: Parameters needed for the execution of the query, form key: value with parameter as key and its value as value
    :param mandatory_params: Parameters needed for the execution of the query
    """
    if query_name is None:
        raise ValueError("Query name cannot be None")

    logger.info("Query name: %s", query_name)
    if not query_name.endswith(".sql"):
        query_name += ".sql"
    logger.info(f"Query path: {queries_folder}/{query_name}")

    # Retrieve query from file
    query_as_text = open(queries_folder / query_name).read()

    # Validate
    for param in mandatory_params:
        if not validate_sql_query_param(query_as_text, param):
            raise ValueError(f"SQL query must contain the parameter: {param}")
    logger.info("SQL query validated")

    # Execute query from file
    stmt = text(query_as_text).bindparams(*params)
    return stmt


def resolve_batched_query(
    batch_size: int, queries_folder: Path, query_name: str, revision_id: str
) -> TextClause:
    """
    Create SQL query from specified file with a batching logic

    :param batch_size: Quantity of items in the batch
    :param queries_folder: Path to the folder where the queries are stored
    :param query_name: Name of the query
    :param revision_id: Revision id needed for the execution of the query
    """
    params = (
        bindparam("batch_size", value=batch_size),
        bindparam("revision_id", value=revision_id),
    )
    mandatory_params = ["batch_size", "revision_id"]

    return _resolve_query_util(queries_folder, query_name, params, mandatory_params)


def resolve_query_on_given_ids(
    given_ids: list, queries_folder: Path, query_name: str, revision_id: str
) -> TextClause:
    """
    Create SQL query from specified file on multiple given IDs

    :param given_ids: List of IDs needed for the execution of the query
    :param queries_folder: Path to the folder where the queries are stored
    :param query_name: Name of the query
    :param revision_id: Revision id needed for the execution of the query
    """
    params = (
        bindparam("revision_id", value=revision_id),
        bindparam("ids", value=given_ids, expanding=True),
    )
    mandatory_params = ["ids", "revision_id"]
    return _resolve_query_util(queries_folder, query_name, params, mandatory_params)


def resolve_query(
    queries_folder: Path, query_name: str, revision_id: str
) -> TextClause:
    """
    Create SQL query from specified file, no batched logic existing here, if needed use "resolve_batched_query"

    :param queries_folder: Path to the folder where the queries are stored
    :param query_name: Name of the query
    :param revision_id: Revision id needed for the execution of the query
    """
    params = (bindparam("revision_id", value=revision_id),)
    mandatory_params = ["revision_id"]
    return _resolve_query_util(queries_folder, query_name, params, mandatory_params)
