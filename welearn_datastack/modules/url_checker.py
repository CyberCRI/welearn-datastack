import logging
import os
from typing import Tuple

from welearn_datastack.data.enumerations import URLStatus
from welearn_datastack.utils_.http_client_utils import get_new_https_session

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


def check_url(url: str) -> Tuple[URLStatus, int]:
    """
    Check if the URL is valid
    :param url: URL to check
    :return: URLStatus enum value representing the status of the URL
    """
    session = get_new_https_session()
    response = session.get(
        url,
        allow_redirects=False,
    )

    match response.status_code:
        case 200 | 201 | 202 | 203 | 204 | 205 | 206 | 207 | 208 | 226:
            return URLStatus.VALID, response.status_code
        case 301 | 302 | 303 | 307 | 308:
            return URLStatus.UPDATE, response.status_code
        case 400 | 401 | 402 | 404 | 405 | 410 | 419 | 423 | 456:
            return URLStatus.DELETE, response.status_code
        case _:
            logger.error(
                f"Unprocessed status code {response.status_code} for url {url}"
            )
            return URLStatus.UNKNOWN, response.status_code
