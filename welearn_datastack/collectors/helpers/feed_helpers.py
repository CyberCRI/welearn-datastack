from typing import List

from welearn_datastack.data.db_models import Corpus, WeLearnDocument

url_illegal_characters = ['"', "<", ">"]


def lines_to_url(domain: str, link_lines: List[str]) -> List[str]:
    """
    Retrieve URL from lines of text where URL are supposed to be
    :param domain:  The domain of the URL
    :param link_lines:  The lines of text where URL are supposed to be
    :return: The list of URL
    """
    urls: List[str] = []
    # Refine lines to get URL
    for line in link_lines:
        scheme = "https://"
        https_place = line.find(scheme)
        cursor = line[https_place:]
        illegal_char_pos = [
            cursor.find(x) for x in url_illegal_characters if cursor.find(x) >= 0
        ]
        end_place = min(illegal_char_pos)
        url = cursor[:end_place]
        url = url.strip()

        if url.startswith(domain):
            urls.append(url)
    return urls


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
