import io
import logging
import os
import re
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup, ResultSet  # type: ignore

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


def clean_str(string: str):
    ret = re.sub(r"(\n|\t|\r)", "", string).strip()
    return ret


def format_news_keywords(raw_news_keywords: Optional[str]) -> List[str]:
    if raw_news_keywords is None:
        return []
    elif "," in raw_news_keywords:
        keywords = raw_news_keywords.split(",")
        return [keyword.strip() for keyword in keywords]
    else:
        return [raw_news_keywords.strip()]


class UNCCeLearnCollector(IPluginScrapeCollector):
    related_corpus = "unccelearn"

    def __init__(self):
        super().__init__()
        self.timeout = int(os.environ.get("SCRAPING_TIMEOUT", 60))
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")

    def _get_metadata_from_tika(self, content: io.BytesIO) -> dict:
        with get_new_https_session() as tika_client:
            resp = tika_client.put(
                url=f"{self.tika_address}/meta",
                data=content,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "text/html; charset=utf-8",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()

    def _get_details(self, soup: BeautifulSoup) -> dict:
        page_details = soup.find("div", class_="details")
        details: dict = {}
        if not page_details:
            return details
        theme = page_details.find("p", class_="theme")
        if theme:
            details["theme"] = theme.text.strip()
        # TODO: How to convert this duration to a number of seconds ?
        duration = page_details.find("p", class_="time")
        if duration:
            details["duration"] = duration.text.strip()

        # TODO: Convert it to a boolean
        certification = page_details.find("p", class_="certification")
        if certification:
            details["certification"] = certification.text.strip()

        # TODO: Maybe there is a typology of course here ? Or just classical "type"
        type = page_details.find("p", class_="type")
        if type:
            details["course_type"] = type.text.strip()
        return details

    def _get_content(self, soup: BeautifulSoup) -> str:
        pass

    def _scrape_url(self, url: str) -> ScrapedWeLearnDocument:
        logger.info("Scraping url : '%s'", url)

        with get_new_https_session() as client:
            resp = client.get(url=url, timeout=self.timeout)
            resp.raise_for_status()
            tika_metadata = self._get_metadata_from_tika(io.BytesIO(resp.content))
            doc_title = tika_metadata.get("dc:title", "")
            doc_desc = tika_metadata.get("dc:description", "")

            soup = BeautifulSoup(resp.content, features="html.parser")
            details = self._get_details(soup)
            details["image"] = tika_metadata.get("og:image", "")
            details["keywords"] = format_news_keywords(
                tika_metadata.get("keywords", None)
            )
            details["type"] = "MOOC"

            content = self._get_content(soup)

            return ScrapedWeLearnDocument(
                document_url=url,
                document_title=doc_title,
                document_desc=doc_desc,
                document_content=content,
                document_details=details,
                document_corpus=self.related_corpus,
            )

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        logger.info("Running UNCCeLearnCollector plugin")
        ret: List[ScrapedWeLearnDocument] = []
        error_docs: List[str] = []
        for url in urls:
            try:
                ret.append(self._scrape_url(url))
            except Exception as e:
                logger.exception(
                    "Error while scraping url,\n url: '%s' \nError: %s", url, e
                )
                error_docs.append(url)
                continue
        logger.info("UNCCeLearnCollector plugin finished, %s urls scraped", len(ret))
        return ret, error_docs
