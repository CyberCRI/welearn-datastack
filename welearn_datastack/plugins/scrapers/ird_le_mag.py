import datetime
import json
import logging
import os
import time
from typing import List

import pydantic
import requests
from bs4 import BeautifulSoup  # type: ignore
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import HEADERS
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.exceptions import (
    NoContent,
    NoDescriptionFoundError,
    NotEnoughData,
    NoTitle,
)
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import (
    add_space_after_closing_sign,
    add_space_before_capital_letter,
    clean_return_to_line,
    clean_text,
)

logger = logging.getLogger(__name__)


class IRDLeMagCollector(IPluginScrapeCollector):
    related_corpus = "ird-le-mag"

    def __init__(self):
        super().__init__()
        self.page_delay = int(os.environ.get("PAGE_DELAY", 2))
        self.batch_delay = int(os.environ.get("BATCH_DELAY", 10))

    @staticmethod
    def _get_page(url: str) -> str:
        http_client = get_new_https_session()
        resp = http_client.get(url=url, headers=HEADERS)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _extract_content(page_str: str) -> str:
        """
        The content of the page is stored in a script tag
        <script type="application/json" data-drupal-selector="drupal-settings-json">
            {
                "speakeasy": {
                    "content": "the content of the page"
                }
            }
        </script>

        :param page_str: the html page as a string
        :return: the content of the page as a string
        :raises NoContent: if the content cannot be extracted
        """
        try:
            content_json = json.loads(
                page_str.split(
                    '<script type="application/json" data-drupal-selector="drupal-settings-json">'
                )[1]
                .split("</script>")[0]
                .strip()
            )
        except IndexError as e:
            raise NoContent from e
        except json.decoder.JSONDecodeError as e:
            raise NoContent from e
        try:
            content = content_json["speakeasy"]["content"]
        except KeyError as e:
            raise NoContent from e
        return content

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        title_tag = soup.find("meta", property="og:title")
        if not title_tag:
            raise NoTitle
        try:
            title = title_tag["content"]
        except KeyError as e:
            raise NoTitle from e
        return clean_return_to_line(title)

    @staticmethod
    def _extract_authors(soup: BeautifulSoup) -> list[AuthorDetails | None]:
        ret = []
        prefix = "Auteur :"
        author_info = soup.find("li", class_="info-item name")
        if not author_info:
            return [None]
        content_author_info = author_info.text
        if content_author_info.startswith(prefix):
            content_author_info = content_author_info.replace(prefix, "")
        content_author_info = content_author_info.strip()
        ret.append(AuthorDetails(name=content_author_info, misc=""))
        return ret

    @staticmethod
    def _extract_publication_date(soup: BeautifulSoup) -> int | None:
        try:
            t_format = "%Y-%m-%dT%H:%M:%SZ"
            pub_date_tag = soup.find("time", class_="datetime")
            dt = datetime.datetime.strptime(pub_date_tag["datetime"], t_format)
            dt = dt.replace(tzinfo=datetime.timezone.utc)
            ret = int(dt.timestamp())
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.exception(
                f"An exception occurred while the publication date was being collected: {e}"
            )
            return None
        return ret

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str:
        desc_tag = soup.find("meta", property="og:description")
        if not desc_tag:
            raise NoDescriptionFoundError
        try:
            desc = desc_tag["content"]
        except KeyError as e:
            raise NoDescriptionFoundError from e
        return desc

    @staticmethod
    def correct_text_syntax(content: str) -> str:
        """
        The content of the page is not well formatted, we need to clean it and add spaces after closing signs and before capital letters

        :param content: the content of the page as a string
        :return: the content of the page with the correct syntax
        """
        return add_space_before_capital_letter(
            add_space_after_closing_sign(clean_return_to_line(clean_text(content)))
        )

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running IRDLeMagCollector plugin")
        ret: List[WrapperRetrieveDocument] = []
        for i, document in enumerate(documents):
            if i > 0:
                logger.info(
                    f"Waiting for {self.page_delay} seconds before scraping the next page to avoid being blocked by the server",
                )
                time.sleep(self.page_delay)
                if i % 10 == 0:
                    logger.info(
                        f"Waiting for {self.batch_delay - self.page_delay} seconds before scraping the next batch of pages to avoid being blocked by the server",
                    )
                    time.sleep(self.batch_delay - self.page_delay)
            try:
                page = self._get_page(document.url)
                soup = BeautifulSoup(page, "html.parser")
                if not page:
                    raise NoContent
                document.full_content = self.correct_text_syntax(
                    self._extract_content(page)
                )
                document.title = self._extract_title(soup)
                document.description = self.correct_text_syntax(
                    self._extract_description(soup)
                )
                document.details = {
                    "authors": self._extract_authors(soup),
                    "type": "article",
                    "license_url": "https://lemag.ird.fr/fr/mentions-legales-0",
                    "publication_date": self._extract_publication_date(soup),
                }
                ret.append(WrapperRetrieveDocument(document=document))
            except requests.exceptions.RequestException as e:
                msg = (
                    f"Error while retrieving IRD Le Mag document ({document.url}): {e}"
                )
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        http_error_code=get_http_code_from_exception(e),
                        error_info=msg,
                    )
                )
                continue
            except pydantic.ValidationError as e:
                msg = f"Error while validating IRD Le Mag ({document.url}) : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue
            except NotEnoughData as e:
                msg = f"Not enough data to retrieve document {document.url} from IRD Le Mag : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

        logger.info("IRDLeMagCollector plugin finished, %s urls scraped", len(ret))
        return ret
