import io
import logging
import os
from dataclasses import asdict
from datetime import datetime

import pydantic
import requests
from welearn_database.data.models import WeLearnDocument
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
    NoDescriptionFoundError,
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
    "ara": "يرجى الرجوع إلى النص الكامل لمزيد من التفاصيل.",
    "ces": "Podrobnosti naleznete v plném znění textu.",
    "ita": "Consulti il testo completo per maggiori dettagli.",
    "kor": "자세한 내용은 전체 본문을 확인하세요.",
    "nld": "Raadpleeg de volledige tekst voor meer details.",
    "zho": "更多详情请参阅全文。",
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
    def _extract_licence(uved_document: UVEDMemberItem) -> str:
        licence = None
        cats = uved_document.categories
        license_equivalence_uved_cc = {
            8: "by",  # Attribution
            6: "sa",  # ShareAlike
            13: "nd",  # NoDerivatives
            9: "nc",  # NonCommercial
        }
        licence_flag_cc: set[str] = {"by"}
        for cat in cats:
            if (
                cat.uid in license_equivalence_uved_cc.keys()
            ):  # Authorized licenses uids
                licence_flag_cc.add(license_equivalence_uved_cc[cat.uid])
        if "nd" in licence_flag_cc and "sa" in licence_flag_cc:
            licence_flag_cc.remove(
                "sa"
            )  # ND and SA are incompatible, ND takes precedence
        if licence_flag_cc:
            licence = "CC-" + "-".join(sorted(licence_flag_cc)) + "-4.0"
        return format_cc_license(licence)

    def _extract_topics(
        self, uved_metadata_categorization: list[Category]
    ) -> list[TopicDetails]:
        ret: list[TopicDetails] = []

        for name, uid in [("Domaines", 31), ("Thèmes", 20)]:
            topics = self._extract_specific_metadata(
                uved_metadata_categorization, parent_uid=uid, with_uid=True
            )
            for topic, topic_uid in topics:
                ret.append(
                    TopicDetails(
                        name=topic,
                        depth=0,
                        external_depth_name=name,
                        directly_contained_in=[],
                        external_id=str(topic_uid),
                    )
                )
        return ret

    @staticmethod
    def _extract_authors(uved_document: UVEDMemberItem) -> list[AuthorDetails]:
        ret: list[AuthorDetails] = []
        for contributor in uved_document.contributor:
            ret.append(
                AuthorDetails(
                    name=f"{contributor.firstName} {contributor.lastName}", misc=""
                )
            )
        return ret

    @staticmethod
    def _check_licence_authorization(_license: str) -> None:
        if _license not in AUTHORIZED_LICENSES:
            raise UnauthorizedLicense(f"License '{_license}' is not authorized.")

    def _extract_metadata(self, unesdoc_metdata: UNESDOCItem) -> dict:
        ret_type = unesdoc_metdata.type[0] if unesdoc_metdata.type else None

        return {"type": ret_type, "topics": [], "licence_url": "", "authors": []}

    def _get_metadata_json(self, document: WeLearnDocument) -> UNESDOCItem:
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

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        ret: list[WrapperRetrieveDocument] = []
        for document in documents:
            try:
                uved_document = self._get_json(document)
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

            try:
                if not uved_document.description:
                    raise NoDescriptionFoundError("No description found")
            except NoDescriptionFoundError as e:
                msg = f"Error while retrieving description for uved ({document.url}) document : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

            description = self._clean_txt_content(uved_document.description)

            if uved_document.transcription and len(uved_document.transcription) > 1:
                full_content = self._clean_txt_content(uved_document.transcription)
            elif (
                uved_document.transcriptionFile
                and self.pdf_size_file_limit > uved_document.transcriptionFile.file.size
            ):
                try:
                    full_content = self._get_pdf_content(
                        uved_document.transcriptionFile.url
                    )
                    full_content = self._clean_txt_content(full_content)
                except Exception as e:
                    msg = f"Error while retrieving PDF content for uved ({document.url}) document from this url {uved_document.transcriptionFile.url} : {e}"
                    logger.error(msg)
                    ret.append(
                        WrapperRetrieveDocument(
                            document=document,
                            error_info=msg,
                            http_error_code=get_http_code_from_exception(e),
                        )
                    )
                    continue
            else:
                full_content = description

            document.title = uved_document.title
            document.description = description
            document.full_content = full_content
            try:
                document.details = self._extract_metadata(uved_document)
            except Exception as e:
                msg = f"Error while extracting metadata for uved ({document.url}) document : {e}"
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
