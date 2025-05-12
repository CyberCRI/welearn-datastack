import io
import logging
import math
import os
import re
from datetime import datetime
from itertools import batched
from typing import Dict, Iterable, List, Tuple

from langdetect import detect
from pypdf import PdfReader

from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import (
    NoDescriptionFoundError,
    PDFPagesSizeExceedLimit,
    TooMuchLanguages,
    UnauthorizedLicense,
)
from welearn_datastack.modules.pdf_extractor import (
    delete_accents,
    delete_non_printable_character,
    extract_txt_from_pdf,
    large_pages_size_flag,
    remove_hyphens,
    replace_ligatures,
)
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import remove_extra_whitespace
from welearn_datastack.utils_.text_stat_utils import (
    predict_duration,
    predict_readability,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://library.oapen.org/"


language_to_iso_2_dict = {
    "English": "en",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Italian": "it",
    "Dutch": "nl",
    "Portuguese": "pt",
    "Russian": "ru",
    "Polish": "pl",
    "Czech": "cs",
    "Hungarian": "hu",
    "Romanian": "ro",
    "Slovak": "sk",
}


# Collector
class OAPenCollector(IPluginRESTCollector):
    related_corpus = "oapen"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))

    @staticmethod
    def _extract_oapen_ids(urls: Iterable[str]) -> List[str]:
        start_line = BASE_URL + "handle/"
        ret = [url.replace(start_line, "") for url in urls]
        return ret

    @staticmethod
    def _get_oapen_url_from_handle_id(handle_id: str) -> str:
        return f"{BASE_URL}handle/{handle_id}"

    def _get_pdf_content(self, url: str) -> str:
        logger.info("Getting PDF content from %s", url)
        client = get_new_https_session()
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()

        pdf_file = io.BytesIO(response.content)

        reader = PdfReader(pdf_file)
        sizes, size_flag = large_pages_size_flag(
            reader=reader, limit=self.pdf_size_page_limit
        )

        if size_flag:
            raise PDFPagesSizeExceedLimit()
        pdf_content = extract_txt_from_pdf(reader=reader)

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

    @staticmethod
    def clean_backline(text):
        # "Lin-\nguistique" → "Linguistique"
        text = re.sub(r"-\s*\n\s*", "", text)

        # Merge lines who must be
        text = re.sub(r"(?<![\.\:\?\!])\s*\n\s*", " ", text)

        # Delete other backlines
        text = text.replace("\n", " ")

        # Delete double spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _get_txt_content(self, url: str) -> str:
        logger.info("Getting TXT content from %s", url)
        client = get_new_https_session()
        headers = HEADERS.copy()
        headers["Accept"] = "application/json"
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()

        ret = response.text.encode(response.encoding).decode("utf-8", "ignore")
        ret = self.clean_backline(ret)
        ret = delete_non_printable_character(ret)
        return ret

    @staticmethod
    def _get_jsons(oapen_ids: List[str]) -> List[dict]:
        ret = []

        list_pre_formatted = [f'handle:"{oapen_id}"' for oapen_id in oapen_ids]
        query = " OR ".join(list_pre_formatted)
        url = f"{BASE_URL}rest/search?query={query}&expand=bitstreams,metadata"
        session = get_new_https_session()
        resp = session.get(url)

        resp.raise_for_status()
        json_resp = resp.json()

        for book in json_resp:
            ret.append(book)
        return ret

    @staticmethod
    def _format_metadata(
        metadata: List[Dict[str, str | None]]
    ) -> Dict[str, str | List[str]]:
        ret: Dict = {}
        for i in metadata:
            key = i["key"]
            value = i["value"]

            if key in ret:
                if isinstance(ret[key], list):
                    ret[key].append(value)
                else:
                    ret[key] = [ret[key], value]
            else:
                ret[key] = value

        return ret

    def _convert_json_dict_to_welearndoc(
        self, json_dict: dict
    ) -> ScrapedWeLearnDocument:
        title = json_dict["name"]
        url = self._get_oapen_url_from_handle_id(json_dict["handle"])

        bitstreams = json_dict["bitstreams"]
        content_link = ""
        is_txt = False
        well_formated_license = ""
        for bitstream in bitstreams:
            if bitstream["bundleName"].lower() == "original":
                if not is_txt:
                    content_link = bitstream["retrieveLink"]
                doc_license = (
                    bitstream["code"].lower().replace("cc-", "")
                )  # CC-BY-4.0 -> by-4.0
                well_formated_license = (
                    f"https://creativecommons.org/licenses/{doc_license}/4.0/"
                )

            elif bitstream["bundleName"].lower() == "text":
                # Remove the last '/' of base_url for avoid stupid error
                content_link = BASE_URL[:-1] + bitstream["retrieveLink"]
                is_txt = True

        if well_formated_license not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(
                f"License {well_formated_license} is not authorized"
            )
        logger.info(f"Document at {url} is legally usable")

        if is_txt:
            content = self._get_txt_content(content_link)
        else:
            content = self._get_pdf_content(content_link)

        metadata = self._format_metadata(json_dict["metadata"])

        if isinstance(metadata["dc.language"], str):
            lang = language_to_iso_2_dict.get(metadata["dc.language"], "00")
        else:
            raise TooMuchLanguages("Too much languages in metadata")

        abstracts: List[str] = []
        if "dc.description.abstract" in metadata and isinstance(
            metadata.get("dc.description.abstract"), str
        ):
            abstracts.append(metadata.get("dc.description.abstract"))  # type: ignore

        if "oapen.abstract.otherlanguage" in metadata and isinstance(
            metadata.get("oapen.abstract.otherlanguage"), str
        ):
            abstracts.append(metadata["oapen.abstract.otherlanguage"])  # type: ignore

        if "oapen.abstract.otherlanguage" in metadata and isinstance(
            metadata.get("oapen.abstract.otherlanguage"), list  # type: ignore
        ):
            abstracts.extend(metadata["oapen.abstract.otherlanguage"])
        if len(abstracts) <= 0:
            raise NoDescriptionFoundError("No description found in this document")

        desc = ""
        for abstract in abstracts:
            detected_lang = detect(abstract)
            if detected_lang == lang:
                desc = abstract
                break

        if desc == "":
            raise NoDescriptionFoundError("No description found in this document")

        # Mypy verification
        if not isinstance(desc, str):
            raise NoDescriptionFoundError("No description found in this document")

        publisher = metadata.get("publisher.name", "")
        type_ = metadata.get("dc.type", "")
        isbn = metadata.get("dc.identifier.isbn", "")

        if "dc.date.available" in metadata and isinstance(
            metadata["dc.date.available"], str
        ):
            publication_date = datetime.strptime(
                metadata["dc.date.available"], "%Y-%m-%dT%H:%M:%SZ"
            ).timestamp()
        else:
            publication_date = None

        if "dc.identifier.uri" in metadata and isinstance(
            metadata["dc.identifier.uri"], str
        ):
            doi = metadata["dc.identifier.uri"].replace(BASE_URL + "handle/", "")
        else:
            doi = ""

        authors = []
        if "dc.contributor.author" in metadata:
            metadata_authors = metadata["dc.contributor.author"]
            if isinstance(metadata_authors, str):
                # This is for avoid type divergence after this point
                metadata_authors = [metadata_authors]

            for author in metadata_authors:
                splitted_name = author.split(", ")
                name = f"{splitted_name[1]} {splitted_name[0]}"
                authors.append({"name": name, "misc": ""})

        editors = []
        if "dc.contributor.editor" in metadata:
            for editor in metadata["dc.contributor.editor"]:
                name = f"{editor.split(', ')[1]} {editor.split(', ')[0]}"
                editors.append({"name": name, "misc": ""})

        # Multiple classification can exist in the metadata, wtf
        if "dc.subject.classification" in metadata:
            classification = metadata["dc.subject.classification"]
            if isinstance(classification, str):
                classification = [classification]
        else:
            classification = []

        # Retrieve tags, could be multiple, who knows, there is no documentation
        if "dc.subject.other" in metadata:
            tags = metadata["dc.subject.other"]
            if isinstance(tags, str):
                tags = tags.lower().split(";")
            elif isinstance(tags, list):
                tmp_tags = []
                for tag in tags:
                    tmp_tags.extend(tag.lower().split(";"))
                tags = tmp_tags
        else:
            tags = []
        # Predicted properties
        duration = predict_duration(text=content, lang=lang)
        readability = predict_readability(text=content, lang=lang)

        document_details = {
            "publisher": publisher,
            "doi": doi,
            "type": type_,
            "isbn": isbn,
            "publication_date": publication_date,
            "authors": authors,
            "editors": editors,
            "license": well_formated_license,
            "classification": classification,
            "tags": tags,
            "content_from_pdf": not is_txt,
            "content_from_txt": is_txt,
            "duration": duration,
            "readability": readability,
        }

        return ScrapedWeLearnDocument(
            document_title=title,
            document_url=url,
            document_lang=lang,
            document_content=content,
            document_desc=desc,
            document_corpus=self.corpus_name,
            document_details=document_details,
        )

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        logger.info("Running OAPenCollector plugin")
        ret: List[ScrapedWeLearnDocument] = []
        error_docs: List[str] = []
        resp_from_oapen: List[dict] = []

        logger.info("Start getting JSON from API")
        sub_batch_qty = 100
        logger.info(f"We gonna iterate {math.ceil(len(urls)/sub_batch_qty)} times")
        for i, local_url_batch in enumerate(batched(urls, sub_batch_qty)):
            logger.info(f"Sub batch {i+1}/{math.ceil(len(urls)/sub_batch_qty)}")
            try:
                oapen_ids = self._extract_oapen_ids(local_url_batch)
                resp_from_oapen.extend(self._get_jsons(oapen_ids))
            except Exception as e:
                logger.error("Error while getting JSON from OApen API")
                logger.error(e)
                for url in local_url_batch:
                    error_docs.append(url)
        logger.info(f"We retrieve {len(resp_from_oapen)} json")
        logger.info("Process JSON")
        for doc in resp_from_oapen:
            try:
                ret.append(self._convert_json_dict_to_welearndoc(doc))
            except Exception as e:
                logger.exception(
                    "Error while trying to get contents for url,\n url: '%s' \nError: %s",
                    self._get_oapen_url_from_handle_id(doc["handle"]),
                    e,
                )
                error_docs.append(self._get_oapen_url_from_handle_id(doc["handle"]))
                continue
        logger.info(
            "OAPenCollector plugin finished, %s urls successfully processed",
            len(ret),
        )
        return ret, error_docs
