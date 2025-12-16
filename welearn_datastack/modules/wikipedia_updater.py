import logging
from datetime import datetime

import requests  # type: ignore
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


def _get_revision_id(
    session: requests.Session, page_title: str, rvstart: datetime, lang: str
) -> str | None:
    url = f"https://{lang}.wikipedia.org/w/api.php"

    params = {
        "action": "query",
        "prop": "revisions",
        "titles": page_title,
        "rvlimit": "1",
        "rvprop": "ids",
        "rvdir": "newer",
        "rvstart": rvstart.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rvslots": "main",
        "formatversion": "2",
        "format": "json",
    }

    # We use this API : https://www.mediawiki.org/wiki/API:Revisions
    resp = session.get(url=url, params=params)
    data = resp.json()

    pages = data.get("query", {}).get("pages", [])
    if pages and "revisions" in pages[0]:
        revision = pages[0]["revisions"][0]
        return revision["revid"]

    return None


def is_redirection(document: WeLearnDocument) -> bool:
    """
    Determine if the Wikipedia page is a redirection page.

    :param document: WeLearnDocument object containing title and lang attributes.
    :return: True if the page is a redirection, False otherwise.
    :raises ValueError: If title or lang attributes are missing.
    """
    if not document.title:
        raise ValueError("Document title is required")
    if not document.lang:
        raise ValueError("Document language is required")

    lang = document.lang
    page_title = document.title

    session = get_new_https_session()
    url = f"https://{lang}.wikipedia.org/w/rest.php/v1/page/{page_title}/with_html"

    # We use this API : https://www.mediawiki.org/wiki/API:REST_API/Reference#Page_object
    resp = session.head(url=url, allow_redirects=False)
    resp.raise_for_status()

    if resp.status_code == 301:
        resp = session.head(url=resp.headers["location"], allow_redirects=False)
        resp.raise_for_status()

    if resp.status_code == 307:
        return True
    return False


def is_too_different(document: WeLearnDocument) -> bool:
    """
    Compares the current version of a Wikipedia document with the one available in WeLearn database
    to determine if the size difference exceeds a 5% threshold.

    Args:
        document (WeLearnDocument): An object representing the document to compare.
            It must include the following attributes:
            - title (str): The title of the Wikipedia page.
            - lang (str): The language code of the Wikipedia page (e.g., 'en' for English).
            - updated_at (datetime): The timestamp of the last known update in WeLearn database.

    Returns:
        bool: True if the size difference between the current version and the
        previous version exceeds 5% of the previous version's size, False otherwise.

    Raises:
        KeyError: If the response from the Wikipedia API does not contain the
        expected "compare" or "diffsize" keys.
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
    """
    if not document.title:
        raise ValueError("Document title is required")
    if not document.lang:
        raise ValueError("Document language is required")

    session = get_new_https_session()

    url = f"https://{document.lang}.wikipedia.org/w/api.php"

    params = {
        "action": "compare",
        "format": "json",
        "fromtitle": document.title,
        "fromrev": _get_revision_id(
            session, document.title, document.updated_at, document.lang
        ),
        "torelative": "cur",
        "prop": "size|diffsize",
    }

    resp = session.get(url=url, params=params)
    try:
        data = resp.json()["compare"]
    except KeyError as e:
        raise KeyError("Unexpected response from Wikipedia API") from e

    return data["diffsize"] > 0.05 * data["fromsize"]  # 5% threshold
