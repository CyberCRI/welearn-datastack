import io
import logging
import os

import pydantic
import requests
from welearn_database.data.models import WeLearnDocument
from welearn_database.modules.text_cleaning import clean_text

from welearn_datastack import constants
from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.source_models.fao_open_knowledge import Bundle, Item
from welearn_datastack.exceptions import (
    NoContent,
    NoDescriptionFoundError,
    PDFFileSizeExceedLimit,
    UnauthorizedLicense,
)
from welearn_datastack.modules.pdf_extractor import (
    delete_accents,
    delete_non_printable_character,
    extract_txt_from_pdf_with_tika,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import (
    format_cc_license,
    remove_extra_whitespace,
)

logger = logging.getLogger(__name__)


# Collector
class FAOOpenKnowledgeCollector(IPluginRESTCollector):
    related_corpus = "fao-open-knowledge"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")

        self.api_base_url = "https://openknowledge.fao.org/server/api/"
        self.application_base_url = "https://openknowledge.fao.org/"
        self.headers = constants.HEADERS
        self.pdf_size_file_limit: int = int(os.getenv("PDF_SIZE_FILE_LIMIT", 2000000))

    def _get_pdf_content(self, url: str) -> str:
        logger.info("Getting PDF content from %s", url)
        client = get_new_https_session(retry_total=0)

        if self.pdf_size_file_limit and self.pdf_size_file_limit < 0:
            raise ValueError(
                f"file_size_limit must be positive : {self.pdf_size_file_limit}"
            )

        if self.pdf_size_file_limit:
            resp_head = client.head(
                url, headers=HEADERS, allow_redirects=True, timeout=30
            )
            try:
                content_length = int(resp_head.headers.get("content-length"))
                logger.info(f"PDF size is {content_length}")
            except ValueError:
                raise ValueError(f"Cannot retrieved this pdf size : {url}")

            if content_length > self.pdf_size_file_limit:
                raise PDFFileSizeExceedLimit(
                    f"File size is {content_length} and limit is {self.pdf_size_file_limit}"
                )

        response = client.get(url, headers=HEADERS, timeout=300)
        response.raise_for_status()

        with io.BytesIO(response.content) as pdf_file:
            pdf_content = extract_txt_from_pdf_with_tika(
                pdf_content=pdf_file, tika_base_url=self.tika_address
            )

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

        return ret

    def _clean_txt_content(self, content: str) -> str:
        return clean_text(content)

    @staticmethod
    def _extract_licence(fao_item: Item) -> str:
        md_item = fao_item.metadata.get("dc.rights.license", None)

        if not md_item:
            raise UnauthorizedLicense("No license found.")

        try:
            messy_licence = md_item[0]["value"]
        except (KeyError, IndexError, TypeError):
            raise UnauthorizedLicense("No license found.")

        return format_cc_license(messy_licence.replace(" ", "-"))

    @staticmethod
    def _extract_authors(uved_document: UVEDMemberItem) -> list[AuthorDetails]:
        ret: list[AuthorDetails] = []
        for contributor in uved_document.contributor:
            ret.append(
                AuthorDetails(
                    name=f"{contributor.firstName} {contributor.lastName}", misc=""
                )
            )
        return ret

    @staticmethod
    def _check_licence_authorization(_license: str) -> None:
        if _license not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(f"License '{_license}' is not authorized.")

    def get_metadata_json(self, document: WeLearnDocument) -> Item:
        session = get_new_https_session()
        item_url = f"{self.api_base_url}core/items/{document.external_id}"
        resp = session.get(url=item_url, headers=self.headers)
        resp.raise_for_status()

        item_json = Item.model_validate(resp.json())
        return item_json

    def get_bundle_json(self, document: WeLearnDocument) -> list[Bundle]:
        session = get_new_https_session()
        bundle_url = f"{self.api_base_url}core/items/{document.external_id}/bundles"
        resp = session.get(url=bundle_url, headers=self.headers)
        resp.raise_for_status()

        bundle_json = [Bundle.model_validate(b) for b in resp.json()["_embedded"]]
        return bundle_json

    @staticmethod
    def extract_bitstream_id(bundles: list[Bundle]) -> str | None:
        for bundle in bundles:
            if bundle.name == "ORIGINAL":
                return bundle.uuid
        return None

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        ret: list[WrapperRetrieveDocument] = []
        for document in documents:
            try:
                fao_ok_metadata = self.get_metadata_json(document)
                self._check_licence_authorization(
                    self._extract_licence(fao_ok_metadata)
                )
                bundle_json = self.get_bundle_json(document)
                pdf_id = self.extract_bitstream_id(bundle_json)
                if not pdf_id:
                    raise NoContent("No PDF bitstream found.")
                pdf_url = f"{self.api_base_url}core/bitstreams/{pdf_id}/content"
                pdf_content = self._get_pdf_content(pdf_url)
                if not pdf_content or pdf_content.isspace():
                    raise NoContent("No content extracted from PDF.")
                document.full_content = self._clean_txt_content(pdf_content)
                try:
                    description = fao_ok_metadata.metadata.get(
                        "dc.description.abstract"
                    )[0].get("value", "")
                except (AttributeError, IndexError, KeyError, TypeError):
                    raise NoDescriptionFoundError("No description found.")
                if not description or description.isspace():
                    raise NoDescriptionFoundError("No description found.")
                document.description = clean_text(description)
                document.title = fao_ok_metadata.name

            except UnauthorizedLicense as e:
                logger.warning(
                    f"Document {document.url} skipped due to unauthorized license: {e}"
                )
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=f"From Document Hub Collector, unauthorized license: {e}",
                    )
                )
                continue
            except pydantic.ValidationError as e:
                logger.error(
                    f"Document {document.url} skipped due to validation error: {e}"
                )
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=f"From Document Hub Collector, validation error: {e}",
                    )
                )
                continue
            except requests.HTTPError as e:
                http_code = get_http_code_from_exception(e)
                logger.error(
                    f"Document {document.url} skipped due to HTTP error {http_code}: {e}"
                )
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=f"From Document Hub Collector, HTTP error {http_code}: {e}",
                    )
                )
                continue
        return ret
