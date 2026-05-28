import logging
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

from welearn_database.data.enumeration import ExternalIdType
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack import constants
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.data.xml_data import XMLData
from welearn_datastack.exceptions import NotEnoughData, NoUrl
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class WorldBankOpenKnowledgeRepositoryCollector(URLCollector):
    related_corpus = "world-bank-open-knowledge-repository"

    def __init__(self, corpus: Corpus, date_last_insert: int):
        self.corpus = corpus
        self.date_last_insert = date_last_insert

        self.api_base_url = "https://openknowledge.worldbank.org/server/oai/request"
        self.application_base_url = "https://openknowledge.worldbank.org/handle/"
        self.headers = constants.HEADERS

    def _extract_url(self, xml_input: XMLData) -> str:
        full_record = XMLExtractor(xml_input.content)
        identifiers = full_record.extract_content_attribute_filter(
            tag="mods:identifier", attribute_name="type", attribute_value="uri"
        )

        try:
            [uri] = identifiers
        except ValueError:
            logger.warning(
                "No identifier with type 'uri' found in record, skipping. Record content: %s",
                xml_input.content,
            )
            raise NoUrl("Not exactly one identifier with type 'uri' found in record")
        handle = uri.content.replace("https://hdl.handle.net/", "")
        ret = f"{self.application_base_url}{handle}"

        return ret

    @staticmethod
    def _extract_doi(xml_input: XMLData) -> str | None:
        full_record = XMLExtractor(xml_input.content)
        identifiers = full_record.extract_content_attribute_filter(
            tag="mods:identifier", attribute_name="type", attribute_value="doi"
        )

        try:
            [doi] = identifiers
        except ValueError:
            logger.warning(
                "No identifier with type 'doi' found in record, skipping.",
            )
            return None

        return doi.content

    @staticmethod
    def _extract_external_id(xml_input: XMLData) -> str:
        full_record = XMLExtractor(xml_input.content)
        try:
            oai_pmh_id = (
                XMLExtractor(full_record.extract_content(tag="header")[0].content)
                .extract_content(tag="identifier")[0]
                .content
            )
        except IndexError:
            raise NotEnoughData("No identifier found in header of record")
        return oai_pmh_id

    @staticmethod
    def _is_deleted(xml_input: XMLData) -> bool:
        """
        Check if this record is flagged deleted
        :param xml_input: Record from OAI PMH
        :return: True if it's flagged as deleted, false otherwise
        """
        full_record = XMLExtractor(xml_input.content)
        ret = full_record.extract_content_attribute_filter(
            tag="header", attribute_name="status", attribute_value="deleted"
        )
        return len(ret) > 0

    def _extract_world_bank_okr_document(
        self, world_bank_okr_api_response: XMLExtractor
    ) -> list[WeLearnDocument]:
        urls: List[WeLearnDocument] = []
        records = world_bank_okr_api_response.extract_content(tag="record")
        for record in records:
            external_id = self._extract_external_id(record)
            if self._is_deleted(record):
                logger.info(
                    "Record with external id %s is marked as deleted, skipping.",
                    external_id,
                )
                continue
            url = self._extract_url(record)
            doi = self._extract_doi(record)
            urls.append(
                WeLearnDocument(
                    url=url,
                    doi=doi,
                    external_id=external_id,
                    external_id_type=ExternalIdType.API_ID,
                    corpus_id=self.corpus.id,
                )
            )
        return urls

    def _format_date(self):
        str_format_date_iso = "%Y-%m-%dT%H:%M:%SZ"
        formated_date: str = datetime.fromtimestamp(
            self.date_last_insert, tz=ZoneInfo("GMT")
        ).strftime(str_format_date_iso)

        return formated_date

    def collect(self) -> List[WeLearnDocument]:
        session = get_new_https_session()

        params = {
            "verb": "ListRecords",
            "metadataPrefix": "mods",
            "from": self._format_date(),
        }

        wbokr_ok_resp = session.get(
            url=self.api_base_url, headers=self.headers, params=params
        )
        wbokr_ok_resp.raise_for_status()

        urls = self._extract_world_bank_okr_document(XMLExtractor(wbokr_ok_resp.text))
        return urls
