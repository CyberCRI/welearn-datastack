import io
import logging
import os
from dataclasses import asdict
from datetime import datetime

import pydantic
import requests
from welearn_database.data.models import Category, WeLearnDocument
from welearn_database.modules.text_cleaning import clean_text

from welearn_datastack import constants
from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.details_dataclass.scholar_fields import ScholarFieldsDetails
from welearn_datastack.data.details_dataclass.scholar_institution_type import (
    InstitutionTypeName,
    ScholarInstitutionTypeDetails,
)
from welearn_datastack.data.details_dataclass.scholar_level import ScholarLevelDetails
from welearn_datastack.data.details_dataclass.topics import TopicDetails
from welearn_datastack.data.source_models.unesdoc import (
    UNESDOCItem,
    UNESDOCRoot,
    UNESDOCSources,
)
from welearn_datastack.exceptions import (
    NoContent,
    NoDescriptionFoundError,
    NoLicenseFoundError,
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
from welearn_datastack.modules.xml_extractor import XMLExtractor
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


translations = {
    "eng": "See the full text for more details.",
    "deu": "Lesen Sie den vollständigen Text für weitere Details.",
    "spa": "Consulte el texto completo para más detalles.",
    "fra": "Consultez le texte intégral pour plus de détails.",
    "jpn": "詳細については全文をご参照ください。",
    "por": "Consulte o texto completo para mais detalhes.",
    "ara": "لمزيد من التفاصيل يرجى الرجوع إلى النص الكامل",
    "ces": "Podrobnosti naleznete v plném znění textu.",
    "ita": "Consulti il testo completo per maggiori dettagli.",
    "kor": "자세한 내용은 전체 본문을 확인하세요.",
    "nld": "Raadpleeg de volledige tekst voor meer details.",
    "zho": "更多详情请参阅全文。",
}

lang_iso3_to_lang_iso2 = {
    "eng": "en",
    "deu": "de",
    "spa": "es",
    "fra": "fr",
    "jpn": "ja",
    "por": "pt",
    "ara": "ar",
    "ces": "cs",
    "ita": "it",
    "kor": "ko",
    "nld": "nl",
    "zho": "zh",
}


# Collector
class UNESDOCCollector(IPluginRESTCollector):
    related_corpus = "unesdoc"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.pdf_size_page_limit: int = int(os.getenv("PDF_SIZE_PAGE_LIMIT", 100000))
        self.tika_address = os.getenv("TIKA_ADDRESS", "http://localhost:9998")

        self.api_base_url = (
            "https://data.unesco.org/api/explore/v2.1/catalog/datasets/doc001"
        )
        self.application_base_url = "https://unesdoc.unesco.org/ark:/"
        self.headers = constants.HEADERS
        self.pdf_size_file_limit: int = int(os.getenv("PDF_SIZE_FILE_LIMIT", 2000000))

    def _get_pdf_content(self, url: str) -> str:
        """
        Get the content of a PDF file from a given URL, using the Tika API to extract the text content.
         The function first checks the size of the PDF file using a HEAD request, and raises a PDFFileSizeExceedLimit exception if the file size exceeds the limit defined in the environment variable PDF_SIZE_FILE_LIMIT.
         If the file size is within the limit, it makes a GET request to retrieve the PDF file, and then uses the Tika API to extract the text content from the PDF file.
         The extracted text content is then cleaned by removing non-printable characters, replacing ligatures, removing hyphens and accents, and removing extra whitespace.
         Finally, the cleaned text content is returned as a string.
         :param url: The URL of the PDF file to retrieve and extract content from.
         :return: The cleaned text content extracted from the PDF file.
         :raises ValueError: If the file size cannot be retrieved or if it exceeds the defined limit.
         :raises requests.exceptions.RequestException: If there is an error while making the HTTP requests to retrieve the PDF file or its size.
         :raises Exception: If there is an error while extracting text from the PDF file using Tika or while cleaning the extracted text content.
        """
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

    @staticmethod
    def _extract_licence(unesdoc_document: UNESDOCItem) -> str:
        rights = unesdoc_document.rights
        if not rights:
            raise NoLicenseFoundError("No license found in the document metadata.")
        [licence_content] = XMLExtractor(rights).extract_content("a")
        return licence_content.attributes["href"]

    def _extract_topics(self, metadata: UNESDOCItem) -> list[TopicDetails]:
        ret: list[TopicDetails] = []

        for topic in metadata.subject:
            ret.append(
                TopicDetails(
                    name=topic.lower(),
                    depth=0,
                    directly_contained_in=[],
                    external_id=None,
                    external_depth_name=None,
                )
            )

        return ret

    @staticmethod
    def _extract_authors(metadata: UNESDOCItem) -> list[AuthorDetails]:
        ret: list[AuthorDetails] = []
        for creator in metadata.creator:
            ret.append(AuthorDetails(name=creator, misc=""))
        return ret

    @staticmethod
    def _check_licence_authorization(_license: str) -> None:
        if _license not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(f"License '{_license}' is not authorized.")

    def _extract_metadata(self, unesdoc_metdata: UNESDOCItem) -> dict:
        ret_type = unesdoc_metdata.type[0] if unesdoc_metdata.type else None
        topics = self._extract_topics(unesdoc_metdata)
        license_url = self._extract_licence(unesdoc_metdata)
        authors = self._extract_authors(unesdoc_metdata)

        return {
            "type": ret_type,
            "topics": topics,
            "licence_url": license_url,
            "authors": authors,
        }

    def _get_metadata_json(self, document: WeLearnDocument) -> UNESDOCItem:
        """
        Get the metadata of a document from the unesdoc API, using the document external_id as a search query.
         The metadata is returned as a UNESDOCItem object.
         If no document is found, a ValueError is raised.
         If more than one document is found, only the first one is returned and a warning is logged.
         The search query is made on the url field of the unesdoc API, which contains the external_id of the document in the format "ark:/12345/abcde" or "ark:/12345/abcde/lang".
         :param document: WeLearnDocument object containing the external_id to search for in the unesdoc API.
         :return: UNESDOCItem object containing the metadata of the document.
         :raises ValueError: If no document is found for the given external_id.
        """
        session = get_new_https_session()
        param = {
            "where": f'search(url, "{document.external_id}")',
            "select": "url, year, language, title, type,description, subject,creator,rights",
            "limit": 1,
        }
        resp = session.get(self.api_base_url + "/records", params=param)
        resp.raise_for_status()
        root = UNESDOCRoot.model_validate(resp.json())
        results = root.results
        if not results:
            raise ValueError(f"No document found for url {document.url}")
        [ret] = results
        return ret

    @staticmethod
    def _convert_ark_id_to_iid(ark_id: str) -> str:
        """
        Convert an ark id like "48223/pf0000389119" to "p::usmarcdef_0000389119" and
        "48223/pf0000396769/fre" to "p::usmarcdef_0000396769_fre"
         The ark id is expected to be in the format "12345/abcde" or "12345/abcde/lang", where
         "12345" is the ark prefix, "abcde" is the document id and "lang" is the language code.
         :param ark_id: The ark id to convert.
         :return: The converted iid.
         :raises ValueError: If the ark id is not in the expected format.
        """
        # Convert an ark id like "48223/pf0000389119" to "p::usmarcdef_0000389119" and
        # "48223/pf0000396769/fre" to "p::usmarcdef_0000396769_fre"
        if "/" in ark_id:
            parts = ark_id.split("/")
            if len(parts) == 2:
                return f"p::usmarcdef_{parts[1]}"
            elif len(parts) == 3:
                return f"p::usmarcdef_{parts[1]}_{parts[2]}"
        raise ValueError(f"Invalid ark id format: {ark_id}")

    @staticmethod
    def _get_pdf_document_name(iid: str) -> list[str]:
        """
        Get the name of the PDF document associated with a given iid from the unesdoc API.
         The PDF document name is returned as a list of strings, as there can be multiple PDF documents associated with a given iid.
         If no PDF document is found, an empty list is returned
            :param iid: The iid to search for in the unesdoc API.
            :return: A list of strings containing the names of the PDF documents associated with the given iid.
            :raises HTTPError: If there is an error while making the request to the unesdoc API.
        """
        session = get_new_https_session()
        param = {"id": iid, "multiple": True, "multilingual": True}
        resp = session.get(
            "https://unesdoc.unesco.org/in/rest/api/documentPlaylistById", params=param
        )
        resp.raise_for_status()
        data = resp.json()
        sources = UNESDOCSources.model_validate(data)
        ret = []
        for s in sources.sources:
            if s:
                ret.append(s.Document)
        return ret

    def _get_description(self, unesdoc_metadata: UNESDOCItem) -> str:
        description = unesdoc_metadata.description
        if not description:
            lang = unesdoc_metadata.language[0] if unesdoc_metadata.language else None
            if not lang:
                raise NoDescriptionFoundError(
                    "No description found in the document metadata."
                )
            return translations.get(lang)
        return self._clean_txt_content(description)

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        ret: list[WrapperRetrieveDocument] = []
        for document in documents:
            try:
                metadata = self._get_metadata_json(document=document)
                _license = self._extract_licence(metadata)
                self._check_licence_authorization(_license)
                iid = self._convert_ark_id_to_iid(document.url.split("ark:/")[1])
                pdf_names = self._get_pdf_document_name(iid=iid)
                if len(pdf_names) == 0:
                    raise NoContent(
                        f"No PDF document found for document {document.url}"
                    )
                pdf_url = f"https://unesdoc.unesco.org/in/rest/annotationSVC/DownloadWatermarkedAttachment/{pdf_names[0]}"
                pdf_content = self._get_pdf_content(pdf_url)

                document.full_content = pdf_content
                document.description = self._get_description(metadata)
                document.title = metadata.title
                document.details = self._extract_metadata(metadata)
                document.lang = lang_iso3_to_lang_iso2.get(metadata.language[0], None)

            except requests.exceptions.RequestException as e:
                msg = f"Error while retrieving uved ({document.url}) document from this url {self.api_base_url}/resources/{document.external_id}: {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        http_error_code=get_http_code_from_exception(e),
                        error_info=msg,
                    )
                )
                continue
            except pydantic.ValidationError as e:
                msg = f"Error while validating uved ({document.url}) document from this url {self.api_base_url}/resources/{document.external_id} : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

            ret.append(WrapperRetrieveDocument(document=document))

        return ret
