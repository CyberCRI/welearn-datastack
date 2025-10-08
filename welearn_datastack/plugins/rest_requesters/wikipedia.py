import logging
import re
from typing import List, Tuple

import requests  # type: ignore
from wikipediaapi import Wikipedia, WikipediaPage, WikipediaPageSection  # type: ignore

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.text_stat_utils import (
    predict_duration,
    predict_readability,
)

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"

SECTIONS_BLACKLIST = {
    "fr": [
        "Notes et références",
        "Liens externes",
        "Voir aussi",
        "Références",
        "Bibliographie",
        "Annexes",
        "Distribution",
        "Articles connexes",
        "Fiche technique",
        "Sources",
        "Lien externe",
        "Notes",
        "Source",
        "Article connexe",
    ],
    "en": [
        "References",
        "Other websites",
        "Related pages",
        "Notes",
        "Further reading",
        "Bibliography",
        "Sources",
        "More reading",
        "External links",
        "See also",
        "Articles",
    ],
}

logger = logging.getLogger(__name__)


def get_sections(sections: List[WikipediaPageSection], lang: str, level=0):
    contents = {}
    for s in sections:
        if s.title not in SECTIONS_BLACKLIST[lang]:
            contents[s.title] = s.text
        contents = contents | get_sections(s.sections, lang, level + 1)
    return contents


class WikipediaCollector(IPluginRESTCollector):
    related_corpus = "wikipedia"

    def __init__(self):
        super().__init__()

    def _get_article_content(self, url: str) -> ScrapedWeLearnDocument:
        """
        Get Wikipedia article text content from its url
        :param url: Wikipedia article URL
        :return: ScrapedWeLearnDocument
        """
        logger.info("Getting text content for url : '%s'", url)

        lang = re.match(r"https://([a-z]{2})", url)[0][-2:]  # type: ignore
        wiki_wiki = Wikipedia(USER_AGENT, lang)

        page: WikipediaPage | None = None
        sections: dict | None = None
        for attempt in range(5):
            try:
                page = wiki_wiki.page(title=url.split("/")[-1])
                sections = get_sections(page.sections, lang)
                break
            except requests.exceptions.ReadTimeout:
                logger.warning(
                    "Attempt %s/5 to get text content for url '%s' failed",
                    str(attempt + 1),
                    url,
                )

        if not page or not sections:
            raise ValueError(
                f"Failed to retrieve page content for URL: {url} after 5 attempts"
            )

        doc_url = url
        doc_title = page.title
        doc_lang = lang
        doc_desc = page.summary
        doc_content = " ".join(
            [doc_desc] + [" ".join([k, v]) for (k, v) in sections.items()]
        )
        scraped_document = ScrapedWeLearnDocument(
            document_url=doc_url,
            document_title=doc_title,
            document_lang=doc_lang,
            document_desc=doc_desc,
            document_content=doc_content,
            document_details={},
            document_corpus=self.related_corpus,
        )

        return scraped_document

    def run(
        self, urls_or_external_ids: List[str], is_external_id=False
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        logger.info("Running WikipediaCollector plugin")
        ret: List[ScrapedWeLearnDocument] = []
        error_docs: List[str] = []
        for url in urls_or_external_ids:
            try:
                ret.append(self._get_article_content(url))
            except Exception as e:
                logger.exception(
                    "Error while trying to get contents for url,\n url: '%s' \nError: %s",
                    url,
                    e,
                )
                error_docs.append(url)
                continue
        logger.info(
            "WikipediaCollector plugin finished, %s urls successfully processed",
            len(ret),
        )
        return ret, error_docs
