import logging
import os
from typing import List

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.helpers.feed_helpers import (
    extracted_url_to_url_datastore,
)
from welearn_datastack.data.url_collector import URLCollector
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


class SiteMapURLCollector(URLCollector):
    def __init__(
        self,
        sitemap_url: str,
        corpus: Corpus,
    ) -> None:
        self.sitemap_url = sitemap_url
        self.corpus = corpus

    @staticmethod
    def _is_sitemap_index(sitemap_to_test: str) -> bool:
        extractor = XMLExtractor(sitemap_to_test)
        index = extractor.extract_content("sitemapindex")

        if index:
            return True
        return False

    @staticmethod
    def _extract_urls(sitemap_to_test: str) -> list[str]:
        ret = []
        extractor = XMLExtractor(sitemap_to_test)
        for loc in extractor.extract_content("loc"):
            ret.append(loc.content)
        return ret

    def collect(self) -> List[WeLearnDocument]:
        logger.info("Start sitemap url collector")
        http_client = get_new_https_session()

        sitemap_resp = http_client.get(self.sitemap_url)
        sitemap_resp.raise_for_status()
        sitemap_content = sitemap_resp.content

        is_index = self._is_sitemap_index(sitemap_content)
        logger.info("Sitemap is index ? : %s", is_index)

        sitemaps_urls = []
        if is_index:
            logger.info("Sitemap %s is index", self.sitemap_url)
            for subsitemap_url in self._extract_urls(sitemap_content):
                subsitemap_resp = http_client.get(subsitemap_url)
                subsitemap_resp.raise_for_status()
                subsitemap_content = subsitemap_resp.content
                sitemaps_urls.extend(self._extract_urls(subsitemap_content))
        else:
            logger.info("Sitemap %s is not index", self.sitemap_url)
            sitemaps_urls.append(self.sitemap_url)

        page_urls = []

        for sm_url in sitemaps_urls:
            pages_container = http_client.get(sm_url)
            pages_container.raise_for_status()
            pages_container_content = pages_container.content
            page_urls.extend(self._extract_urls(pages_container_content))

        logger.info("We found %s urls", len(page_urls))
        ret = extracted_url_to_url_datastore(urls=page_urls, corpus=self.corpus)

        return ret
