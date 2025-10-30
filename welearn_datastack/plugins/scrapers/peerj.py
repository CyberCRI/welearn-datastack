import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests  # type: ignore
from bs4 import BeautifulSoup, Tag  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import AUTHORIZED_LICENSES
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.exceptions import UnauthorizedLicense
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import (
    clean_return_to_line,
    extract_property_from_html,
)

logger = logging.getLogger(__name__)


def _delete_start_or_end_of_sentences_markers(sentence: str) -> str:
    """
    Delete the start or end of sentences markers.
    :param sentence: The sentence to clean.
    :return: The cleaned sentence.
    """
    return sentence.strip(".,!? \n\t")


def format_news_keywords(raw_news_keywords: Optional[str]) -> List[str]:
    if raw_news_keywords is None:
        return []

    split_raw_keywords = raw_news_keywords.split(",")
    return [x.strip() for x in split_raw_keywords]


class PeerJCollector(IPluginScrapeCollector):
    related_corpus = "peerj"

    def __init__(self):
        super().__init__()
        self.timeout = int(os.environ.get("SCRAPING_TIMEOUT", 60))
        self.wait_time = int(os.environ.get("SCRAPING_WAIT_TIME", 10))

    @staticmethod
    def _get_document_details(soup: BeautifulSoup) -> Dict[str, Any]:
        ret: Dict[str, Any] = {}

        license_bs = soup.find("span", {"class": "license-p"})

        if not isinstance(license_bs, Tag):
            raise UnauthorizedLicense("No license span found")

        license_bs_tag_url = license_bs.find("a")

        if not isinstance(license_bs_tag_url, Tag):
            raise UnauthorizedLicense("No license URL found")

        license_bs_url = license_bs_tag_url.get("href")

        # Check if license is authorized
        if license_bs_url not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(license_bs_url)

        ret["license_url"] = license_bs_url

        meta_datas = [meta.attrs for meta in soup.find_all("meta")]
        authors_institutions: Dict[str, List[str]] = {}
        cursor: str = ""
        for m in meta_datas:
            tag_content = m.get("content")
            match m.get("name"):
                case "citation_author":
                    cursor = tag_content
                    authors_institutions[tag_content] = []
                case "citation_author_institution":
                    authors_institutions[cursor].append(tag_content)
                case "citation_keywords":
                    ret["tags"] = [x.strip() for x in tag_content.split(";")]
                case "citation_journal_title":
                    ret["journal"] = tag_content
                case "citation_issn":
                    ret["issn"] = tag_content
                case "citation_doi":
                    ret["doi"] = tag_content
                case "citation_publisher":
                    ret["publisher"] = tag_content
                case "citation_date":
                    # convert date to timestamp
                    ret["publication_date"] = (
                        datetime.strptime(tag_content, "%Y-%m-%d")
                        .replace(tzinfo=timezone.utc)
                        .timestamp()
                    )

        ret["authors"] = [
            {"name": k, "misc": ", ".join(v)} for k, v in authors_institutions.items()
        ]

        return ret

    @staticmethod
    def _clean_dom(article_dom) -> Tag:
        for useless_category in article_dom.find_all(
            "section", {"id": ["supplemental-information", "supplementary-material"]}
        ):
            useless_category.decompose()

        for tables_in_figures in article_dom.find_all("figure"):
            try:
                tables_in_figures.replace_with(
                    BeautifulSoup(
                        PeerJCollector._figure_to_paragraph(tables_in_figures),
                        "html.parser",
                    )
                )
            except Exception as e:
                logger.error("Error while converting figure to paragraph: %s", e)
                tables_in_figures.decompose()

        for unwanted_element in article_dom.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "table", "figure"]
        ):
            unwanted_element.decompose()

        return article_dom

    @staticmethod
    def _figure_to_paragraph(soup_: BeautifulSoup) -> str:
        """
        Convert a figure to a paragraph
        :param soup_: The figure to convert
        :return: The paragraph
        """
        if soup_ is None:
            return ""

        # Get title
        title_dom = soup_.find("div", class_="title")
        if title_dom is not None:
            title = title_dom.get_text()
        else:
            title = ""

        # Get the rows of the table
        rows = soup_.find_all("tr")
        if len(rows) == 0:
            return ""
        # Get the headers of the table
        headers = [
            _delete_start_or_end_of_sentences_markers(header.get_text())
            for header in rows[0].find_all("th")
        ]
        if len(headers) == 0:
            return ""

        # Get the data of the table
        data = [
            [
                _delete_start_or_end_of_sentences_markers(cell.get_text())
                for cell in row.find_all("td")
            ]
            for row in rows[1:]
        ]
        if len(data) == 0:
            return ""

        # Create the sentence
        sentence = ""
        for row in data:
            sentence += f"{_delete_start_or_end_of_sentences_markers(title)}: "
            for h in headers:
                # Retrieve corresponding data (same index than the header)
                sentence += f"{h}: {row[headers.index(h)]}, "

            # Remove the last ", " and add a "." at the end of the sentence
            sentence = sentence[:-2] + ".\n"
        return sentence

    def _scrape_url(self, document: WeLearnDocument) -> WeLearnDocument:
        """
        Scrape an document
        :param document: Document to scrape
        :return: WrapperRetrieveDocument
        """
        logger.info("Scraping url : '%s'", document.url)

        simple_page_url = document.url
        # Generate simple page url
        if not document.url.endswith(".html"):
            if document.url.endswith("/"):
                simple_page_url = simple_page_url[:-1]
            simple_page_url += ".html"

        logger.info("Simple page url : '%s'", simple_page_url)

        # Create a new session object
        session = get_new_https_session()
        req_res = session.get(url=simple_page_url, timeout=self.timeout)
        logger.info("Requests status : '%s'", req_res.status_code)
        req_res.raise_for_status()
        txt = req_res.text
        soup = BeautifulSoup(txt, "html.parser")

        # Get content
        content_beautifulsoup = soup.find(
            "main",
        )
        content_bs_txt = clean_return_to_line(
            self._clean_dom(content_beautifulsoup).text
        )

        # Get title
        title = extract_property_from_html(
            soup.find("h1", {"class": "article-title"}),
            mandatory=True,
            error_property_name="title",
        )

        # Get description
        description = extract_property_from_html(
            soup.find("meta", {"name": "description"}),
            mandatory=True,
            error_property_name="description",
        )

        document.title = title
        document.description = description
        document.full_content = content_bs_txt
        document.details = self._get_document_details(soup=soup)

        return document

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running PeerJCollector plugin")
        ret: List[WrapperRetrieveDocument] = []
        for document in documents:
            try:
                ret.append(
                    WrapperRetrieveDocument(
                        document=self._scrape_url(document),
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
        logger.info("PeerJCollector plugin finished, %s urls scraped", len(ret))
        return ret
