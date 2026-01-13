import io
import json
import logging
import math
import os
import re
from collections import deque
from dataclasses import asdict
from datetime import datetime
from itertools import batched
from typing import Dict, Iterable, List

import pydantic
import requests
from lingua import Language
from welearn_database.data.models import WeLearnDocument
from welearn_database.modules.text_cleaning import clean_text

from welearn_datastack import constants
from welearn_datastack.constants import AUTHORIZED_LICENSES, HEADERS
from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.details_dataclass.scholar_fields import ScholarFieldsDetails
from welearn_datastack.data.details_dataclass.scholar_institution_type import (
    InstitutionTypeName,
    ScholarInstitutionTypeDetails,
)
from welearn_datastack.data.details_dataclass.scholar_level import ScholarLevelDetails
from welearn_datastack.data.details_dataclass.topics import TopicDetails
from welearn_datastack.data.source_models.oapen import Metadatum, OapenModel
from welearn_datastack.data.source_models.uved import Category, UVEDMemberItem
from welearn_datastack.exceptions import (
    NoDescriptionFoundError,
    PDFFileSizeExceedLimit,
    TooMuchLanguages,
    UnauthorizedLicense,
    UnauthorizedState,
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
from welearn_datastack.utils_.scraping_utils import (
    format_cc_license,
    remove_extra_whitespace,
)

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
        self.application_base_url = "https://www.uved.fr/fiche/ressource/"
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
    def _extract_specific_metadata(
        uved_metadata_categorization: list[Category],
        parent_uid: int,
        with_uid: bool = False,
    ) -> list[str] | list[tuple[str, int]]:
        ret: list[str] = []
        for category in uved_metadata_categorization:
            if category.parent and category.parent.uid == parent_uid:
                if with_uid:
                    ret.append((category.title.lower(), category.uid))
                else:
                    ret.append(category.title.lower())
        return ret

    @staticmethod
    def _convert_level(input_str) -> ScholarLevelDetails:
        corres_french_level_cite = {
            "bac": 344,
            "bac+1": 541,
            "bac+2": 641,
            "bac+3": 665,
            "bac+4": 761,
            "bac+5": 766,
            "bac+6": 767,
            "bac+7": 861,
            "bac+8": 864,
            "du": 544,
        }
        level_id = corres_french_level_cite.get(input_str.lower())
        if level_id:
            return ScholarLevelDetails(
                isced_level=level_id,
                original_scholar_level_name=input_str,
                original_country="france",
            )
        else:
            return ScholarLevelDetails(
                isced_level=0,
                original_scholar_level_name=input_str,
                original_country="france",
            )

    @staticmethod
    def _convert_field_of_education(input_str: str) -> ScholarFieldsDetails:
        corres_french_field_of_education_cite = {
            "droit": "0421",  # Law
            "economie": "0311",  # Economics
            "gestion": "0410",  # Business and administration (generic)
            "economie et gestion": "0400",  # Business, administration and law (broad)
            "science politique": "0312",  # Political science
            "sciences sanitaires et sociales": "0910",  # Health and welfare (generic)
            "histoire": "0222",  # History and archaeology
            "géographie et aménagement": "0319",  # Not specified elsewhere
            "psychologie": "0313",  # Psychology
            "sciences de l'éducation": "0111",  # Education science
            "philosophie": "0223",  # Philosophy and ethics
            "sciences sociales": "0310",  # Social sciences (generic)
            "sciences de l’homme, anthropologie, ethnologie": "0314",  # Anthropology and cultural studies
            "mathématiques": "0541",  # Mathematics
            "physique": "0533",  # Physics
            "physique, chimie": "0530",  # Natural sciences (broad)
            "sciences de la vie": "0511",  # Biology
            "sciences de la terre": "0532",  # Earth sciences / geology
            "sciences de la vie et de la terre": "0510",  # Natural sciences (broad)
            "génie civil": "0732",  # Civil engineering
            "sciences pour l'ingénieur": "0700",  # Engineering, manufacturing and construction (broad)
        }
        field_code = corres_french_field_of_education_cite.get(input_str.lower())
        if field_code:
            return ScholarFieldsDetails(
                isced_field=int(field_code),
                original_scholar_field_name=input_str,
                original_country="france",
            )
        else:
            return ScholarFieldsDetails(
                isced_field=9999,
                original_scholar_field_name=input_str,
                original_country="france",
            )

    def _extract_fields_of_education(
        self, uved_metadata_categorization: list[Category]
    ) -> list[ScholarFieldsDetails]:
        ret: list[ScholarFieldsDetails] = []
        fields = self._extract_specific_metadata(
            uved_metadata_categorization, parent_uid=115
        )
        for field in fields:
            field_detail = self._convert_field_of_education(field)
            ret.append(field_detail)
        return ret

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

    def _extract_activities_types(
        self, uved_metadata_categorization: list[Category]
    ) -> list[str | None]:
        activity_type_mapping = {
            "cours": "course",
            "exercice": "exercise",
            "activités": "activity",
            "animation": "workshop",
            "autoévaluation": "self-assessment",
            "documentaire": "documentary",
            "étude de cas": "case study",
            "évaluation": "assessment",
            "lecture": "reading",
            "outil": "tool",
            "parcours de formation": "learning path",
            "présentation": "presentation",
            "questionnaire": "quiz",
            "scénario pédagogique": "learning scenario",
            "simulation": "simulation",
            "entretiens et témoignages": "interviews and testimonials",
            "démonstration": "demonstration",
            "glossaire": "glossary",
            "directs": "live session",
        }
        ret: list[str] = []
        activity_types = self._extract_specific_metadata(
            uved_metadata_categorization, parent_uid=10
        )
        for activity_type in activity_types:
            mapped_value = activity_type_mapping.get(activity_type)
            if mapped_value:
                ret.append(mapped_value)
            else:
                logger.warning(f"Activity type '{activity_type}' not found in mapping.")
                ret.append(activity_type)
        return ret

    def _extract_levels(
        self, uved_metadata_categorization: list[Category]
    ) -> list[ScholarLevelDetails]:
        ret: list[ScholarLevelDetails] = []
        levels = self._extract_specific_metadata(
            uved_metadata_categorization, parent_uid=14
        )
        for level in levels:
            level_detail = self._convert_level(level)
            ret.append(level_detail)
        return ret

    def _extract_external_sdg_ids(
        self, uved_metadata_categorization: list[Category]
    ) -> list[int]:
        ret: list[int] = []
        ids = self._extract_specific_metadata(
            uved_metadata_categorization, parent_uid=90
        )
        for ext_id in ids:
            if ext_id.lower() == "Les 17 ODD".lower():
                return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
            else:
                try:
                    sdg_id = int(ext_id.lower().split(". ")[0])
                    ret.append(sdg_id)
                except ValueError:
                    logger.warning(f"Cannot convert SDG id '{ext_id}' to int.")
            ret.sort()
        return ret

    def _extract_scholar_institution_types(
        self, uved_metadata_categorization: list[Category]
    ) -> list[ScholarInstitutionTypeDetails]:
        names = self._extract_specific_metadata(
            uved_metadata_categorization, parent_uid=209
        )

        ret: list[ScholarInstitutionTypeDetails] = []
        for name in names:
            taxonomy_name: InstitutionTypeName | None = None
            isced_level_awarded: list[int] | None = None
            match name.lower():
                case "grande Ecole, ecole d’ingénieurs":
                    taxonomy_name = InstitutionTypeName.SEL
                    isced_level_awarded = [7]
                case "université":
                    taxonomy_name = InstitutionTypeName.UNI
                    isced_level_awarded = [6, 7, 8]
                case "ecole de commerce":
                    taxonomy_name = InstitutionTypeName.BUS
                    isced_level_awarded = [6, 7]
                case "autre établissement":
                    taxonomy_name = InstitutionTypeName.OTHER
                    isced_level_awarded = []
                case _:
                    logger.warning(f"Institution type '{name}' not found in mapping.")
                    continue

            if not taxonomy_name:
                continue

            if not isced_level_awarded:
                isced_level_awarded = []

            ret.append(
                ScholarInstitutionTypeDetails(
                    taxonomy_name=taxonomy_name,
                    isced_level_awarded=isced_level_awarded,
                    original_institution_type_name=name,
                    original_country="france",
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

    @staticmethod
    def _check_state_authorization(state: str) -> None:
        if state != "labellisé":
            raise UnauthorizedState(f"State '{state}' is not authorized.")

    def _extract_metadata(self, uved_document: UVEDMemberItem) -> dict:
        # Simple metadata
        tags = [kw.title.lower() for kw in uved_document.keywords]
        main_institution = uved_document.mainInstitution.name
        resource_link = uved_document.url

        dt_format = "%Y-%m-%dT%H:%M:%S"
        publication_date = datetime.strptime(
            uved_document.date.split(".")[0], dt_format
        ).timestamp()
        recognition = self._extract_specific_metadata(uved_document.categories, 152)
        learning_modalities = self._extract_specific_metadata(
            uved_document.categories, 214
        )
        target_audiences = self._extract_specific_metadata(
            uved_document.categories, 198
        )
        used_sources = self._extract_specific_metadata(uved_document.categories, 218)
        initiative_types = self._extract_specific_metadata(
            uved_document.categories, 146
        )
        types = self._extract_specific_metadata(uved_document.categories, 1)
        formation_type = self._extract_specific_metadata(uved_document.categories, 204)
        institution_statut_for_provider = self._extract_specific_metadata(
            uved_document.categories, 74
        )
        state = self._extract_specific_metadata(uved_document.categories, 70)[0]
        self._check_state_authorization(state)

        # Complex metadata
        licence = self._extract_licence(uved_document)
        # self._check_licence_authorization(licence)

        topics = [asdict(o) for o in self._extract_topics(uved_document.categories)]
        levels = [asdict(o) for o in self._extract_levels(uved_document.categories)]
        external_sdg_ids = self._extract_external_sdg_ids(uved_document.categories)
        activities_types = self._extract_activities_types(uved_document.categories)
        scholar_institution_types = [
            asdict(o)
            for o in self._extract_scholar_institution_types(uved_document.categories)
        ]
        fields_of_education = [
            asdict(o)
            for o in self._extract_fields_of_education(uved_document.categories)
        ]

        return {
            "tags": tags,
            "main_institution": main_institution,
            "resource_link": resource_link,
            "publication_date": publication_date,
            "recognition": recognition,
            "learning_modalities": learning_modalities,
            "target_audiences": target_audiences,
            "used_sources": used_sources,
            "initiative_types": initiative_types,
            "types": types,
            "formation_type": formation_type,
            "institution_statut_for_provider": institution_statut_for_provider,
            "licence": licence,
            "state": state,
            "topics": topics,
            "levels": levels,
            "external_sdg_ids": external_sdg_ids,
            "activities_types": activities_types,
            "scholar_institution_types": scholar_institution_types,
            "fields_of_education": fields_of_education,
            "authors": [asdict(o) for o in self._extract_authors(uved_document)],
        }

    def _get_json(self, document: WeLearnDocument) -> UVEDMemberItem:
        session = get_new_https_session()
        forged_url = f"{self.api_base_url}/resources/{document.external_id}"
        resp = session.get(forged_url)
        resp.raise_for_status()

        return UVEDMemberItem.model_validate(resp.json())

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
