import datetime
import io
import logging
import math
import os
import re
import time
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup, ResultSet  # type: ignore
from requests.exceptions import RequestException
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import HEADERS
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.exceptions import NoContent
from welearn_datastack.modules.pdf_extractor import (
    delete_accents,
    delete_non_printable_character,
    extract_txt_from_pdf_with_tika,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import remove_extra_whitespace

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

    def _get_metadata_from_tika(self, content: io.BytesIO, content_type: str) -> dict:
        with get_new_https_session() as tika_client:
            resp = tika_client.put(
                url=f"{self.tika_address}/meta",
                data=content,
                headers={
                    "Accept": "application/json",
                    "Content-Type": content_type,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()

    def _convert_duration_to_seconds(self, duration_str: str) -> int:
        """
        Convert a duration string like "3 hours", "3.5 hours" or "3-4 hours" to seconds.

        :param duration_str: The duration string to convert.
        :return: The duration in seconds.
        """
        avg_symbol = "-"

        duration_str = duration_str.replace("hours", "").strip()

        if "," in duration_str:
            duration_str = duration_str.replace(",", ".")

        if avg_symbol in duration_str:
            parts = duration_str.split("-")
            course_duration_in_hour = (float(parts[0]) + float(parts[1])) / 2
        else:
            course_duration_in_hour = float(duration_str)

        course_duration_in_seconds = course_duration_in_hour * 3600
        return int(course_duration_in_seconds)

    def _get_details(self, soup: BeautifulSoup) -> dict:
        """
        Get the details of the course from the page
        :param soup: The BeautifulSoup object of the page
        :return: A dictionary with the details of the course
        """
        page_details = soup.find("div", class_="details")
        details: dict = {}
        if not page_details:
            return details
        theme = page_details.find("p", class_="thematic-areas")
        if theme:
            details["theme"] = theme.text.strip().lower()

        duration = page_details.find("p", class_="time")
        if duration:
            details["duration"] = self._convert_duration_to_seconds(
                duration.text.strip()
            )

        # Convert into boolean this property
        certification = page_details.find("p", class_="certification")
        if certification:
            details["certifying"] = (
                certification.text.strip().lower().startswith("with certification")
            )

        type = page_details.find("p", class_="type")
        if type:
            details["course-type"] = type.text.strip().lower()
        return details

    def _get_pdf(self, pdf_url: str):
        with get_new_https_session() as client:
            resp = client.get(url=pdf_url, headers=HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            return resp.content

    def _get_content_and_file_metadata(self, soup: BeautifulSoup) -> tuple[str, dict]:
        """
        Get the content and the metadata of the PDF file
        :param soup: The BeautifulSoup object of the page
        :return: A tuple with the content and the metadata of the PDF file
        """
        try:
            pdf_url = soup.find("a", id="overview_syllabus_download").get("href", "")
        except AttributeError as e:
            raise NoContent from e

        if not pdf_url:
            raise NoContent("No url found")

        try:
            pdf_content_bytes = self._get_pdf(pdf_url)
            pdf_content, tika_metadata = extract_txt_from_pdf_with_tika(
                pdf_content_bytes, tika_base_url=self.tika_address, with_metadata=True
            )
        except RequestException as e:
            raise NoContent from e

        # Delete non printable characters
        pdf_content = [
            [delete_non_printable_character(word) for word in page]
            for page in pdf_content
        ]

        pages = []
        for content in pdf_content:
            page_text = " ".join(content)
            page_text = replace_ligatures(page_text)
            page_text = remove_hyphens(page_text)
            page_text = delete_accents(page_text)

            pages.append(page_text)
        ret = remove_extra_whitespace(" ".join(pages))

        produced_date = tika_metadata.get("pdf:docinfo:created", "")
        produced_timestamp = None
        if produced_date:
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            # Convert into timestamp
            produced_timestamp = math.floor(
                time.mktime(datetime.datetime.strptime(produced_date, fmt).timetuple())
            )

        file_metadata = {
            "produced_date": produced_timestamp if produced_date else None,
        }

        return ret, file_metadata

    def _scrape_document(self, document: WeLearnDocument) -> WeLearnDocument:
        logger.info("Scraping url : '%s'", document.url)

        client = get_new_https_session()
        resp = client.get(url=document.url, timeout=self.timeout)
        resp.raise_for_status()
        tika_metadata = self._get_metadata_from_tika(
            io.BytesIO(resp.content), content_type="text/html; charset=utf-8"
        )
        doc_title = tika_metadata.get("dc:title", "")
        doc_desc = tika_metadata.get("dc:description", "")

        soup = BeautifulSoup(resp.content, features="html.parser")
        details = self._get_details(soup)
        details["image"] = tika_metadata.get("og:image", "")
        details["keywords"] = format_news_keywords(tika_metadata.get("keywords", None))
        details["type"] = "MOOC"

        try:
            content, file_md = self._get_content_and_file_metadata(soup)
            details.update(file_md)
        except NoContent as e:
            logger.warning(
                f"There is no content detected for this url {document.url} : {str(e)}. Degraded mode activated and use description as content"
            )
            content = doc_desc
            details["content_from_pdf"] = False
        else:
            details["content_from_pdf"] = True

        document.title = doc_title
        document.description = doc_desc
        document.full_content = content
        document.details = details

        return document

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running UNCCeLearnCollector plugin")
        ret: List[WrapperRetrieveDocument] = []
        for document in documents:
            try:
                ret.append(
                    WrapperRetrieveDocument(
                        document=self._scrape_document(document),
                    )
                )
            except Exception as e:
                msg = f"Error while scraping url,\n url: '{document.url}' \nError: {str(e)}"
                logger.exception(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                        http_error_code=get_http_code_from_exception(e),
                    )
                )
                continue

        logger.info("UNCCeLearnCollector plugin finished, %s urls scraped", len(ret))
        return ret
