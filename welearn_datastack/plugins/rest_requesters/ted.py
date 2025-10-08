import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple, TypedDict

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import NoContent
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import clean_return_to_line
from welearn_datastack.utils_.text_stat_utils import predict_readability

logger = logging.getLogger(__name__)

PROHIBITED_TEXT = ["(Music)", "(Applause)", "(Laughter)"]


# JSON Types
class TEDVideoRelatedJSON(TypedDict):
    description: str
    internalLanguageCode: str
    presenterDisplayName: str
    duration: int
    title: str
    publishedAt: str
    canonicalUrl: str
    type: Dict[str, str]


class TEDTranslationRelatedJSON(TypedDict):
    paragraphs: List[Dict[str, List[Dict[str, str]]]]


# Collector
class TEDCollector(IPluginRESTCollector):
    related_corpus = "ted"

    def __init__(self) -> None:
        self.corpus_name = self.related_corpus
        self.corpus_fix = True
        self.ted_graphql_query: str = """
            query{
              video(id: "<PLACEHOLDER_ID>"){
                description
                internalLanguageCode
                presenterDisplayName
                duration
                title
                publishedAt
                canonicalUrl
                type{
                  name
                }
              }
              translation(language: "en" videoId: "<PLACEHOLDER_ID>"){
                paragraphs{
                  cues{text}
                }
              }
            }
        """

    @staticmethod
    def _extract_ted_ids(urls: List[str]) -> List[str]:
        ted_ids = []
        for url in urls:
            ted_ids.append(url.split("/")[-1])
        return ted_ids

    def _generate_jsons(self, ted_ids: List[str]) -> List[Dict[str, str]]:
        """
        Generate JSONs for API requests
        """
        ret = []
        for _id in ted_ids:
            current_json = {
                "query": self.ted_graphql_query.replace("<PLACEHOLDER_ID>", _id)
            }
            ret.append(current_json)
        return ret

    @staticmethod
    def _concat_content_from_json(
        ted_json_paragraph: List[Dict[str, List[Dict[str, str]]]],
    ) -> str:
        """
        Concatenate content from JSON
        """
        ret = ""
        for paragraph in ted_json_paragraph:
            cues = paragraph["cues"]
            for cue in cues:
                text = cue["text"]
                if text not in PROHIBITED_TEXT:
                    ret += clean_return_to_line(text) + " "
        return ret.strip()

    def _convert_json_dict_to_welearndoc(
        self, ted_content: Dict
    ) -> ScrapedWeLearnDocument:
        """
        Convert JSON to ScrapedWeLearnDocument
        """
        video_related: TEDVideoRelatedJSON = ted_content["data"]["video"]
        translation_related: TEDTranslationRelatedJSON = ted_content["data"][
            "translation"
        ]

        if not video_related or not translation_related:
            raise NoContent("No content found")

        desc = video_related["description"]
        lang = video_related["internalLanguageCode"]
        title = video_related["title"]
        canonical_url = video_related["canonicalUrl"]
        doc_content = self._concat_content_from_json(translation_related["paragraphs"])

        ted_date_format = "%Y-%m-%dT%H:%M:%SZ"
        pubdate = datetime.strptime(video_related["publishedAt"], ted_date_format)
        pubdate.replace(tzinfo=timezone.utc)
        pubdate_ts = pubdate.timestamp()
        document_details = {
            "duration": str(video_related["duration"]),
            "readability": predict_readability(doc_content, lang),
            "authors": [{"name": video_related["presenterDisplayName"], "misc": ""}],
            "publication_date": pubdate_ts,
            "type": video_related.get("type", {}).get("name", ""),
        }

        return ScrapedWeLearnDocument(
            document_title=title,
            document_url=canonical_url,
            document_lang=lang,
            document_content=doc_content,
            document_desc=desc,
            document_corpus=self.corpus_name,
            document_details=document_details,
        )

    @staticmethod
    def _get_ted_content(ted_json: Dict) -> Dict:
        """
        Get content from TED API

        Args:
            ted_json (Dict): JSON for TED API

        Returns:
            Dict: JSON response from TED API
        """
        session = get_new_https_session()
        response = session.post(
            "https://www.ted.com/graphql",
            json=ted_json,
        )
        response.raise_for_status()
        json_response = response.json()
        if json_response.get("errors"):
            raise NoContent("No content found")
        return json_response

    def run(
        self, urls_or_external_ids: List[str], is_external_id=False
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        logger.info("Running TEDCollectorRest plugin")
        ret: List[ScrapedWeLearnDocument] = []
        error_docs: List[str] = []

        try:
            ted_ids = self._extract_ted_ids(urls_or_external_ids)
            json_reqs_for_ted = self._generate_jsons(ted_ids)

            for req in json_reqs_for_ted:
                ret.append(
                    self._convert_json_dict_to_welearndoc(self._get_ted_content(req))
                )

        except Exception as e:
            logger.error("Error while getting content from TED API")
            logger.exception(e)
            for url in urls_or_external_ids:
                error_docs.append(url)

        logger.info(
            "TEDCollector plugin finished, %s urls successfully processed",
            len(ret),
        )
        return ret, error_docs
