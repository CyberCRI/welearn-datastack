import logging
import math
from typing import List

import requests
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack import constants
from welearn_datastack.data.source_models.datagouv import RootDataGouvModel
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)

DATA_GOUV_PAGE_SIZE = 100


class DataGouvURLCollector(URLCollector):
    related_corpus = "datagouv"

    def __init__(self, corpus: Corpus):
        self.corpus = corpus

        self.base_url = "https://www.data.gouv.fr"
        self.headers = constants.HEADERS

    def _get_object_datagouv_api(
        self, client: requests.Session, page: int
    ) -> RootDataGouvModel:
        params = {
            "page": page,
            "page_size": DATA_GOUV_PAGE_SIZE,
            "sort": "-created",
            "access_type": "open",
        }
        response = client.get(
            f"{self.base_url}/api/1/datasets",
            params=params,
            headers=self.headers,
        )
        response.raise_for_status()
        return RootDataGouvModel.model_validate(response.json())

    def _extract_datagouv_urls(
        self, datagouv_api_response: RootDataGouvModel
    ) -> list[WeLearnDocument]:
        urls: list[WeLearnDocument] = []
        for item in datagouv_api_response.data:
            if not item.page:
                logger.warning(
                    "Dataset '%s' has no page URL",
                    item.id,
                )
                continue
            document = WeLearnDocument(
                url=item.page,
                external_id=item.id,
                corpus=self.corpus,
            )
            urls.append(document)
        return urls

    def collect(self) -> list[WeLearnDocument]:
        client = get_new_https_session()
        datagouv_api_response = self._get_object_datagouv_api(client, page=1)

        page_count = math.ceil(
            datagouv_api_response.total / datagouv_api_response.page_size
        )
        logger.info(
            "Retrieving %s DataGouv datasets across %s pages",
            datagouv_api_response.total,
            page_count,
        )

        urls = self._extract_datagouv_urls(datagouv_api_response)
        for page in range(2, page_count + 1):
            logger.info("Retrieving DataGouv page %s/%s", page, page_count)
            page_response = self._get_object_datagouv_api(client, page=page)
            urls.extend(self._extract_datagouv_urls(page_response))

        return urls
