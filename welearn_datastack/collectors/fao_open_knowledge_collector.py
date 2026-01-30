import logging
from typing import List

import requests  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack import constants
from welearn_datastack.data.source_models.fao_open_knowledge import FaoOKModel
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class FAOOpenKnowledgeURLCollector(URLCollector):
    related_corpus = "fao-open-knowledge"

    def __init__(self, corpus: Corpus):
        self.corpus = corpus

        self.api_base_url = "https://openknowledge.fao.org/server/api/"
        self.application_base_url = "https://openknowledge.fao.org/"
        self.headers = constants.HEADERS

    def _extract_fao_ok_urls(
        self, fao_ok_api_response: FaoOKModel
    ) -> List[WeLearnDocument]:
        urls: List[WeLearnDocument] = []
        for item in fao_ok_api_response.embedded.items:
            document = WeLearnDocument(
                url=self.application_base_url + f"handle/{item.handle}",
                external_id=item.uuid,
                corpus=self.corpus,
            )
            urls.append(document)
        return urls

    def collect(self) -> List[WeLearnDocument]:
        session = get_new_https_session()

        discover_url = f"{self.api_base_url}discover/browses/dateavailable/items"
        params = {
            "sort": "default,DESC",
            "page": 0,
            "size": 50,
        }
        fao_ok_resp = session.get(url=discover_url, headers=self.headers, params=params)
        fao_ok_resp.raise_for_status()
        fao_ok_response = FaoOKModel.model_validate(fao_ok_resp.json())

        urls = self._extract_fao_ok_urls(fao_ok_response)
        return urls
