import logging
import os
from typing import List

import extruct
from bs4 import BeautifulSoup  # type: ignore
from trafilatura import extract
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.exceptions import NoContent
from welearn_datastack.modules.scraping_utils import clean_return_to_line, clean_text
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class NotreEnvironnementCollector(IPluginScrapeCollector):
    related_corpus = "notre-environnement"

    def __init__(self):
        super().__init__()
        self.page_delay = int(os.environ.get("PAGE_DELAY", 10))

    def _get_document(self, url: str) -> str:
        client = get_new_https_session()
        logger.info(
            f"Waiting for {self.page_delay} seconds before scraping the next page to avoid being blocked by the server",
        )
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text

    def _get_full_content(self, html_text: str) -> str:
        content = extract(filecontent=html_text)
        if not content:
            raise NoContent
        return clean_text(clean_return_to_line(content))

    def _get_dublin_core_metadata(
        self, html_text: str, base_url: str
    ) -> dict[str, str | list[str]]:
        ret: dict[str, str | list[str]] = {}
        data: dict = extruct.extract(
            html_text, base_url=base_url, syntaxes=["dublincore"]
        )

        for element in data.get("dublincore", {}).get("elements", []):
            element: dict[str, str]
            content = element.get("content", "")
            name = element.get("name", "")

            if not content or not name:
                logger.warning("One metadata is empty or no named")

            if name in ret:
                if not type(ret[name]) == list:
                    ret[name] = [ret[name]]
                ret[name].append(content)
            else:
                ret[name] = content

        return ret

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running NotreEnvironnementCollector plugin")
        ret: List[WrapperRetrieveDocument] = []
        for document in documents:
            html_document = self._get_document(document.url)
            dublin_core_metadata = self._get_dublin_core_metadata(
                html_document, document.url
            )
            document.full_content = self._get_full_content(html_document)
