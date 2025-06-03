import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import requests  # type: ignore
from bs4 import BeautifulSoup, Tag  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore

from welearn_datastack.constants import ANTI_URL_REGEX, AUTHORIZED_LICENSES
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import UnauthorizedLicense
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import clean_return_to_line
from welearn_datastack.utils_.text_stat_utils import (
    predict_duration,
    predict_readability,
)

logger = logging.getLogger(__name__)


class PlosCollector(IPluginScrapeCollector):
    related_corpus = "plos"

    def __init__(self):
        super().__init__()
        self.timeout = int(os.environ.get("SCRAPING_TIMEOUT", 60))
        self.wait_time = int(os.environ.get("SCRAPING_WAIT_TIME", 10))

    @staticmethod
    def _generate_timestamp_from_html(tag_date: Tag) -> Optional[float]:
        day = ""
        month = ""
        year = ""
        for child in tag_date.children:
            if child.name == "day":  # type: ignore
                day = child.text
            elif child.name == "month":  # type: ignore
                month = child.text
            elif child.name == "year":  # type: ignore
                year = child.text

        return datetime(
            year=int(year),
            month=int(month),
            day=int(day),
            tzinfo=timezone.utc,
        ).timestamp()

    def _get_document_details(self, soup: BeautifulSoup) -> Dict[str, Any]:
        ret: Dict[str, Any] = {}

        # Journal meta
        journal_meta = soup.find("journal-meta")

        if not isinstance(journal_meta, Tag):
            raise ValueError("No journal meta found")

        # Article meta
        article_meta = soup.find("article-meta")

        if not isinstance(article_meta, Tag):
            raise ValueError("No article meta found")

        categories = self._get_categories(article_meta)

        authors = self._get_authors(article_meta)

        doi_extract = article_meta.find("article-id", {"pub-id-type": "doi"})
        published_id_extract = article_meta.find(
            "article-id", {"pub-id-type": "publisher-id"}
        )
        doi = "" if not isinstance(doi_extract, Tag) else doi_extract.text
        published_id = (
            ""
            if not isinstance(published_id_extract, Tag)
            else published_id_extract.text
        )

        journal_extract = journal_meta.find("journal-title")
        journal = "" if not isinstance(journal_extract, Tag) else journal_extract.text

        article_type = self._get_article_type(article_meta)

        pubdate_extract = article_meta.find("pub-date", {"pub-type": "epub"})
        publication_date = None
        if isinstance(pubdate_extract, Tag):
            publication_date = self._generate_timestamp_from_html(pubdate_extract)

        issn_extract = journal_meta.find("issn")
        issn = "" if not isinstance(issn_extract, Tag) else issn_extract.text

        pub_name_extract = journal_meta.find("publisher-name")
        pub_loc_extract = journal_meta.find("publisher-loc")
        publisher = ""
        if isinstance(pub_name_extract, Tag) and isinstance(pub_loc_extract, Tag):
            publisher = f"{pub_name_extract.text}, {pub_loc_extract.text}"

        license_url = self._handle_license(article_meta)

        tags = list(categories)

        ret = {
            "authors": authors,
            "doi": doi,
            "published_id": published_id,
            "journal": journal,
            "type": clean_return_to_line(article_type),
            "publication_date": int(publication_date) if publication_date else None,
            "issn": issn,
            "license_url": license_url,
            "tags": tags,
            "publisher": publisher,
        }
        return ret

    @staticmethod
    def _handle_license(article_meta):
        """
        Extract license from article meta tag and check if it is authorized
        :param article_meta: BeautifulSoup tag
        :return: License URL
        """
        license_extract = article_meta.find("license")
        if not isinstance(license_extract, Tag):
            raise UnauthorizedLicense("No license found")
        license_url = license_extract.get("xlink:href", default="")  # type: ignore
        if isinstance(license_url, list):
            license_url = license_url[0].strip()
        if license_url not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(license_url)
        return license_url

    @staticmethod
    def _get_article_type(article_meta):
        """
        Extract article type from article meta tag
        :param article_meta: BeautifulSoup tag
        :return: Article type
        """
        article_type = ""
        article_category_extract = article_meta.find("article-categories")
        if article_category_extract is not None:
            article_type_extract = article_category_extract.find(
                "subj-group", {"subj-group-type": "heading"}  # type: ignore
            )

            if isinstance(article_type_extract, Tag):
                article_type = article_type_extract.text
        return article_type

    @staticmethod
    def _get_authors(article_meta):
        """
        Extract authors from article meta tag and return a list of authors
        :param article_meta: BeautifulSoup tag
        :return: List of authors
        """
        # Authors
        contributors = article_meta.find_all("contrib", {"contrib-type": "author"})
        authors = []
        for contrib in contributors:
            author = {}

            # Name
            name_tag = contrib.find_next("name")
            name = ""
            for name_part in name_tag.children:
                if name_part.text != "\n":
                    name += name_part.text + " "
            name.strip()
            author["name"] = clean_return_to_line(name)

            # Misc
            affiliation_id = contrib.find("xref", {"ref-type": "aff"}).get("rid")
            aff = article_meta.find("aff", {"id": affiliation_id})

            misc = ""
            if aff is not None:
                extract_aff = aff.find("addr-line")
                if isinstance(extract_aff, Tag):
                    misc = extract_aff.text
            author["misc"] = clean_return_to_line(misc)

            authors.append(author)
        return authors

    @staticmethod
    def _get_categories(article_meta):
        """
        Extract categories from article meta tag and return a set of categories
        :param article_meta: BeautifulSoup tag
        :return: Set of categories
        """
        # Categories
        categories = set()
        for subject in article_meta.find_all("subject"):
            if subject.parent.get("subj-group-type"):
                categories.add(subject.text.strip())
        return categories

    def _scrape_url(self, url: str) -> ScrapedWeLearnDocument:
        """
        Scrape an url
        :param url: Url to scrape
        :return: ScrapedWeLearnDocument
        """
        logger.info("Scraping url : '%s'", url)

        api_page_url = self._generate_api_url(url)
        logger.info("Simple page url : '%s'", api_page_url)

        # Create a new session object
        session = get_new_https_session()
        req_res = session.get(url=api_page_url, timeout=self.timeout)
        logger.info("Requests status : '%s'", req_res.status_code)
        req_res.raise_for_status()
        txt = req_res.text

        scraped_document = self.extract_data_from_plos_xml(txt, url)

        return scraped_document

    def extract_data_from_plos_xml(self, txt, url):
        soup = BeautifulSoup(txt, "html.parser")

        # Document content and lang
        body = soup.find("body")
        if not isinstance(body, Tag):
            raise ValueError("No body found")
        for title in body.find_all("title"):
            title.decompose()
        messy_content = body.text
        doc_content = re.sub(ANTI_URL_REGEX, "", messy_content).strip()
        doc_lang_extract = soup.find("article")
        if not isinstance(doc_lang_extract, Tag):
            raise ValueError("No lang tag found")
        doc_lang = doc_lang_extract.get("xml:lang")
        if isinstance(doc_lang, list):
            raise ValueError("Multiple lang found")
        if not doc_lang:
            raise ValueError("No lang found")
        clean_doc_content = clean_return_to_line(doc_content)
        doc_url = url

        # Article meta
        article_meta = soup.find("article-meta")
        if not isinstance(article_meta, Tag):
            raise ValueError("No article meta found")
        doc_title_extract = article_meta.find("article-title")
        if not isinstance(doc_title_extract, Tag):
            raise ValueError("No title found")
        doc_title = doc_title_extract.text
        full_doc_desc_extract = article_meta.find("abstract")
        if not isinstance(full_doc_desc_extract, Tag):
            raise ValueError("No description found")

        doc_desc_extract = full_doc_desc_extract.find_all("p")
        doc_desc = " ".join([p.text for p in doc_desc_extract])

        # Get readability and duration
        readability = predict_readability(text=clean_doc_content, lang=doc_lang)
        duration = predict_duration(text=clean_doc_content, lang=doc_lang)
        doc_details = self._get_document_details(soup=soup)
        doc_details["readability"] = str(readability)
        doc_details["duration"] = str(duration)
        scraped_document = ScrapedWeLearnDocument(
            document_url=doc_url,
            document_title=clean_return_to_line(doc_title),
            document_lang=doc_lang,
            document_desc=clean_return_to_line(doc_desc),
            document_content=clean_doc_content,
            document_details=doc_details,
            document_corpus=self.related_corpus,
        )
        return scraped_document

    def _generate_api_url(self, url):
        # Generate API URL
        parsed_url = urlparse(url)
        new_path_url = f"{parsed_url.path}/file"
        new_query_url = f"{parsed_url.query}&type=manuscript"
        api_page_url = urlunparse(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                new_path_url,
                parsed_url.params,
                new_query_url,
                parsed_url.fragment,
            )
        )
        return api_page_url

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        logger.info("Running PlosJCollector plugin")
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
        logger.info("PlosJCollector plugin finished, %s urls scraped", len(ret))
        return ret, error_docs
