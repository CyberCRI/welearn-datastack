import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, ResultSet  # type: ignore

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import extract_property_from_html

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


class ConversationCollector(IPluginScrapeCollector):
    related_corpus = "conversation"

    def __init__(self):
        super().__init__()
        self.timeout = int(os.environ.get("SCRAPING_TIMEOUT", 60))

    @staticmethod
    def _retrieve_lang_from_js_script(scripts: ResultSet) -> str:
        script_key = "content_language"
        pattern = r"'([A-Za-z]+)'"
        for script in scripts:
            script_text = script.text
            if script_key in script_text:
                matches = re.findall(pattern, script_text)
                if len(matches) > 0:
                    return matches[0]
        return ""

    @staticmethod
    def _get_document_details(soup: BeautifulSoup) -> Dict[str, Any]:
        authors_data = soup.find_all("li", {"class": "vcard"})
        authors: List[dict[str, str]] = []
        for raw_author_data in authors_data:
            author_name = raw_author_data.find("span").text

            author_role_data = clean_str(
                raw_author_data.find("p", {"class": "role"}).text
            ).strip()

            author_data = {"name": clean_str(author_name), "misc": author_role_data}

            authors.append(author_data)
        if soup.find("meta", {"name": "news_keywords"}):
            raw_news_keywords: Optional[str] = soup.find("meta", {"name": "news_keywords"}).get("content")  # type: ignore
        else:
            raw_news_keywords = None
        news_keywords = format_news_keywords(raw_news_keywords)

        if soup.find("meta", {"name": "commissioning-region"}):
            commissioning_region = soup.find("meta", {"name": "commissioning-region"}).get(  # type: ignore
                "content"  # type: ignore
            )
        else:
            commissioning_region = None

        if soup.find("meta", {"name": "pubdate"}):
            str_publication_date = soup.find("meta", {"name": "pubdate"}).get("content")  # type: ignore
            publication_date = datetime.strptime(str_publication_date, "%Y%m%d").timestamp()  # type: ignore
        else:
            publication_date = None

        if soup.find("meta", {"property": "og:updated_time"}):
            str_update_date = soup.find("meta", {"property": "og:updated_time"}).get(  # type: ignore
                "content"  # type: ignore
            )
            update_date = datetime.strptime(  # type: ignore
                str_update_date, "%Y-%m-%dT%H:%M:%SZ"  # type: ignore
            ).timestamp()  # type: ignore
        else:
            update_date = None

        details = {
            "authors": authors,
            "news_keywords": news_keywords,
            "commissioning-region": commissioning_region,
            "publication_date": publication_date,
            "update_date": update_date,
        }

        return details

    def _scrape_url(self, url: str) -> ScrapedWeLearnDocument:
        """
        Scrape an url
        :param url: Url to scrape
        :return: ScrapedWeLearnDocument
        """
        logger.info("Scraping url : '%s'", url)
        https_session = get_new_https_session()

        req_res = https_session.get(url=url, timeout=self.timeout)

        req_res.raise_for_status()  # Raise exception if status code is not a good one

        txt = req_res.text

        soup = BeautifulSoup(txt, "html.parser")

        title = extract_property_from_html(
            soup.find("h1", {"itemprop": "headline"}),
            mandatory=True,
            error_property_name="Title",
        )

        description = extract_property_from_html(
            soup.find("meta", {"property": "og:description"}),
            mandatory=True,
            error_property_name="Description",
        )

        content = extract_property_from_html(
            soup.find("div", {"itemprop": "articleBody"}),
            mandatory=True,
            error_property_name="content",
        )

        doc_url = url
        doc_title = title
        doc_desc = description
        doc_content = content
        doc_details = self._get_document_details(soup)
        scraped_document = ScrapedWeLearnDocument(
            document_url=doc_url,
            document_title=doc_title,
            document_desc=doc_desc,
            document_content=doc_content,
            document_details=doc_details,
            document_corpus=self.related_corpus,
        )

        return scraped_document

    def run(
        self, urls_or_external_ids: List[str], is_external_id=False
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        logger.info("Running ConversationCollector plugin")
        ret: List[ScrapedWeLearnDocument] = []
        error_docs: List[str] = []
        for url in urls_or_external_ids:
            try:
                ret.append(self._scrape_url(url))
            except Exception as e:
                logger.exception(
                    "Error while scraping url,\n url: '%s' \nError: %s", url, e
                )
                error_docs.append(url)
                continue
        logger.info("ConversationCollector plugin finished, %s urls scraped", len(ret))
        return ret, error_docs
