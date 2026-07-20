import logging
import os
from datetime import datetime
from typing import List

import extruct
import requests
from bs4 import BeautifulSoup  # type: ignore
from trafilatura import extract
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.exceptions import NoContent
from welearn_datastack.modules.scraping_utils import clean_return_to_line, clean_text
from welearn_datastack.plugins.interface import IPluginScrapeCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)

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

    @staticmethod
    def _get_full_content(html_text: str) -> str:
        content = extract(filecontent=html_text)
        if not content:
            raise NoContent
        return clean_text(clean_return_to_line(content))

    @staticmethod
    def _get_dublin_core_metadata(
        html_text: str, base_url: str
    ) -> dict[str, str | list[str]]:
        ret: dict[str, str | list[str]] = {}
        data: dict = extruct.extract(
            html_text, base_url=base_url, syntaxes=["dublincore"]
        )

        for metadata_category in ["elements", "terms"]:
            for element in data.get("dublincore", {}).get(metadata_category, []):
                element: dict[str, str]
                content = element.get("content", "")
                name = element.get("name", "")

                if not content or not name:
                    logger.warning("One metadata is empty or no named")

                if name in ret:
                    if not isinstance(ret[name], list):
                        ret[name] = [ret[name]]
                    ret[name].append(content)
                else:
                    ret[name] = content

        return ret

    def _compute_metadata(self, document: WeLearnDocument, html_document: str):
        dublin_core_metadata = self._get_dublin_core_metadata(
            html_document, document.url
        )
        details: dict = {}
        t_format = "%Y-%m-%d"

        for md_name in dublin_core_metadata:
            if md_name.lower() == "descritpion":
                document.desc = dublin_core_metadata[md_name]
            if md_name.lower() == "dc.title":
                document.title = dublin_core_metadata[md_name]
            if md_name.lower() == "dc.date":
                dt = datetime.strptime(
                    dublin_core_metadata[md_name], t_format
                ).timestamp()
                details["publication_date"] = int(dt)
            if md_name.lower() == "dc.data.modified":
                dt = datetime.strptime(
                    dublin_core_metadata[md_name], t_format
                ).timestamp()
                details["update_date"] = int(dt)
        document.details = details

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running NotreEnvironnementCollector plugin")
        ret: List[WrapperRetrieveDocument] = []
        for document in documents:
            try:
                html_document = self._get_document(document.url)
                document.full_content = self._get_full_content(html_document)
                self._compute_metadata(html_document=html_document, document=document)
            except NoContent as e:
                logger.warning(
                    f"Document {document.url} skipped due to no content: {e}"
                )
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=f"From Document Hub Collector, no content: {e}",
                        http_error_code=204,
                    )
                )
                continue
            except requests.HTTPError as e:
                http_code = get_http_code_from_exception(e)
                logger.exception(
                    f"Document {document.url} skipped due to HTTP error {http_code}: {e}"
                )
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=f"From Document Hub Collector, HTTP error {http_code}: {e}",
                        http_error_code=http_code,
                    )
                )
                continue
            ret.append(
                WrapperRetrieveDocument(
                    document=document,
                )
            )
        return ret
