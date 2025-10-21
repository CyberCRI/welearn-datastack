import io
import json
import logging
import math
import os
import re
from collections import deque
from datetime import datetime
from itertools import batched
from typing import Dict, Iterable, List, Tuple

from lingua import Language
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.data.source_models.oapen import Metadatum, OapenModel
from welearn_datastack.exceptions import (
    NoDescriptionFoundError,
    TooMuchLanguages,
    UnauthorizedLicense,
    WrongLangFormat,
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
from welearn_datastack.utils_.scraping_utils import remove_extra_whitespace
from welearn_datastack.utils_.text_stat_utils import get_language_detector

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
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")

    @staticmethod
    def _extract_oapen_ids(
        documents: Iterable[WeLearnDocument],
    ) -> dict[str, WeLearnDocument]:
        start_line = BASE_URL + "handle/"
        ret = {d.url.replace(start_line, ""): d for d in documents}
        return ret

    @staticmethod
    def _get_oapen_url_from_handle_id(handle_id: str) -> str:
        return f"{BASE_URL}handle/{handle_id}"

    def _get_pdf_content(self, url: str) -> str:
        logger.info("Getting PDF content from %s", url)
        client = get_new_https_session()
        response = client.get(url, headers=HEADERS)
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
    def _get_jsons(oapen_documents: list[WeLearnDocument]) -> list[WrapperRawData]:
        ret = []

        oapen_docs_ext_ids = OAPenCollector._extract_oapen_ids(oapen_documents)
        list_pre_formatted = [
            f'handle:"{oapen_id}"' for oapen_id in oapen_docs_ext_ids.keys()
        ]
        query = " OR ".join(list_pre_formatted)
        url = f"{BASE_URL}rest/search?query={query}&expand=bitstreams,metadata"
        session = get_new_https_session()
        resp = session.get(url)

        resp.raise_for_status()
        json_resp = resp.json()

        for i in json_resp:
            raw_data = OapenModel.model_validate_json(json.dumps(i))
            ret.append(
                WrapperRawData(
                    raw_data=raw_data,
                    document=oapen_docs_ext_ids[raw_data.handle],
                )
            )
        return ret

    @staticmethod
    def _format_metadata(
        metadata: list[Metadatum],
    ) -> Dict[str, str | List[str]]:
        ret: Dict = {}
        for i in metadata:
            key = i.key
            value = i.value

            if key in ret:
                if isinstance(ret[key], list):
                    ret[key].append(value)
                else:
                    ret[key] = [ret[key], value]
            else:
                ret[key] = value

        return ret

    def _update_welearn_document(self, wrapper: WrapperRawData) -> WeLearnDocument:
        title = wrapper.raw_data.name
        url = self._get_oapen_url_from_handle_id(wrapper.raw_data.handle)

        bitstreams = wrapper.raw_data.bitstreams
        content_link = ""
        is_txt = False
        well_formated_license = ""
        for bitstream in bitstreams:
            if bitstream.bundleName.lower() == "original":
                if not is_txt:
                    content_link = bitstream.retrieveLink
                doc_license = bitstream.code.lower().replace(
                    "cc-", ""
                )  # CC-BY-4.0 -> by-4.0
                well_formated_license = (
                    f"https://creativecommons.org/licenses/{doc_license}/4.0/"
                )

            elif bitstream.bundleName.lower() == "text":
                # Remove the last '/' of base_url for avoid stupid error
                content_link = BASE_URL[:-1] + bitstream.retrieveLink
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

        metadata = self._format_metadata(wrapper.raw_data.metadata)

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

        # Identify which abstract to collect
        desc = ""
        if isinstance(metadata["dc.language"], str):
            try:
                lang = Language.from_str(
                    metadata["dc.language"]
                ).iso_code_639_1.name.lower()
            except ValueError:
                raise WrongLangFormat(
                    f"This language cannot be handled : {metadata['dc.language']}"
                )
        else:
            raise TooMuchLanguages("Too much languages in metadata")

        lang_detector = get_language_detector()
        for abstract in abstracts:
            confidence_values_desc = deque(
                lang_detector.compute_language_confidence_values(abstract)
            )
            detected_lang = (
                confidence_values_desc.popleft().language.iso_code_639_1.name.lower()
            )
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
        }

        wrapper.document.title = title
        wrapper.document.url = url
        wrapper.document.lang = lang
        wrapper.document.content = content
        wrapper.document.description = desc
        wrapper.document.details = document_details

        return wrapper.document

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running OAPenCollector plugin")
        ret: List[WrapperRetrieveDocument] = []
        resp_from_oapen: list[WrapperRawData] = []

        logger.info("Start getting JSON from API")
        sub_batch_qty = 100
        logger.info(
            f"We gonna iterate {math.ceil(len(documents) / sub_batch_qty)} times"
        )
        for i, local_doc_batch in enumerate(batched(documents, sub_batch_qty)):
            logger.info(f"Sub batch {i+1}/{math.ceil(len(documents) / sub_batch_qty)}")
            try:
                resp_from_oapen.extend(self._get_jsons(documents))
            except Exception as e:
                logger.error("Error while getting JSON from OApen API")
                logger.error(e)
                for wl_doc in local_doc_batch:
                    logger.error(f"Failed URL: {wl_doc.url}, id: {wl_doc.id}")
                    http_error_code = get_http_code_from_exception(e)
                    ret.append(
                        WrapperRetrieveDocument(
                            document=wl_doc,
                            http_error_code=http_error_code,
                            error_info=str(e),
                        )
                    )
        logger.info(f"We retrieve {len(resp_from_oapen)} json")
        logger.info("Process JSON")

        for doc in resp_from_oapen:
            try:
                ret.append(
                    WrapperRetrieveDocument(document=self._update_welearn_document(doc))
                )
            except Exception as e:
                logger.exception(f"Error while processing document {doc.document.url}")
                ret.append(
                    WrapperRetrieveDocument(
                        document=doc.document,
                        error_info=str(e),
                    )
                )
                continue
        logger.info(
            "OAPenCollector plugin finished, %s urls successfully processed",
            len(ret),
        )
        return ret
