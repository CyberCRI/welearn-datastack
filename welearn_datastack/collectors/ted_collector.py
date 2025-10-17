from typing import List

import requests  # type: ignore
from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.helpers.feed_helpers import (
    extracted_url_to_url_datastore,
)
from welearn_datastack.constants import TED_API_URL, TED_URL
from welearn_datastack.data.url_collector import URLCollector

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "TE": "Trailers",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
}

payload = [
    {
        "indexName": "newest",
        "params": {
            "attributeForDistinct": "objectID",
            "distinct": 1,
            "facets": ["subtitle_languages", "tags"],
            "highlightPostTag": "__/ais-highlight__",
            "highlightPreTag": "__ais-highlight__",
            "hitsPerPage": 24,
            "maxValuesPerFacet": 500,
            "page": 0,
            "query": "",
            "tagFilters": "",
        },
    }
]


class TedURLCollector(URLCollector):
    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus

    def collect(self) -> List[WeLearnDocument]:
        res = requests.post(
            url=TED_API_URL, json=payload, headers=headers, timeout=(3.05, 15)
        )

        urls = [f'{TED_URL}{h["slug"]}' for h in res.json()["results"][0]["hits"]]

        ret = extracted_url_to_url_datastore(urls=urls, corpus=self.corpus)

        return ret
