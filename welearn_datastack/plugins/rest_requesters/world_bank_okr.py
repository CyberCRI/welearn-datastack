import io
import json
import logging
import math
import os
import re
from collections import deque
from datetime import datetime
from itertools import batched
from typing import Dict, Iterable, List

from lingua import Language
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.source_models.oapen import Metadatum, OapenModel
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

    def _retrieve_record_from_oai(self, oai_id: str) -> XMLExtractor:
        client = get_new_https_session()
        params = {
            "verb": "GetRecord",
            "identifier": oai_id,
            "metadataPrefix": self.oai_metadata_prefix,
        }
        okr_resp = client.get(self.api_base_url, params=params, headers=self.headers)
        okr_resp.raise_for_status()

        return XMLExtractor(okr_resp.content)

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running WorldBankOKR plugin")
        ret: List[WrapperRetrieveDocument] = []

        for document in documents:
            pass
