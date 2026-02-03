import io
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any

import pydantic
import requests
from PIL.MpegImagePlugin import BitStream
from welearn_database.data.models import WeLearnDocument
from welearn_database.modules.text_cleaning import clean_text

from welearn_datastack import constants
from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.source_models.fao_open_knowledge import (
    BitstreamModel,
    Bundle,
    Item,
    MetadataEntry,
)
from welearn_datastack.exceptions import (
    NoContent,
    NoDescriptionFoundError,
    PDFFileSizeExceedLimit,
    UnauthorizedLicense,
    UnauthorizedState,
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
    def _extract_embargo_status(fao_item: Item) -> bool:
        try:
            md_item = MetadataEntry.model_validate(
                fao_item.metadata.get("fao.embargo", None)
            )
        except pydantic.ValidationError:
            raise ValueError("No embargo status found")

        return md_item.value.lower().strip() != "No"

    @staticmethod
    def _extract_authors(fao_document: Item) -> list[AuthorDetails]:
        ret: list[AuthorDetails] = []
        messy_authors = [
            MetadataEntry.model_validate(a)
            for a in fao_document.metadata.get("dc.contributor.author", [])
        ]
        if not messy_authors:
            logger.warning("No authors found.")
            return ret
        contributors_names: list[str] = []
        for contributor_entry in messy_authors:
            for name in contributor_entry.value.split(";"):
                if name.strip():
                    contributors_names.append(name.strip())

        for contributor in contributors_names:
            ret.append(AuthorDetails(name=contributor, misc=""))
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

        bundle_json = [
            Bundle.model_validate(b) for b in resp.json()["_embedded"]["bundles"]
        ]
        return bundle_json

    def get_bitstream_json(self, bitstream_id: str) -> BitstreamModel:
        session = get_new_https_session()
        bitstream_url = f"{self.api_base_url}core/bundles/{bitstream_id}/bitstreams"
        resp = session.get(url=bitstream_url, headers=self.headers)
        resp.raise_for_status()

        bitstreams: list[BitstreamModel] = [
            BitstreamModel.model_validate(b)
            for b in resp.json()["_embedded"]["bitstreams"]
        ]

        [ret] = bitstreams

        return ret

    @staticmethod
    def _extract_external_sdgs(sdgs_str: list[MetadataEntry]) -> list[int]:
        ret: list[int] = []
        for sdg in sdgs_str:
            sdg_full_title = sdg.value.lower().strip()
            first_ints_isolate = sdg_full_title.split(" ").pop(0).replace(".", "")
            if not first_ints_isolate.isdigit():
                logger.warning(f"SDG value is not digit: {first_ints_isolate}")
                continue
            if first_ints_isolate != "10" and "0" in first_ints_isolate:
                first_ints_isolate = first_ints_isolate.replace("0", "")
            try:
                ret.append(int(first_ints_isolate))
            except ValueError:
                logger.warning(
                    f"SDG value cannot be converted to int: {sdg_full_title}"
                )
                continue
        return ret

    def _extract_details(self, fao_document: Item) -> dict:
        parsed_metadata: defaultdict[str, list[MetadataEntry]] = defaultdict(list)
        for metadata in fao_document.metadata:
            try:
                mds = fao_document.metadata.get(metadata)
                lst_to_extend = [MetadataEntry.model_validate(md) for md in mds]
                parsed_metadata[metadata].extend(lst_to_extend)
            except pydantic.ValidationError as e:
                logger.warning(f"Cannot parse metadata entry: {metadata}: {e}")
                continue
        empty_entry = [
            MetadataEntry(value="", language="", authority=None, confidence=-1, place=0)
        ]
        date_format = "%Y-%m-%dT%H:%M:%SZ"
        [publication_date] = parsed_metadata.get("dc.date.available", empty_entry)
        [update_date] = parsed_metadata.get("dc.date.lastModified", empty_entry)
        [isbn] = parsed_metadata.get("dc.identifier.isbn", empty_entry)
        [doi] = parsed_metadata.get("dc.identifier.doi", empty_entry)
        [type_] = parsed_metadata.get("fao.taxonomy.type", empty_entry)
        ret: dict[str, Any] = {
            "publication_date": (
                None
                if not publication_date.value
                else datetime.strptime(publication_date.value, date_format).timestamp()
            ),
            "update_date": (
                None
                if not update_date.value
                else datetime.strptime(update_date.value, date_format).timestamp()
            ),
            "isbn": isbn.value,
            "license_url": self._extract_licence(fao_document),
            "authors": self._extract_authors(fao_document),
            "external_sdg": self._extract_external_sdgs(
                parsed_metadata.get("fao.sdgs", [])
            ),
            "contrent_from_pdf": True,
            "doi": doi.value,
            "type": type_.value,
        }
        return ret

    @staticmethod
    def extract_bitstream_id(bundles: list[Bundle]) -> str | None:
        for bundle in bundles:
            if bundle.name == "ORIGINAL":
                return bundle.links.bitstreams.href.replace(
                    "https://openknowledge.fao.org/server/api/core/bundles/", ""
                ).replace("/bitstreams", "")
        return None

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        ret: list[WrapperRetrieveDocument] = []
        for document in documents:
            try:
                fao_ok_metadata = self.get_metadata_json(document)
                self._check_licence_authorization(
                    self._extract_licence(fao_ok_metadata)
                )
                if fao_ok_metadata.withdrawn:
                    raise UnauthorizedState("Document is withdrawn from source.")
                is_under_fao_embargo: bool

                try:
                    is_under_fao_embargo = self._extract_embargo_status(fao_ok_metadata)
                except ValueError:
                    is_under_fao_embargo = False

                if is_under_fao_embargo:
                    raise UnauthorizedState(
                        f"Document {document.url} is under fao embargo."
                    )

                bundle_json = self.get_bundle_json(document)
                bitstream_id = self.extract_bitstream_id(bundle_json)
                bitstream = self.get_bitstream_json(bitstream_id)
                pdf_url = bitstream.links.content.href
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
                document.details = self._extract_details(fao_ok_metadata)

            except UnauthorizedLicense as e:
                logger.warning(
                    f"Document {document.url} skipped due to unauthorized license: {e}"
                )
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=f"From Document Hub Collector, unauthorized license: {e}",
                        http_error_code=403,
                    )
                )
                continue
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
            except UnauthorizedState as e:
                logger.warning(
                    f"Document {document.url} skipped due to unauthorized state: {e}"
                )
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=f"From Document Hub Collector, unauthorized state: {e}",
                        http_error_code=403,
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
                        http_error_code=http_code,
                    )
                )
                continue

            ret.append(WrapperRetrieveDocument(document=document))
        return ret
