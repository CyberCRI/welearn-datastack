import datetime
import logging
from typing import Any, Dict
from urllib.parse import urlparse
from zlib import adler32

from sentence_transformers import SentenceTransformer  # type: ignore

from welearn_datastack.exceptions import InvalidURLScheme, WrongLangFormat
from welearn_datastack.utils_.scraping_utils import clean_text

logger = logging.getLogger(__name__)


class ScrapedWeLearnDocument:
    loaded_models: dict[str, SentenceTransformer] = {}

    def __init__(
        self,
        document_title: str,
        document_url: str,
        document_lang: str | None,
        document_content: str,
        document_desc: str,
        document_corpus: str,
        document_details: Dict[str, Any],
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
            ("document_lang", document_lang),
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

        # Trivial lang verification
        if len(document_lang) != 2:
            raise WrongLangFormat("Lang must be in ISO-639-1 format: %s", document_lang)

        self.document_title = clean_text(document_title)
        self.document_url = document_url
        self.document_lang = document_lang
        self.document_content = clean_text(document_content)
        self.document_desc = clean_text(document_desc)
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
