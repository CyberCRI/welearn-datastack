import logging
from cgi import parse
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Tuple, TypedDict
from urllib.parse import urlparse, urlunparse

import requests.exceptions

from welearn_datastack.constants import AUTHORIZED_LICENSES
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import UnauthorizedLicense
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import (
    clean_return_to_line,
    clean_text_keep_punctuation,
)
from welearn_datastack.utils_.text_stat_utils import predict_readability

logger = logging.getLogger(__name__)

CONTAINERS_NAME = ["parts", "chapters", "front-matter", "back-matter"]


# Collector
class PressBooksCollector(IPluginRESTCollector):
    related_corpus = "press-books"

    def _extract_books_main_url(self, urls: List[str]):
        ret = defaultdict(list)
        for url in urls:
            parsed_url = urlparse(url)
            book_addr = urlunparse(
                ["https", parsed_url.netloc, parsed_url.path, "", "", ""]
            )
            post_id = int(parsed_url.query.split("=")[-1])  # Left part
            ret[book_addr].append(post_id)

        return ret

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        client = get_new_https_session()
        main_urls = self._extract_books_main_url(urls)

        collected_docs: List[ScrapedWeLearnDocument] = []
        error_docs: List[str] = []
        # Get different book containers
        for main_url in main_urls:
            for container_name in CONTAINERS_NAME:
                forged_url = f"{main_url}/wp-json/pressbooks/v2/{container_name}"
                container_content = client.get(url=forged_url)
                try:
                    container_content.raise_for_status()
                except requests.exceptions.RequestException:
                    logger.error(
                        f"Error while retrieving {container_name} for {main_url}: {forged_url}"
                    )
                    continue
                container_content = container_content.json()
                if not container_content:
                    logger.warning(
                        f"No content found for {container_name} in {main_url}"
                    )
                    continue

                for item in container_content:
                    post_id = item["id"]
                    if post_id not in main_urls[main_url]:
                        # Retrieve document doesnt exist in previous retrieved url
                        logger.warning(
                            f"Post ID {post_id} not found in main URLs for {main_url}"
                        )
                        error_docs.append(f"{main_url}/?p={post_id}")
                        continue
                    metadata_url = item["_links"]["metadata"][0]["href"]
                    metadata_resp = client.get(metadata_url)
                    try:
                        metadata_resp.raise_for_status()
                    except requests.exceptions.RequestException:
                        logger.error(
                            f"Error while retrieving metadata for post ID {post_id} in {main_url}"
                        )
                        error_docs.append(f"{main_url}/?p={post_id}")
                        continue
                    metadata = metadata_resp.json()
                    license_url = metadata["license"]["url"]
                    if license_url not in AUTHORIZED_LICENSES:
                        logger.error(
                            f"Unauthorized license {license_url} for post ID {post_id} in {main_url}"
                        )
                        error_docs.append(f"{main_url}/?p={post_id}")
                        continue
                    title = metadata["name"]

                    # Content stuff
                    not_formatted_content = item["content"]["raw"]
                    content = clean_text_keep_punctuation(not_formatted_content)
