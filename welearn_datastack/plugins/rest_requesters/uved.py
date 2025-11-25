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

from welearn_datastack import constants
from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.source_models.oapen import Metadatum, OapenModel
from welearn_datastack.data.source_models.uved import Category, UVEDMemberItem
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
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)
from welearn_datastack.utils_.scraping_utils import remove_extra_whitespace

logger = logging.getLogger(__name__)


# Collector
class UVEDCollector(IPluginRESTCollector):
    related_corpus = "uved"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")

        self.api_base_url = "https://www.uved.fr/api/V1"
        self.application_base_url = "https://www.uved.fr/ressource/"
        self.headers = constants.HEADERS

    def _get_pdf_content(self, url: str) -> str:
        pass

    def _clean_txt_content(self, url: str) -> str:
        pass

    def _extract_licence(self, uved_document: UVEDMemberItem) -> str:
        pass

    def _extract_metadata(self, uved_document: UVEDMemberItem) -> Dict:
        pass

    def _extract_external_sdg_id(
        self, uved_metadata_categorization: list[Category]
    ) -> str:
        pass

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        pass
