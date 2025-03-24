import logging
import os
from functools import cache
from typing import Dict

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_dotenv_local() -> None:
    # If your not in local .env doesnt exist at all, this method just avoid the cost of an useless search
    if bool(os.getenv("IS_LOCAL", True)):
        load_dotenv()


@cache
def get_sub_environ_according_prefix(prefix: str) -> Dict[str, str]:
    """
    Get the models names from the environ according to the prefix
    :return: A dictionary from the environ according to the prefix
    """
    prefix += "_"

    os_dict = os.environ
    related_keys = {
        key: os_dict[key] for key in os_dict.keys() if key.startswith(prefix)
    }

    return related_keys
