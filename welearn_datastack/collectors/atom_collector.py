import logging
import os
from typing import List
from urllib.parse import urlparse

from welearn_database.data.enumeration import ExternalIdType
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.modules.url_utils import (
    extract_doi_number,
    extract_url_parts_post_netloc,
)
from welearn_datastack.modules.validation import validate_doi
from welearn_datastack.modules.xml_extractor import XMLExtractor
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

url_illegal_characters = ['"', "<", ">"]
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "TE": "Trailers",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
}


class AtomURLCollector(URLCollector):
    def __init__(
        self,
        feed_url: str,
        corpus: Corpus,
    ) -> None:
        self.feed_url = feed_url
        self.corpus = corpus

    def collect(self) -> List[WeLearnDocument]:
        logger.info(
            f"Collecting URLs from feed {self.feed_url} for corpus {self.corpus.id}"
        )
        domain = "https://" + urlparse(self.corpus.main_url).netloc
        client = get_new_https_session()
        res = client.get(url=self.feed_url, headers=headers)
        content = res.content.decode("utf-8")

        logger.debug(f"Content of the feed {self.feed_url} : {content}")

        ret: list[WeLearnDocument] = []
        entries = XMLExtractor(content).extract_content("entry")
        logger.info(f"Found {len(entries)} entries in the feed {self.feed_url}")
        for entry in entries:
            entry_extractor = XMLExtractor(entry.content)
            link = entry_extractor.extract_content_attribute_filter(
                tag="link",
                attribute_name="rel",
                attribute_value="alternate",
            )
            [xml_external_id] = entry_extractor.extract_content("id")
            external_id = xml_external_id.content.strip()
            if len(link) == 0:
                continue
            link_url = link[0].attributes["href"]
            if link_url.startswith(domain):
                if validate_doi(external_id, resolve_doi=False):
                    # If the external ID is a valid DOI, we can use it directly as the external ID and set the type to DOI
                    logger.info(
                        f"External ID {external_id} is a valid DOI for URL {link_url}"
                    )
                    external_id = extract_doi_number(external_id)
                    external_id_type = ExternalIdType.DOI
                else:
                    # Otherwise, we can use the part of the URL after the domain as the external ID and set the type to SLUG
                    logger.info(
                        f"External ID {external_id} is not a valid DOI for URL {link_url}, using the part of the URL after the domain as the external ID"
                    )
                    external_id = extract_url_parts_post_netloc(
                        link_url, remove_start_slash=True
                    )
                    external_id_type = ExternalIdType.SLUG
                ret.append(
                    WeLearnDocument(
                        url=link_url,
                        corpus=self.corpus,
                        external_id=external_id,
                        external_id_type=external_id_type,
                    )
                )
        logger.info(
            f"Collected {len(ret)} URLs from feed {self.feed_url} for corpus {self.corpus.id}"
        )
        return ret
