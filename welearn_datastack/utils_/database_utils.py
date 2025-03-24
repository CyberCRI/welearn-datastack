import logging
import math
import os
from typing import Any, List

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

from welearn_datastack.utils_.virtual_environement_utils import load_dotenv_local

logger = logging.getLogger(__name__)


def create_db_session():
    engine = create_sqlalchemy_engine()
    session_made = sessionmaker(engine)
    return session_made()


def create_sqlalchemy_engine():
    load_dotenv_local()
    pg_driver = os.getenv("PG_DRIVER", "postgresql+psycopg2")
    pg_user = os.getenv("PG_USER")
    pg_password = os.getenv("PG_PASSWORD")
    pg_host = os.getenv("PG_HOST")
    pg_port = os.getenv("PG_PORT")
    pg_db = os.getenv("PG_DB")
    url_object = URL.create(
        drivername=pg_driver,
        username=pg_user,
        password=pg_password,
        host=pg_host,
        port=pg_port,
        database=pg_db,
    )
    engine = create_engine(url_object)
    return engine


def create_specific_batches_quantity(
    to_batch_list: List[Any],
    qty_batch: int,
) -> List[List[Any]]:
    logger.info("Create batch")
    ret = []
    quantity_items_per_batch = math.ceil(len(to_batch_list) / qty_batch)

    logger.info("Batch quantity : %s", qty_batch)
    for i in range(qty_batch):
        to_write_batch = to_batch_list[
            i * quantity_items_per_batch : (i + 1) * quantity_items_per_batch
        ]
        if to_write_batch:
            ret.append(to_write_batch)
    logger.info("Batch created")
    return ret
