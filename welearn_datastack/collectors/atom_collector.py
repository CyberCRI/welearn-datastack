from typing import List
from urllib.parse import urlparse

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.helpers.feed_helpers import (
    extracted_url_to_url_datastore,
    lines_to_url,
)
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session

url_illegal_characters = ['"', "<", ">"]
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "TE": "Trailers",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
}


class AtomURLCollector(URLCollector):
    def __init__(
        self,
        feed_url: str,
        corpus: Corpus,
    ) -> None:
        self.feed_url = feed_url
        self.corpus = corpus

    def collect(self) -> List[WeLearnDocument]:
        domain = "https://" + urlparse(self.feed_url).netloc
        client = get_new_https_session()
        res = client.get(url=self.feed_url, headers=headers)
        content = res.content.decode("utf-8")

        flag = False
        link_lines: List[str] = []
        for line in content.split("\n"):
            # If we are in the entry section and we find a link
            # The definition, especially "rel" part is empirical
            if flag and line.strip().startswith('<link rel="alternate"'):
                link_lines.append(line.strip())
            if line.strip().startswith("<entry>"):
                flag = True

        urls = lines_to_url(domain, link_lines)

        ret = extracted_url_to_url_datastore(urls=urls, corpus=self.corpus)

        return ret
