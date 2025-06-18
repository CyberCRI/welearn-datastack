import logging
from typing import List
from urllib.parse import urlparse, urlunparse

import requests
from requests import Response

from welearn_datastack.constants import HEADERS
from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.exceptions import NotEnoughData
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


class PressBooksURLCollector(URLCollector):
    def __init__(
        self, corpus: Corpus | None, api_key: str, application_id: str, qty_books: int
    ) -> None:
        self.corpus = corpus
        self.algolia_base_url = "https://k0sncqlm4a-dsn.algolia.net"
        self.api_key = api_key
        self.application_id = application_id
        self.qty_books = qty_books

    def collect(self) -> List[WeLearnDocument]:
        """
        Collect the URLs of the books and their chapters.
        :return:
        """
        # Get last books
        logger.info("Getting last book from pressbooks...")
        client = get_new_https_session()
        forged_url = f"{self.algolia_base_url}/1/indexes/prod_pressbooks_directory_by_lastUpdated/browse"
        params = {
            "x-algolia-api-key": self.api_key,
            "x-algolia-application-id": self.application_id,
        }
        body = {
            "hitsPerPage": self.qty_books,
            "attributesToRetrieve": ["url"],
            "filters": "hasInstitutions:true",
        }
        resp_last_books: Response = client.post(
            url=forged_url, params=params, json=body
        )
        resp_last_books.raise_for_status()
        hits = resp_last_books.json().get("hits")
        if not hits:
            raise NotEnoughData("There is no data from pressbooks")

        logger.info(f"Got {len(hits)} main books from pressbooks")

        main_books_url = [hit.get("url") for hit in hits]
        tocs_url = [f"{hit}wp-json/pressbooks/v2/toc" for hit in main_books_url]
        logger.info("Getting TOCs...")
        tocs: list[dict] = []
        for toc_url in tocs_url:
            resp_toc = client.get(toc_url, headers=HEADERS)
            try:
                resp_toc.raise_for_status()
            except requests.exceptions.RequestException as req_e:
                logger.warning(f"Exception while getting {toc_url}: {str(req_e)}")
                continue
            tocs.append(resp_toc.json())
        logger.info(f"Got {len(tocs)} tocs from pressbooks")
        logger.info("Extracting real URL from tocs...")

        preformated_page_urls = []
        for toc in tocs:
            links = toc.get("_links")
            if not links:
                logger.warning("Empty TOC, continue")
                continue
            metadata = links.get("metadata")
            if not links:
                logger.warning("Empty TOC, continue")
                continue
            local_urls: list[str] = [i.get("href") for i in metadata]
            preformated_page_urls.extend(local_urls)

        page_urls = set()
        for url in preformated_page_urls:
            preformat = url.replace("/metadata", "")
            parsed = urlparse(preformat)
            post_id = parsed.path.split("/")[-1]
            book_domain = parsed.path.split("/")[
                1
            ]  # 1st one is empty bc path start with '/'
            # scheme='scheme', netloc='netloc', path='/path;parameters', params='', query='query', fragment='fragment'
            final_url = urlunparse(
                ["https", parsed.netloc, book_domain + "/", "", f"p={post_id}", ""]
            )
            page_urls.add(final_url)
        logger.info(f"There is {len(page_urls)} found in this pressbooks batch")
        ret: list[WeLearnDocument] = []
        for page_url in page_urls:
            local_doc = WeLearnDocument(url=page_url, corpus_id=self.corpus.id)
            ret.append(local_doc)

        return ret
