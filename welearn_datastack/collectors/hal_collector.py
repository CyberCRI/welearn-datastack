import logging
from datetime import datetime, tzinfo
from typing import List
from zoneinfo import ZoneInfo

import requests  # type: ignore
from requests.adapters import HTTPAdapter  # type: ignore
from urllib3 import Retry
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.constants import HAL_SEARCH_URL, HAL_URL_BASE
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.utils_.scraping_utils import get_url_without_hal_like_versionning

logger = logging.getLogger(__name__)


class HALURLCollector(URLCollector):
    def __init__(self, corpus: Corpus, date_last_insert: int):
        self.corpus = corpus
        self.date_last_insert = date_last_insert

        # Query params : https://api.archives-ouvertes.fr/docs/search/?schema=fields#fields
        self._query_params_doctype_s = (
            "ART+OR+COMM+OR+OUV+OR+COUV+OR+DOUV+OR+OTHER+OR+THESE+OR+HDR+OR+LECTURE"
        )
        self._query_params_fl = f"docid,halId_s,producedDate_tdate"
        self._query_params_wt = "json"
        self._query_params_sort = "producedDate_tdate asc"

    def _generate_api_query(self) -> str:
        """
        Generate the API query to get the HAL documents with correct date format
        :return: the API query to get the HAL documents with correct date format
        """
        str_format_date_iso = "%Y-%m-%dT%H:%M:%SZ"
        formated_date: str = datetime.fromtimestamp(
            self.date_last_insert, tz=ZoneInfo("GMT")
        ).strftime(str_format_date_iso)

        return f"producedDate_tdate:[{formated_date} TO NOW]"

    def _get_json_hal_api(self) -> List[dict]:
        """
        Get the JSON from the HAL API with the correct query
        :return: JSON from the HAL API with the correct query
        """
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "TE": "Trailers",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
        }

        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)

        http_client = requests.Session()
        http_client.mount("https://", adapter)

        response = http_client.get(
            HAL_SEARCH_URL,
            params={
                "q": self._generate_api_query(),
                "doctype_s": self._query_params_doctype_s,
                "fl": self._query_params_fl,
                "wt": self._query_params_wt,
                "sort": self._query_params_sort,
            },
            headers=headers,
        )
        json_req = response.json()
        docs: List = json_req["response"]["docs"]
        return docs

    def collect(self) -> List[WeLearnDocument]:
        ret = []
        json_content = self._get_json_hal_api()
        urls = []
        for doc in json_content:
            urls.append(HAL_URL_BASE + doc["halId_s"])

        for url in urls:
            if not url.startswith("https"):
                continue
            ret.append(
                WeLearnDocument(
                    url=get_url_without_hal_like_versionning(url),
                    corpus=self.corpus,
                )
            )
        return ret
