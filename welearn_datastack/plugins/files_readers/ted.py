import csv
import logging
import sys
from typing import Any, Generator, List

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import LocalModelsExceptions
from welearn_datastack.plugins.interface import IPluginCSVReader

logger = logging.getLogger(__name__)


class CSVTedCollector(IPluginCSVReader):
    """
    This class is a plugin to read CSV files from ted corpus
    """

    related_corpus = "csv_ted"

    def __init__(self):
        super().__init__()

    @staticmethod
    def _get_details_from_line(line: dict) -> dict[str, str]:
        """
        Get details from a csv line
        :param line: CSV line
        :return: Details
        """
        details: dict[str, Any] = {
            "duration": line.get("duration", ""),
            "authors": [{"name": line.get("speaker", ""), "misc": ""}],
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

        current = ScrapedWeLearnDocument(
            document_title=line["title"],
            document_url=line["url"],
            document_lang=line["lang"],
            document_content=line["content"],
            document_desc=line["description"],
            document_corpus="ted",
            document_details=self._get_details_from_line(line),
        )

        return current
