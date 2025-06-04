import datetime
import logging
from collections import deque
from typing import Any, Dict
from urllib.parse import urlparse
from zlib import adler32

from lingua import IsoCode639_1, Language
from sentence_transformers import SentenceTransformer  # type: ignore

from welearn_datastack.exceptions import InvalidURLScheme, WrongLangFormat
from welearn_datastack.utils_.scraping_utils import clean_text
from welearn_datastack.utils_.text_stat_utils import (
    _get_language_detector,
    predict_duration,
    predict_readability,
)

logger = logging.getLogger(__name__)


class ScrapedWeLearnDocument:
    loaded_models: dict[str, SentenceTransformer] = {}

    def __init__(
        self,
        document_title: str,
        document_url: str,
        document_content: str,
        document_desc: str,
        document_corpus: str,
        document_details: Dict[str, Any],
        document_lang: str | None = None,
        document_is_sdg: bool | None = None,
        document_scrape_date: datetime.datetime | None = None,
    ):
        # Trivial URL validation
        parsed_url = urlparse(url=document_url)
        accepted_scheme = ["https", "http"]
        if parsed_url.scheme not in accepted_scheme or len(parsed_url.netloc) == 0:
            raise InvalidURLScheme(
                "There is an error on the URL form : %s", document_url
            )

        for checked_value in [
            ("document_title", document_title),
            ("document_url", document_url),
            ("document_content", document_content),
            ("document_desc", document_desc),
            ("document_corpus", document_corpus),
        ]:
            if checked_value[1] is None or checked_value[1] == "":
                raise ValueError(
                    f"One of the required field is empty : {checked_value[0]}"
                )

        if len(document_content) < 25:
            raise ValueError(f"Content is too short : {len(document_content)}")

        content = clean_text(document_content)
        desc = clean_text(document_desc)

        # Detecting language
        content_and_description_different_language: bool | None = None
        desc_lang: str | None = None
        if not document_lang:
            lang_detector = _get_language_detector()
            confidence_values_content = deque(
                lang_detector.compute_language_confidence_values(content)
            )
            confidence_values_desc = deque(
                lang_detector.compute_language_confidence_values(desc)
            )
            document_lang = (
                confidence_values_content.popleft().language.iso_code_639_1.name.lower()
            )
            desc_lang = (
                confidence_values_desc.popleft().language.iso_code_639_1.name.lower()
            )
            content_and_description_different_language = document_lang != desc_lang
            if content_and_description_different_language:
                logger.warning(
                    f"Content and description languages are different: {document_lang} vs {desc_lang}"
                )
        else:
            logger.warning(
                f"Be aware, for the document from {document_url} language is from metadata"
            )
            try:
                document_lang = Language.from_iso_code_639_1(
                    IsoCode639_1(document_lang)
                ).iso_code_639_1.name.lower()
            except ValueError:
                raise WrongLangFormat(
                    "Lang must be in ISO-639-1 format: %s", document_lang
                )

        if not document_lang:
            raise ValueError(f"There is no lang for this document : {document_url}")

        document_details["content_and_description_lang"] = {
            "are_different": content_and_description_different_language,
            "description_lang": desc_lang,
            "content_lang": document_lang,
        }

        # Get readability and duration
        if "readability" not in document_details:
            readability = predict_readability(text=content, lang=document_lang)
            document_details["readability"] = str(readability)

        if "duration" not in document_details:
            duration = predict_duration(text=content, lang=document_lang)
            document_details["duration"] = str(duration)

        self.document_title = clean_text(document_title)
        self.document_url = document_url
        self.document_lang = document_lang
        self.document_content = content
        self.document_desc = desc
        self.document_corpus = document_corpus
        self.document_details = document_details
        self.document_is_sdg: bool | None = document_is_sdg
        if document_scrape_date:
            self._scrape_date = document_scrape_date
        else:
            self._scrape_date = datetime.datetime.now()

    @property
    def trace(self):
        return adler32(bytes(self.document_content, "utf-8"))

    @property
    def document_scrape_date(self):
        return self._scrape_date

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "document_title": self.document_title,
            "document_url": self.document_url,
            "document_lang": self.document_lang,
            "document_content": self.document_content,
            "document_desc": self.document_desc,
            "document_corpus": self.document_corpus,
            "document_details": self.document_details,
            "document_is_sdg": self.document_is_sdg,
            "document_scrape_date": self._scrape_date.timestamp(),
        }
        return res
