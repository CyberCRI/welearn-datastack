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
from welearn_database.modules.text_cleaning import clean_text

from welearn_datastack import constants
from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.source_models.oapen import Metadatum, OapenModel
from welearn_datastack.data.source_models.uved import Category, UVEDMemberItem
from welearn_datastack.exceptions import (
    NoDescriptionFoundError,
    PDFFileSizeExceedLimit,
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

    def _extract_licence(self, uved_document: UVEDMemberItem) -> str:
        licence = None
        cats = uved_document.categories
        license_equivalence_uved_cc = {
            8: "by",  # Attribution
            6: "sa",  # ShareAlike
            13: "nd",  # NoDerivatives
            9: "nc",  # NonCommercial
        }
        licence_flag_cc: list[str] = []
        for cat in cats:
            if (
                cat.uid in license_equivalence_uved_cc.keys()
            ):  # Authorized licenses uids
                licence_flag_cc.append(license_equivalence_uved_cc[cat.uid])
        if "nd" in licence_flag_cc and "sa" in licence_flag_cc:
            licence_flag_cc.remove(
                "sa"
            )  # ND and SA are incompatible, ND takes precedence
        if licence_flag_cc:
            licence = "CC " + "-".join(sorted(licence_flag_cc)) + " 4.0"
        return licence

    def _extract_metadata(self, uved_document: UVEDMemberItem) -> Dict:
        pass

    def _extract_external_sdg_id(
        self, uved_metadata_categorization: list[Category]
    ) -> str:
        pass

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        pass
