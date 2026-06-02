import logging
import os
from typing import List
from urllib.parse import urlparse

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.helpers.feed_helpers import (
    extracted_url_to_url_datastore,
    lines_to_url,
)
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.utils_.http_client_utils import get_new_https_session

url_illegal_characters = ['"', "<", ">"]
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "TE": "Trailers",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
}

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


class AtomURLCollector(URLCollector):
    def __init__(
        self,
        feed_url: str,
        corpus: Corpus,
    ) -> None:
        self.feed_url = feed_url
        self.corpus = corpus

    def collect(self) -> List[WeLearnDocument]:
        domain = "https://" + urlparse(self.corpus.main_url).netloc
        client = get_new_https_session()
        res = client.get(url=self.feed_url, headers=headers)
        content = res.content.decode("utf-8")
        link_lines = []

        entries = XMLExtractor(content).extract_content(tag="entry")
        for entry in entries:
            links = XMLExtractor(entry.content).extract_content_attribute_filter(
                tag="link", attribute_name="rel", attribute_value="alternate"
            )
            if not links:
                logger.warning(
                    "No link found for entry, skipping entry. Entry content: %s",
                    entry.content,
                )
                continue

            if len(links) > 1:
                logger.warning(
                    "Multiple rel='alternate' links found for entry; using the first. Entry content: %s",
                    entry.content,
                )

            link_lines.append(links[0].attributes.get("href", ""))

        urls = lines_to_url(domain, link_lines)

        ret = extracted_url_to_url_datastore(urls=urls, corpus=self.corpus)

        return ret
