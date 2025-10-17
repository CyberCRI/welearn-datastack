import logging
from typing import Any

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.interface import IPluginCSVReader

logger = logging.getLogger(__name__)


class CSVConversationCollector(IPluginCSVReader):
    """
    This class is a plugin to read CSV files from conversation corpus
    """

    related_corpus = "csv_conversation"

    def __init__(self):
        super().__init__()

    @staticmethod
    def _get_details_from_line(line: dict) -> dict[str, str]:
        """
        Get details from a csv line
        :param line: CSV line
        :return: Details
        """
        raw_authors = line.get("author", "").split(",")
        authors = [{"name": author.strip(), "misc": ""} for author in raw_authors]
        details: dict[str, Any] = {
            "duration": line.get("duration", ""),
            "readability": line.get("readability", ""),
            "authors": authors,
            "source": line.get("source", ""),
        }
        return details

    def _convert_csv_line_to_welearndoc(self, line: dict) -> ScrapedWeLearnDocument:
        """
        Convert a csv line to a ScrapedWeLearnDocument
        :param line: CSV line
        :return: ScrapedWeLearnDocument
        """

        if not line.get("url", None):
            raise KeyError("This line : '%s' cannot be scraped", str(line))

        content = line.get("content", "")
        if not content:
            raise KeyError("This line : '%s' cannot be scraped", str(line))

        lang = line.get("lang", "")
        if not lang:
            raise KeyError("This line : '%s' cannot be scraped", str(line))

        desc = line.get("description", "")
        if not desc:
            raise KeyError("This line : '%s' cannot be scraped", str(line))

        title = line.get("title", "")
        if not title:
            raise KeyError("This line : '%s' cannot be scraped", str(line))

        current = ScrapedWeLearnDocument(
            document_title=title,
            document_url=line.get("url", ""),
            document_lang=lang,
            document_content=content,
            document_desc=desc,
            document_corpus="conversation",
            document_details=self._get_details_from_line(line),
        )

        return current
