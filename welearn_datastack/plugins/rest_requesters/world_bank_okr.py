import io
import json
import logging
import math
import os
import re
import time
from collections import deque
from datetime import datetime
from itertools import batched
from typing import Dict, Iterable, List

from lingua import Language
from requests import Session
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.details_dataclass.topics import TopicDetails
from welearn_datastack.data.source_models.oapen import Metadatum, OapenModel
from welearn_datastack.data.source_models.world_bank_okr import WorldBankOKRRecord
from welearn_datastack.exceptions import (
    NoDescriptionFoundError,
    TooMuchLanguages,
    UnauthorizedLicense,
    WrongLangFormat,
)
from welearn_datastack.modules.computed_metadata import get_language_detector
from welearn_datastack.modules.pdf_extractor import (
    delete_accents,
    delete_non_printable_character,
    extract_txt_from_pdf_with_tika,
    get_pdf_content,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.regular_expression import (
    BLANK_CHARACTERS_SEQUENCE_REGEX,
    SOFT_LINE_BREAK_REGEX,
    WORD_CUT_BY_BACKLINES_REGEX,
)
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import (
    format_cc_license,
    remove_extra_whitespace,
)

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

    def _retrieve_records_from_oai(
        self, documents: list[WeLearnDocument]
    ) -> list[WrapperRawData]:
        client = get_new_https_session()
        ret = []
        for doc in documents:
            try:
                ret.append(
                    WrapperRawData(
                        document=doc,
                        raw_data=self._retrieve_record_from_oai(
                            doc.external_id, client
                        ),
                    )
                )
            except Exception as e:
                logger.error(
                    "Error while retrieving record with oai_id %s: %s",
                    doc.external_id,
                    str(e),
                )
        return ret

    @staticmethod
    def _process_authors(authors_str: list[str]) -> list[AuthorDetails]:
        ret = []
        for author in authors_str:
            first_name = remove_extra_whitespace(author.split()[1])
            last_name = remove_extra_whitespace(author.split()[0])
            ret.append(AuthorDetails(name=f"{first_name} {last_name}", misc=""))
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
        }

        return details

    def _update_welearn_document(self, wrapper: WrapperRawData) -> WeLearnDocument:
        licence = self._extract_licence(wrapper.raw_data)
        if licence not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(
                f"License {licence} is not in the list of authorized licenses"
            )

        doc = wrapper.document
        doc.title = wrapper.raw_data.title
        doc.doi = wrapper.raw_data.identifiers.doi
        doc.description = wrapper.raw_data.abstract

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running WorldBankOKR plugin")
        ret: List[WrapperRetrieveDocument] = []

        for document in documents:
            pass
