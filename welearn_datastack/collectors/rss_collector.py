from typing import List
from urllib.parse import urlparse

from welearn_datastack.collectors.helpers.feed_helpers import (
    extracted_url_to_url_datastore,
    lines_to_url,
)
from welearn_datastack.constants import HEADERS
from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session


class RssURLCollector(URLCollector):
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
        res = client.get(url=self.feed_url, headers=HEADERS)
        content = res.content.decode("utf-8")

        # Check if were in articles part
        flag = False

        # Check if link tag was the last thing read
        link_flag = False
        link_lines: List[str] = []

        # Retrieve lines where URL are
        for line in content.split(">"):
            if flag and link_flag:
                link_lines.append(line.strip())
                link_flag = False
            if flag and line.strip().startswith("<link"):
                link_flag = True
            if line.strip().startswith("<item"):
                flag = True

        urls = lines_to_url(domain, link_lines)

        ret = extracted_url_to_url_datastore(urls=urls, corpus=self.corpus)

        return ret
