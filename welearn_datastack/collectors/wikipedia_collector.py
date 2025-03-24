import logging
from datetime import datetime, timedelta
from itertools import batched
from typing import List, Set

import requests  # type: ignore
import wikipediaapi  # type: ignore
from requests import Session

from welearn_datastack.collectors.helpers.feed_helpers import (
    extracted_url_to_url_datastore,
)
from welearn_datastack.constants import HEADERS, WIKIPEDIA_BASE_URL
from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.data.wikipedia_container import WikipediaContainer
from welearn_datastack.utils_.database_utils import create_specific_batches_quantity
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)


USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"


class WikipediaURLCollector(URLCollector):
    def __init__(
        self,
        corpus: Corpus,
        wikipedia_containers: List[WikipediaContainer],
        nb_batches: int | None = None,
    ) -> None:
        self.corpus = corpus
        self.nb_batches = nb_batches
        self.initial_time = datetime.now()
        self.wikipedia_portals_fr = [c for c in wikipedia_containers if c.lang == "fr"]
        self.wikipedia_categories_en = [
            c for c in wikipedia_containers if c.lang == "en"
        ]

    def get_last_page_titles_added_in_pages_container(
        self, http_client: Session, container_info: WikipediaContainer
    ) -> Set[str]:
        start_time = self.initial_time - timedelta(days=10)

        # Usage of this endpoint https://www.mediawiki.org/wiki/API:Categorymembers
        endpoint = (
            "w/api.php?"
            "action=query"
            "&list=categorymembers&cmtitle=<category_name>"
            "&cmsort=timestamp&cmdir=newer"
            "&format=json&cmprop=ids|title|type"
            "&cmstart=<start_date>"
            "&cmlimit=500"
        )

        container_name = container_info.wikipedia_path
        container_depth_max = container_info.depth
        base_url = WIKIPEDIA_BASE_URL.replace("<lang>", container_info.lang)
        local_endpoint = (
            endpoint.replace("<lang>", container_info.lang)
            .replace("<category_name>", container_name)
            .replace("<start_date>", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        )
        full_url = base_url + local_endpoint
        wiki_ret = http_client.get(full_url, headers=HEADERS)
        cat_members_ret = wiki_ret.json()["query"]["categorymembers"]

        while (
            wiki_ret.json()
            .get("continue", {"cmcontinue": None})
            .get("cmcontinue", None)
        ):
            cmcontinue = (
                wiki_ret.json()
                .get("continue", {"cmcontinue": None})
                .get("cmcontinue", None)
            )
            local_full_url = full_url + f"&cmcontinue={cmcontinue}"
            wiki_ret = http_client.get(local_full_url, headers=HEADERS)
            cat_members_ret.extend(wiki_ret.json()["query"]["categorymembers"])

        pages_titles: Set[str] = set()
        subcats: Set[WikipediaContainer] = set()

        for member in cat_members_ret:
            if member["type"] == "page":
                pages_titles.add(member["title"].replace(" ", "_"))
            elif member["type"] == "subcat":
                if container_depth_max > 0:
                    subcats.add(
                        WikipediaContainer(
                            wikipedia_path=f"{member["title"].replace(" ", "_")}",
                            depth=container_depth_max - 1,
                            lang=container_info.lang,
                        )
                    )

        logger.info(
            f"For the container {container_info} we found {len(pages_titles)} new articles"
        )
        logger.info(
            f"For the container {container_info} we found {len(subcats)} new subcategories"
        )
        for subcat in subcats:
            pages_titles.union(
                self.get_last_page_titles_added_in_pages_container(
                    http_client=http_client, container_info=subcat
                )
            )
        return pages_titles

    @staticmethod
    def get_page_translation(
        http_client: Session, page_title: List[str], from_lang: str, to_lang: str
    ) -> List[str] | None:
        """
        Get the translation of a page from a language to another language
        From this endpoint https://www.mediawiki.org/wiki/API:Langlinks
        :param http_client: HTTP client
        :param page_title: Wikipedia pages titles
        :param from_lang: From which language we start
        :param to_lang: In which language we want
        :return: url of page in the to_lang language or None
        """
        base_url = WIKIPEDIA_BASE_URL.replace("<lang>", from_lang)

        endpoint_part = f"w/api.php?action=query"
        params = {
            "format": "json",
            "prop": "langlinks",
            "titles": "|".join(page_title),
            "formatversion": 2,
            "lllang": to_lang,
        }
        full_url = base_url + endpoint_part
        wiki_ret = http_client.get(full_url, headers=HEADERS, params=params)

        page_translation = wiki_ret.json()["query"]["pages"]
        if len(page_translation) <= 0:
            return None

        ret = []
        for translation in page_translation:
            for langlink in translation.get("langlinks", []):
                if langlink.get("lang", "") == to_lang:
                    ret.append(langlink["title"].replace(" ", "_"))
        return ret

    def collect(self, batch_id: int | None = None) -> List[WeLearnDocument]:

        portals_to_process: List[WikipediaContainer]
        categories_to_process: List[WikipediaContainer]

        if self.nb_batches is None or batch_id is None:
            # Unbatch mode
            portals_to_process = self.wikipedia_portals_fr
            categories_to_process = self.wikipedia_categories_en
        else:
            # Batched mode
            portals_batches: List[List[WikipediaContainer]] = (
                create_specific_batches_quantity(
                    to_batch_list=self.wikipedia_portals_fr,
                    qty_batch=self.nb_batches,
                )
            )
            categories_batches: List[List[WikipediaContainer]] = (
                create_specific_batches_quantity(
                    to_batch_list=self.wikipedia_categories_en,
                    qty_batch=self.nb_batches,
                )
            )
            portals_to_process = portals_batches[batch_id]
            categories_to_process = categories_batches[batch_id]

        http_client = get_new_https_session()
        urls: List[str] = []
        container_to_process = portals_to_process + categories_to_process
        # Process for each portal
        logger.info(f"Processing {len(container_to_process)} containers")
        for container in container_to_process:
            page_titles = self.get_last_page_titles_added_in_pages_container(
                http_client=http_client, container_info=container
            )
            logger.info(f"{len(page_titles)} new pages we're found before translation")

            for sub_batch_page_titles in batched(page_titles, 50):
                translated_titles = self.get_page_translation(
                    http_client=http_client,
                    page_title=list(sub_batch_page_titles),
                    to_lang="en" if container.lang == "fr" else "fr",
                    from_lang=container.lang,
                )
                urls.extend(
                    [
                        f"{WIKIPEDIA_BASE_URL.replace('<lang>', container.lang)}wiki/{pt}"
                        for pt in sub_batch_page_titles
                    ]
                )
                if translated_titles:
                    urls.extend(
                        [
                            f"{WIKIPEDIA_BASE_URL.replace('<lang>', container.lang)}wiki/{tt}"
                            for tt in translated_titles
                        ]
                    )

            logger.info(f"{len(urls)} new pages we're found for now")

        ret = extracted_url_to_url_datastore(
            urls=urls,
            corpus=self.corpus,
        )

        return ret
