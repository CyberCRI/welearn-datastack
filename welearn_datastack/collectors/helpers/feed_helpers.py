from typing import List
from urllib.parse import urlparse, urlunparse

from welearn_database.data.models import Corpus, WeLearnDocument

url_illegal_characters = ['"', "<", ">"]


def lines_to_url(domain: str, link_lines: List[str]) -> List[str]:
    """
    Retrieve URL from lines of text where URL are supposed to be
    :param domain:  The domain of the URL
    :param link_lines:  The lines of text where URL are supposed to be
    :return: The list of URL
    """
    urls: List[str] = []
    scheme = "https"
    # Refine lines to get URL
    for line in link_lines:
        line = remove_illegal_character(line)
        parsed = urlparse(line)
        if parsed.netloc == urlparse(domain).netloc or parsed.netloc.endswith(
            f".{urlparse(domain).netloc}"
        ):
            urls.append(
                urlunparse(
                    [
                        scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment,
                    ]
                )
            )

    return urls


def remove_illegal_character(text: str):
    scheme = "https://"
    https_place = text.find(scheme)
    cursor = text[https_place:]
    illegal_char_pos = [
        cursor.find(x) for x in url_illegal_characters if cursor.find(x) >= 0
    ]
    if illegal_char_pos:
        end_place = min(illegal_char_pos)
        url = cursor[:end_place]
    else:
        url = cursor
    return url.strip()


def extracted_url_to_url_datastore(
    corpus: Corpus,
    urls: List[str],
) -> List[WeLearnDocument]:
    """
    Convert a list of URL to a list of URLDataStore
    :param corpus: Corpus object from the database, to link the URL to the corpus
    :param urls: The list of URL to convert
    :return: The list of WeLearnDocument converted
    """
    ret: List[WeLearnDocument] = []
    # Create URLDataStore object for each URL
    for url in urls:
        current = WeLearnDocument(
            url=url,
            corpus=corpus,
        )
        ret.append(current)
    return ret
