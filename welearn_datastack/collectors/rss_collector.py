from typing import List
from urllib.parse import urlparse

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.helpers.feed_helpers import (
    extracted_url_to_url_datastore,
    lines_to_url,
)
from welearn_datastack.constants import HEADERS
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.modules.xml_extractor import XMLExtractor
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

        root = XMLExtractor(content)
        items = root.extract_content("item")

        ret: list[WeLearnDocument] = []

        for item in items:
            item_extractor = XMLExtractor(item.content)
            link_lines = item_extractor.extract_content("link")
            assert len(link_lines) == 1
            url = link_lines[0].content

            if not url.startswith(domain):
                continue

            guid = item_extractor.extract_content("guid")
            if guid:
                guid = guid[0].content
            else:
                guid = None

            ret.append(
                WeLearnDocument(
                    url=url,
                    corpus=self.corpus,
                    external_id=guid,
                )
            )

        return ret
