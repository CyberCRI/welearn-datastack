import logging
from datetime import datetime, timezone

import pydantic
import requests
from welearn_database.data.models import WeLearnDocument
from welearn_database.exceptions import ContentIsTooShort

from welearn_datastack import constants
from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.source_models.datagouv import Dataset
from welearn_datastack.exceptions import (
    NoDescriptionFoundError,
)
from welearn_datastack.modules.scraping_utils import clean_text
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import (
    get_http_code_from_exception,
    get_new_https_session,
)

logger = logging.getLogger(__name__)


# Collector
class DataGouvCollector(IPluginRESTCollector):
    related_corpus = "datagouv"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True

        self.base_url = "https://www.data.gouv.fr"
        self.headers = constants.HEADERS

    @staticmethod
    def _parse_timestamp(value: str) -> float:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()

    def _extract_metadata(self, datagouv_document: Dataset) -> dict:
        # Simple metadata
        doi = datagouv_document.doi
        frequency = datagouv_document.frequency
        license = datagouv_document.license
        main_institution = (
            datagouv_document.organization.name
            if datagouv_document.organization is not None
            else None
        )
        resource_link = datagouv_document.page
        tags = datagouv_document.tags

        publication_date = self._parse_timestamp(datagouv_document.created_at)
        update_date = self._parse_timestamp(datagouv_document.last_modified)

        return {
            "doi": doi,
            "frequency": frequency,
            "main_institution": main_institution,
            "license": license,
            "resource_link": resource_link,
            "tags": tags,
            "publication_date": publication_date,
            "update_date": update_date,
        }

    def _get_json(
        self, session: requests.Session, document: WeLearnDocument
    ) -> Dataset:
        forged_url = f"{self.base_url}/api/1/datasets/{document.external_id}"
        resp = session.get(forged_url, timeout=30)
        resp.raise_for_status()

        return Dataset.model_validate(resp.json())

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        ret: list[WrapperRetrieveDocument] = []
        session = get_new_https_session()
        for document in documents:
            try:
                datagouv_document = self._get_json(session, document)
            except requests.exceptions.RequestException as e:
                msg = f"Error while retrieving datagouv ({document.url}) metadata from this url {self.base_url}/api/1/datasets/{document.external_id}: {e}"
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
                msg = f"Error while validating datagouv ({document.url}) metadata from this url {self.base_url}/api/1/datasets/{document.external_id} : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

            try:
                if not datagouv_document.description:
                    raise NoDescriptionFoundError("No description found")
            except NoDescriptionFoundError as e:
                msg = f"Error while retrieving description for datagouv ({document.url}) metadata : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue

            description = clean_text(datagouv_document.description)
            full_content = description

            document.title = datagouv_document.title
            document.description = description
            try:
                document.full_content = full_content
            except ContentIsTooShort as e:
                msg = f"Content too short for datagouv ({document.url}) document : {e}"
                logger.error(msg)
                ret.append(
                    WrapperRetrieveDocument(
                        document=document,
                        error_info=msg,
                    )
                )
                continue
            document.doi = datagouv_document.doi
            document.external_id = datagouv_document.id
            try:
                document.details = self._extract_metadata(datagouv_document)
            except Exception as e:
                msg = f"Error while extracting metadata for datagouv ({document.url}) document : {e}"
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
