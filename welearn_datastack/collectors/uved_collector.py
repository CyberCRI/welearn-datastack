import logging
from typing import List

import requests  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack import constants
from welearn_datastack.data.source_models.uved import RootUVEDModel
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class UVEDURLCollector(URLCollector):
    related_corpus = "uved"

    def __init__(self, corpus: Corpus):
        self.corpus = corpus

        self.api_base_url = "https://www.uved.fr/api/V1"
        self.application_base_url = "https://www.uved.fr/fiche/ressource/"
        self.headers = constants.HEADERS

    def _get_object_uved_api(self) -> RootUVEDModel:
        client = get_new_https_session()
        params = {
            "page": 1,
            "order[date]": "desc",
            "pagination": True,
            "itemsPerPage": 10,
        }
        response = client.get(
            f"{self.api_base_url}/resources",
            params=params,
            headers=self.headers,
        )
        response.raise_for_status()
        return RootUVEDModel.model_validate(response.json())

    def _extract_uved_urls(
        self, uved_api_response: RootUVEDModel
    ) -> List[WeLearnDocument]:
        urls: List[WeLearnDocument] = []
        for item in uved_api_response.hydra_member:
            document = WeLearnDocument(
                url=self.application_base_url + item.slug,
                external_id=item.uid,
                corpus=self.corpus,
            )
            urls.append(document)
        return urls

    def collect(self) -> List[WeLearnDocument]:
        uved_api_response = self._get_object_uved_api()
        urls = self._extract_uved_urls(uved_api_response)
        return urls
