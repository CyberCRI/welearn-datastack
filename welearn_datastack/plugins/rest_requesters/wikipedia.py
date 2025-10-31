import logging
import re
from typing import List

import requests  # type: ignore
from welearn_database.data.models import WeLearnDocument
from wikipediaapi import Wikipedia, WikipediaPage, WikipediaPageSection  # type: ignore

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.plugins.interface import IPluginRESTCollector

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

    def _get_article_content(self, document: WeLearnDocument) -> WeLearnDocument:
        """
        Get Wikipedia article text content from its url
        :param document: Wikipedia article URL
        :return: ScrapedWeLearnDocument
        """
        logger.info("Getting text content for url : '%s'", document)

        lang = re.match(r"https://([a-z]{2})", document.url)[0][-2:]  # type: ignore
        wiki_wiki = Wikipedia(USER_AGENT, lang)

        page: WikipediaPage | None = None
        sections: dict | None = None
        for attempt in range(5):
            try:
                page = wiki_wiki.page(title=document.url.split("/")[-1])
                sections = get_sections(page.sections, lang)
                break
            except requests.exceptions.ReadTimeout:
                logger.warning(
                    "Attempt %s/5 to get text content for url '%s' failed",
                    str(attempt + 1),
                    document,
                )

        if not page or not sections:
            raise ValueError(
                f"Failed to retrieve page content for URL: {document} after 5 attempts"
            )

        document.title = page.title
        document.lang = lang
        document.description = page.summary
        document.full_content = " ".join(
            [page.summary] + [" ".join([k, v]) for (k, v) in sections.items()]
        )

        return document

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running WikipediaCollector plugin")
        ret: List[WrapperRetrieveDocument] = []

        for doc in documents:
            try:
                ret.append(
                    WrapperRetrieveDocument(
                        document=self._get_article_content(doc),
                    )
                )
            except Exception as e:
                logger.exception(
                    "Error while trying to get contents for url,\n url: '%s' \nError: %s",
                    doc.url,
                    e,
                )
                ret.append(
                    WrapperRetrieveDocument(
                        document=doc,
                        error_info=str(e),
                    )
                )
                continue
        logger.info(
            "WikipediaCollector plugin finished, %s urls successfully processed",
            len(ret),
        )
        return ret
