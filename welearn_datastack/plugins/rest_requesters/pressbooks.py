import logging
from collections import defaultdict
from datetime import datetime
from typing import List, Tuple
from urllib.parse import urlparse, urlunparse

import requests.exceptions
import spacy

from welearn_datastack.constants import AUTHORIZED_LICENSES
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import clean_text

logger = logging.getLogger(__name__)

CONTAINERS_NAME = ["parts", "chapters", "front-matter", "back-matter"]

nlp_model = spacy.load("xx_sent_ud_sm")


# Collector
class PressBooksCollector(IPluginRESTCollector):
    related_corpus = "press-books"

    @staticmethod
    def _create_pressbook_id(main_url: str, post_id: int):
        return f"{main_url}?p={post_id}"

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

    @staticmethod
    def _extract_three_first_sentences(text: str) -> str:
        """
        Extracts the first three sentences from a given text.
        :param text: The input text from which to extract sentences.
        :return: A string containing the first three sentences.
        """
        doc = nlp_model(text)
        sentences = [sent.text for sent in doc.sents]
        return " ".join(sentences[:3]) if len(sentences) >= 3 else text

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
                    url = self._create_pressbook_id(main_url, post_id)
                    if post_id not in main_urls[main_url]:
                        # Retrieve document doesnt exist in previous retrieved url
                        logger.warning(
                            f"Post ID {post_id} not found in main URLs for {main_url}"
                        )
                        error_docs.append(url)
                        continue
                    metadata_url = item["_links"]["metadata"][0]["href"]
                    if not metadata_url.endswith("/"):
                        metadata_url += "/"
                    metadata_resp = client.get(metadata_url)
                    try:
                        metadata_resp.raise_for_status()
                    except requests.exceptions.RequestException:
                        logger.error(
                            f"Error while retrieving metadata for post ID {post_id} in {main_url}"
                        )
                        error_docs.append(url)
                        continue
                    metadata = metadata_resp.json()
                    license_url = metadata["license"]["url"]
                    if license_url not in AUTHORIZED_LICENSES:
                        logger.error(
                            f"Unauthorized license {license_url} for post ID {post_id} in {main_url}"
                        )
                        error_docs.append(url)
                        continue
                    title = metadata["name"]

                    # Content stuff
                    not_formatted_content = item["content"]["raw"]
                    content = clean_text(not_formatted_content)

                    # Date stuff
                    pubdate: float | None
                    if "date_gmt" in metadata:
                        collected_pubdate = metadata["date_gmt"]
                        pubdate = datetime.strptime(
                            collected_pubdate, "%Y-%m-%dT%H:%M:%S"
                        ).timestamp()
                    elif "datePublished" in metadata:
                        # Fallback for datePublished
                        collected_pubdate = metadata["datePublished"]
                        pubdate = datetime.strptime(
                            collected_pubdate, "%Y-%m-%d"
                        ).timestamp()
                    else:
                        logger.warning(
                            f"No publication date found for post ID {post_id} in {main_url}"
                        )
                        pubdate = None

                    update_date: float | None
                    if "modified_gmt" in metadata:
                        collected_update_date = metadata["modified_gmt"]
                        update_date = datetime.strptime(
                            collected_update_date, "%Y-%m-%dT%H:%M:%S"
                        ).timestamp()
                    else:
                        logger.warning(
                            f"No update date found for post ID {post_id} in {main_url}"
                        )
                        update_date = None

                    # Authors stuff
                    authors = []
                    for author in metadata["author"]:
                        authors.append(
                            {
                                "name": author["name"],
                                "misc": author.get("contributor_institution"),
                            }
                        )

                    # Editors stuff
                    editors = []
                    for editor in metadata["editor"]:
                        editors.append(
                            {
                                "name": editor["name"],
                            }
                        )

                    publisher = metadata.get("publisher", {}).get("name")

                    details = {
                        "license": license_url,
                        "update_date": update_date,
                        "publication_date": pubdate,
                        "authors": authors,
                        "editors": editors,
                        "publisher": publisher,
                        "type": container_name,
                        "partOf": {"element": main_url, "order": None},
                    }

                    collected_docs.append(
                        ScrapedWeLearnDocument(
                            document_title=title,
                            document_url=url,
                            document_content=content,
                            document_corpus=self.related_corpus,
                            document_desc=self._extract_three_first_sentences(content),
                            document_details=details,
                        )
                    )
        return collected_docs, error_docs


if __name__ == "__main__":
    # Example usage
    collector = PressBooksCollector()
    urls = [
        "https://wtcs.pressbooks.pub/communications/?p=5",
    ]
    scraped_docs, error_docs = collector.run(urls)
    print(f"Scraped Documents: {len(scraped_docs)}")
    print(f"Error Documents: {len(error_docs)}")
