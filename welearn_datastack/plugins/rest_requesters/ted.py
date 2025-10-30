import json
import logging
from datetime import datetime, timezone
from typing import Dict, List

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.source_models.ted import (
    Paragraph,
    TEDModel,
    Translation,
    Video,
)
from welearn_datastack.exceptions import NoContent
from welearn_datastack.plugins.interface import IPluginRESTCollector
from welearn_datastack.utils_.http_client_utils import get_new_https_session
from welearn_datastack.utils_.scraping_utils import clean_return_to_line
from welearn_datastack.utils_.text_stat_utils import predict_readability

logger = logging.getLogger(__name__)

PROHIBITED_TEXT = ["(Music)", "(Applause)", "(Laughter)"]


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
    def _extract_ted_ids(ted_docs: list[WeLearnDocument]) -> dict[str, WeLearnDocument]:
        return {ted_doc.url.split("/")[-1]: ted_doc for ted_doc in ted_docs}

    def _generate_json(self, ted_id: str) -> Dict[str, str]:
        """
        Generate JSONs for API requests
        """
        current_json = {
            "query": self.ted_graphql_query.replace("<PLACEHOLDER_ID>", ted_id)
        }
        return current_json

    @staticmethod
    def _concat_content_from_json(
        ted_json_paragraph: list[Paragraph],
    ) -> str:
        """
        Concatenate content from JSON
        """
        if not ted_json_paragraph:
            return ""
        ret = ""

        for paragraph in ted_json_paragraph:
            cues = paragraph.cues
            for cue in cues:
                text = cue.text
                if text not in PROHIBITED_TEXT:
                    ret += clean_return_to_line(text) + " "
        return ret.strip()

    def _update_welearndocument(self, wrapper: WrapperRawData) -> WeLearnDocument:
        """
        Convert JSON to ScrapedWeLearnDocument
        """

        video_related: Video = wrapper.raw_data.data.video
        translation_related: Translation = wrapper.raw_data.data.translation

        if not video_related or not translation_related:
            raise NoContent("No content found")

        desc = video_related.description
        lang = video_related.internalLanguageCode
        title = video_related.title
        canonical_url = video_related.canonicalUrl
        doc_content = self._concat_content_from_json(translation_related.paragraphs)

        ted_date_format = "%Y-%m-%dT%H:%M:%SZ"
        pubdate = datetime.strptime(video_related.publishedAt, ted_date_format)
        pubdate.replace(tzinfo=timezone.utc)
        pubdate_ts = pubdate.timestamp()
        document_details = {
            "duration": str(video_related.duration),
            "readability": predict_readability(doc_content, lang),
            "authors": [{"name": video_related.presenterDisplayName, "misc": ""}],
            "publication_date": pubdate_ts,
            "type": video_related.type.name,
        }

        wrapper.document.document_title = title
        wrapper.document.document_url = canonical_url
        wrapper.document.document_desc = desc
        wrapper.document.document_content = doc_content
        wrapper.document.document_details = document_details

        return wrapper.document

    @staticmethod
    def _get_ted_content(ted_json: Dict) -> TEDModel:
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
        ret = TEDModel.model_validate_json(json.dumps(json_response))
        return ret

    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        logger.info("Running TEDCollectorRest plugin")
        ret: List[WrapperRetrieveDocument] = []

        ted_ids_docs = self._extract_ted_ids(documents)
        for ted_id, doc in ted_ids_docs.items():
            json_req = self._generate_json(ted_id)
            try:
                ted_content = self._get_ted_content(json_req)
                wrapper = WrapperRawData(
                    raw_data=ted_content,
                    document=doc,
                )
                welearn_doc = self._update_welearndocument(wrapper)

                ret.append(WrapperRetrieveDocument(document=welearn_doc))
            except Exception as e:
                logger.error(f"Error processing TED ID {ted_id}")
                logger.exception(e)
                ret.append(
                    WrapperRetrieveDocument(
                        document=doc,
                        error_info=str(e),
                    )
                )

        logger.info(
            "TEDCollector plugin finished, %s urls successfully processed",
            len(ret),
        )
        return ret
