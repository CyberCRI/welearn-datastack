import logging

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.constants import ZENODO_API_BASE_URL, ZENODO_APPLICATION_BASE_URL
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.exceptions import (
    NoDOIFoundError,
    NoExternalID,
    WrongExternalIdFormat,
)
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class ZenodoCollector(URLCollector):
    def __init__(self, corpus: Corpus):
        self.corpus = corpus

        self.api_base_url = ZENODO_API_BASE_URL
        self.application_base_url = ZENODO_APPLICATION_BASE_URL

    @staticmethod
    def _compute_search_parameters(
        community_name: str, doc_type: str | None = None, ascending: bool = True
    ):
        sort_value = "mostrecent" if ascending else "-mostrecent"
        querystring = {
            "communities": community_name,
            "sort": sort_value,
        }
        if doc_type:
            querystring["type"] = doc_type

        return querystring

    def _compute_subdocument(self, hit: dict) -> list[WeLearnDocument]:
        ret = []
        for identifier in hit["metadata"].get("related_identifiers", []):
            if identifier["relation"] == "hasPart":
                doc_id = identifier["identifier"]
                if identifier.get("schema", identifier.get("scheme", None)) != "doi":
                    raise WrongExternalIdFormat(
                        f"We only manage DOI for Zenodo external ID: {doc_id}"
                    )
                # Retrieve the second part of the DOI it's the zenodo ID
                zenodo_id = doc_id.split(".")[-1]
                full_doi = doc_id

                url = f"{self.application_base_url}{zenodo_id}"
                ret.append(
                    WeLearnDocument(
                        doi=full_doi,
                        external_id=zenodo_id,
                        url=url,
                        corpus_id=self.corpus.id,
                    )
                )
        return ret

    def _convert_hit_into_documents(
        self, hit: dict, only_sub_documents: bool
    ) -> list[WeLearnDocument]:
        if only_sub_documents:
            return self._compute_subdocument(hit)

        doc_id = hit.get("id", None)
        if not doc_id:
            raise NoExternalID()

        full_doi = hit.get("doi", None)
        if not full_doi:
            raise NoDOIFoundError(f"Document {doc_id} does not have DOI")

        url = f"{self.application_base_url}{doc_id}"
        return [
            WeLearnDocument(
                doi=full_doi,
                external_id=doc_id,
                url=url,
                corpus_id=self.corpus.id,
            )
        ]

    def _convert_hits_to_documents(
        self, json_from_zenodo: dict
    ) -> list[WeLearnDocument]:
        first_level_hits = json_from_zenodo.get("hits", {})
        logger.info("First level hits is %s long", str(len(first_level_hits)))
        second_level_hits = first_level_hits.get("hits", [])
        logger.info("Second level hits is %s long", str(len(second_level_hits)))

        ret = []
        for hit in second_level_hits:
            ret.extend(self._convert_hit_into_documents(hit, only_sub_documents=True))

        return ret

    def collect(self, doc_type: str | None = None) -> list[WeLearnDocument]:
        session = get_new_https_session()
        search_parameters = self._compute_search_parameters(
            community_name=self.corpus.source_name.lower(),
            doc_type=doc_type,
        )
        zenodo_ret = session.get(self.api_base_url, params=search_parameters)

        zenodo_ret.raise_for_status()

        urls = self._convert_hits_to_documents(zenodo_ret.json())
        return urls
