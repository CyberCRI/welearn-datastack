import io
import logging
import os
import re
import time
from datetime import datetime
from typing import List

import pydantic
import requests
from requests import Session
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.details_dataclass.topics import TopicDetails
from welearn_datastack.data.source_models.world_bank_okr import WorldBankOKRRecord
from welearn_datastack.exceptions import (
    FileTypeUnsupported,
    LegalException,
    NoContent,
    UnauthorizedLicense,
)
from welearn_datastack.modules.pdf_extractor import (
    delete_accents,
    delete_non_printable_character,
    extract_txt_from_pdf_with_tika,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import remove_extra_whitespace

logger = logging.getLogger(__name__)


class WorldBankOpenKnowledgeRepository(IPluginRESTCollector):
    related_corpus = "world-bank-open-knowledge-repository"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")
        self.api_base_url = "https://openknowledge.worldbank.org/server/oai/request"
        self.application_base_url = "https://openknowledge.worldbank.org/handle/"
        self.oai_metadata_prefix = "xoai"
        self.headers = HEADERS

    def _retrieve_record_from_oai(
        self, oai_id: str, client: Session
    ) -> WorldBankOKRRecord:
        params = {
            "verb": "GetRecord",
            "identifier": oai_id,
            "metadataPrefix": self.oai_metadata_prefix,
        }
        okr_resp = client.get(self.api_base_url, params=params, headers=self.headers)
        okr_resp.raise_for_status()

        return WorldBankOKRRecord.model_validate(XMLExtractor(okr_resp.text))

    @staticmethod
    def _process_authors(authors_str: list[str]) -> list[AuthorDetails]:
        ret = []
        for author in authors_str:
            first_name = remove_extra_whitespace(author.split()[1])
            last_name = remove_extra_whitespace(author.split()[0])
            name = f"{first_name} {last_name}"
            name = name.replace(",", "")
            ret.append(AuthorDetails(name=name, misc=""))
        return ret

    @staticmethod
    def _extract_licence(record: WorldBankOKRRecord) -> str:
        messy_licence = record.accessCondition.lower()
        s = messy_licence.strip().lower()

        match = re.match(r"cc\s+([a-z\-]+)\s+(\d+(?:\.\d+)?)\s*(igo)?", s)
        if not match:
            return s

        license_code, version, igo = match.groups()

        if igo:
            return f"https://creativecommons.org/licenses/{license_code}/{version}/igo/"

        return f"https://creativecommons.org/licenses/{license_code}/{version}/"

    def _build_details(
        self, raw_data: WorldBankOKRRecord
    ) -> dict[str, list[AuthorDetails] | list[TopicDetails] | str | int]:
        publication_date = None
        if raw_data.dates.dateAvailable:
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            publication_date = time.mktime(
                datetime.strptime(raw_data.dates.dateAvailable, fmt).timetuple()
            )
        authors = self._process_authors(raw_data.authors)
        topics = [
            TopicDetails(
                name=subject.lower(),
                depth=0,
                directly_contained_in=[],
                external_id=None,
                external_depth_name=None,
            )
            for subject in raw_data.subjects
        ]
        details = {
            "authors": authors,
            "topics": topics,
            "publication_date": publication_date,
            "doi": raw_data.identifiers.doi,
        }

        return details

    def _extract_full_content(self, record: WorldBankOKRRecord) -> tuple[str, bool]:
        if len(record.fileGrp) == 0:
            raise NoContent("No file group found in the record")

        txt_address = None
        pdf_address = None
        unsupported_file_type_flag = False

        for grp in record.fileGrp:
            if grp.mimetype == "application/pdf":
                pdf_address = grp.flocat.href
            elif grp.mimetype == "text/plain":
                txt_address = grp.flocat.href
            else:
                unsupported_file_type_flag = True

        if unsupported_file_type_flag and not (txt_address and pdf_address):
            raise FileTypeUnsupported(
                f"No supported file type found in the record: {record.identifiers.uri}"
            )

        is_txt = False

        # TXT will be used as fallback because it's more difficult to clean
        if pdf_address:
            logger.info("Getting PDF content from %s", pdf_address)
            client = get_new_https_session(retry_total=0)
            response = client.get(pdf_address, headers=HEADERS, timeout=300)
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
        elif txt_address:
            is_txt = True
            logger.info("Getting TXT content from %s", txt_address)
            client = get_new_https_session(retry_total=0)
            response = client.get(txt_address, headers=HEADERS, timeout=300)
            ret = response.text
        else:
            raise NoContent("Can't find content address for this document")
        return ret, is_txt

    def _update_welearn_document(self, wrapper: WrapperRawData) -> WeLearnDocument:
        """
        Update the WeLearnDocument with the data from the WorldBankOKRRecord.
        """
        licence = self._extract_licence(wrapper.raw_data)
        if licence not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(
                f"License {licence} is not in the list of authorized licenses"
            )

        doc = wrapper.document
        doc.title = wrapper.raw_data.title
        doc.doi = wrapper.raw_data.identifiers.doi
        doc.description = wrapper.raw_data.abstract
        full_content, is_txt = self._extract_full_content(wrapper.raw_data)
        doc.full_content = full_content
        details = self._build_details(wrapper.raw_data)
        details.update(
            {
                "content_from_pdf": not is_txt,
                "content_from_txt": is_txt,
                "licence": licence,
            }
        )
        doc.details = details
        return doc

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running WorldBankOKR plugin")
        ret: List[WrapperRetrieveDocument] = []

        client = get_new_https_session()
        for doc in documents:
            try:
                ret_doc = WrapperRawData(
                    document=doc,
                    raw_data=self._retrieve_record_from_oai(doc.external_id, client),
                )
            except requests.exceptions.RequestException as e:
                msg = f"Error while retrieving World bank OKR document ({doc.url}) document from this url {self.api_base_url}/?verb=GetRecord&identifier={doc.external_id}: {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=doc,
                        http_error_code=get_http_code_from_exception(e),
                        error_info=msg,
                    )
                )
                continue
            except pydantic.ValidationError as e:
                msg = f"Error while validating World bank OKR document ({doc.url}) document from this url {self.api_base_url}/?verb=GetRecord&identifier={doc.external_id}: {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=doc,
                        error_info=msg,
                    )
                )
                continue

            try:
                doc = WrapperRetrieveDocument(
                    document=self._update_welearn_document(ret_doc),
                )
            except LegalException as e:
                msg = f"Legal exception for document {doc.url} from world bank OKR: {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=doc,
                        error_info=msg,
                    )
                )
                continue
            except requests.exceptions.RequestException as e:
                msg = f"Error while retrieving World bank OKR content ({ret_doc.document.url}) document from this url {self.api_base_url}/?verb=GetRecord&identifier={ret_doc.document.external_id}: {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=ret_doc.document,
                        http_error_code=get_http_code_from_exception(e),
                        error_info=msg,
                    )
                )
                continue
            except NoContent as e:
                msg = f"No content found for document {ret_doc.document.url}: {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=ret_doc.document,
                        error_info=msg,
                    )
                )
                continue
            except FileTypeUnsupported as e:
                msg = f"FileTypeUnsupported exception for document {ret_doc.document.url}: {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=ret_doc.document,
                        error_info=msg,
                    )
                )
                continue
            ret.append(doc)

        return ret
