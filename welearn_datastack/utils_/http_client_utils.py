import logging

import requests  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from urllib3 import Retry

from welearn_datastack.constants import HEADERS

logger = logging.getLogger(__name__)


def get_new_https_session(retry_total: int = 10):
    # Define the retry strategy
    retry_strategy = Retry(
        total=retry_total,  # Maximum number of retries
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
        backoff_factor=2,  # Factor to apply to the backoff
    )

    # Create an HTTP adapter with the retry strategy and mount it to session
    adapter = HTTPAdapter(max_retries=retry_strategy)

    # Create a new session object
    session = requests.Session()
    session.mount("https://", adapter)
    session.headers = HEADERS  # type: ignore
    return session


def get_http_code_from_exception(e: Exception) -> int | None:
    if not isinstance(e, requests.HTTPError):
        return None
    e: requests.HTTPError
    ret = e.response.status_code
    return ret
