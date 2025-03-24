import logging
import re
from typing import Dict, List

from welearn_datastack.collectors.rss_collector import RssURLCollector
from welearn_datastack.constants import (
    AUTHORIZED_LICENSES,
    HEADERS,
    MD_OE_BOOKS_BASE_URL,
)
from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.data.url_collector import URLCollector
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.utils_.http_client_utils import get_new_https_session

logger = logging.getLogger(__name__)

local_headers = HEADERS.copy()

OPEN_ACCESS_NAME = [
    "Open Access".lower(),
    "Open Access Freemium".lower(),
    "Accès ouvert tout format".lower(),
    "Accès ouvert freemium".lower(),
    "Accès ouvert".lower(),
]


class OpenEditionBooksURLCollector(URLCollector):
    def __init__(self, feed_url: str, corpus: Corpus | None) -> None:
        self.feed_url = feed_url
        self.corpus = corpus

    def _check_research(self, start_tag, end_tag, xml_str):
        pre_ret = re.search(f"{start_tag}(.*?){end_tag}", xml_str, re.DOTALL)
        if pre_ret:
            return pre_ret.group(1)
        return None

    @staticmethod
    def _get_descriptive_metadata_sections(xml_content: str) -> List[Dict[str, str]]:
        """
        :param xml_content: The content of the METS file.
        :return: A list of dictionaries containing the type, rights and access rights of the book.
        """
        ret = []
        root_extractor = XMLExtractor(xml_content)
        dmd_sections = root_extractor.extract_content("mets:dmdSec")
        for dmd in dmd_sections:
            try:
                # Critical section
                dmd_extractor = XMLExtractor(dmd.content)
                type_ = dmd_extractor.extract_content("dcterms:type")
                rights = dmd_extractor.extract_content("dcterms:rights")
                access_rights = dmd_extractor.extract_content("dcterms:accessRights")
                url = dmd_extractor.extract_content_attribute_filter(
                    tag="dcterms:identifier",
                    attribute_name="scheme",
                    attribute_value="URI",
                )

                current_dmd = {
                    "type": type_[0].content,
                    "rights": rights[0].content,
                    "access_rights": access_rights[0].content,
                    "url": url[0].content,
                }

                ret.append(current_dmd)

            except Exception as e:
                logger.error("Error while extracting dmd: %s", e)
                continue

        return ret

    def collect(self) -> List[WeLearnDocument]:
        """
        Collect the URLs of the books and their chapters.
        :return:
        """
        rss_collector = RssURLCollector(feed_url=self.feed_url, corpus=self.corpus)  # type: ignore
        rss_urls = rss_collector.collect()

        ret: List[WeLearnDocument] = []
        client = get_new_https_session()
        for book_url in rss_urls:
            logger.info("Collecting book: %s", book_url)
            md_id = book_url.url.replace("https://books.openedition.org/", "")
            md_url = MD_OE_BOOKS_BASE_URL.replace("<md_id>", md_id)

            md_res = client.get(url=md_url, headers=HEADERS)
            md_res.raise_for_status()
            md_xml = md_res.content.decode("utf-8")
            dmds = self._get_descriptive_metadata_sections(xml_content=md_xml)

            book_dmd = {}
            for dmd in dmds:
                if dmd["type"].lower() == "book":
                    book_dmd = dmd
                    break

            md_access = book_dmd.get("access_rights", "").lower().split("/")[-1].strip()
            md_license = book_dmd.get("rights", "").lower().strip()

            if md_access.lower() == "openaccess":
                if md_license.lower() in AUTHORIZED_LICENSES:
                    logger.info(
                        "Book is open access and rightful access: %s", book_url.url
                    )

                    chapters_urls = {
                        mdm["url"] for mdm in dmds if mdm["type"].lower() == "chapter"
                    }

                    if len(chapters_urls) == 0:
                        # Weird case where there is no chapters
                        logger.warning("No chapters found for book: %s", book_url.url)
                        ret.append(
                            WeLearnDocument(url=book_url.url, corpus=self.corpus)
                        )
                        continue
                    else:
                        for chapter_url in chapters_urls:
                            logger.info("--Collecting chapter: %s", chapter_url)
                            ret.append(
                                WeLearnDocument(url=chapter_url, corpus=self.corpus)
                            )
                else:
                    logger.info(
                        "Book chapters are not legally usable : %s", book_url.url
                    )
                    ret.append(WeLearnDocument(url=book_url.url, corpus=self.corpus))
                    continue
            else:
                logger.info("Book is not open access: %s", book_url.url)
                continue
        return ret
