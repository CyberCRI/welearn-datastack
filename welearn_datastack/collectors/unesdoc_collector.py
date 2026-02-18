import logging
from typing import List

import requests  # type: ignore
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack import constants
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class UNESDOCURLCollector(URLCollector):
    related_corpus = "unesdoc"

    def __init__(self, corpus: Corpus):
        self.corpus = corpus

        self.api_base_url = (
            "https://data.unesco.org/api/explore/v2.1/catalog/datasets/doc001/"
        )
        self.application_base_url = "https://unesdoc.unesco.org/ark:/"
        self.headers = constants.HEADERS

    def _get_unesdoc_url(self) -> list[str]:
        client = get_new_https_session()
        params = {
            "order_by": "year DESC",
            "select": "url",
            "where": 'search(rights, "by-sa/3.0/igo/")',
        }
        response = client.get(
            f"{self.api_base_url}",
            params=params,
            headers=self.headers,
        )
        response.raise_for_status()

        res = []
        for result in response.json().get("results", []):
            url = result.get("url")
            if url:
                res.append(url)

        return res

    def _correct_unesdoc_url(self, url: str) -> str:
        # Ensure URL like that: https://unesdoc.unesco.org/ark:/48223/pf0000396769/fre are correctly formatted like :
        # https://unesdoc.unesco.org/ark:/48223/pf0000396769_fre
        parts = url.split("/")
        if len(parts) >= 5:
            ark_part = parts[4]  # This should be "ark:12345"
            doc_part = parts[5]  # This should be "pf0000396769"
            lang_part = (
                parts[6] if len(parts) > 6 else ""
            )  # This should be "fre" or similar
            if lang_part:
                return f"{self.application_base_url}{ark_part}/{doc_part}_{lang_part}"
            else:
                return f"{self.application_base_url}{ark_part}/{doc_part}"
        else:
            logger.warning(f"URL does not have the expected format: {url}")
            raise ValueError(f"URL does not have the expected format: {url}")

    @staticmethod
    def _extract_unesdoc_id_from_url(url: str) -> str:
        # The URL format is expected to be: https://unesdoc.unesco.org/ark:/12345/abcde
        # We want to extract the part after "ark:/"
        if "ark:/" in url:
            return url.split("ark:/")[1]
        else:
            logger.warning(f"URL does not contain 'ark:/': {url}")
            return ""

    def collect(self) -> List[WeLearnDocument]:
        raw_urls = self._get_unesdoc_url()

        ret = []
        for url in raw_urls:
            try:
                corrected_url = self._correct_unesdoc_url(url)
                unesdoc_id = self._extract_unesdoc_id_from_url(corrected_url)
                ret.append(
                    WeLearnDocument(
                        url=corrected_url,
                        corpus=self.corpus,
                        external_id=unesdoc_id,
                    )
                )
            except ValueError as e:
                logger.error(f"Error processing URL {url}: {e}")
                continue

        return ret
