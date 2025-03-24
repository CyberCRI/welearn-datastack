import logging

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.interface import IPluginCSVReader

logger = logging.getLogger(__name__)


class CSVWikipediaCollector(IPluginCSVReader):
    """
    This class is a plugin to read CSV files from wikipedia corpus
    """

    related_corpus = "csv_wikipedia"

    def __init__(self):
        super().__init__()

    @staticmethod
    def _get_details_from_line(line: dict) -> dict[str, str]:
        """
        Get details from a csv line
        :param line: CSV line
        :return: Details
        """
        details: dict[str, str] = {
            "duration": line.get("duration", ""),
            "readability": line.get("readability", ""),
            "qid": line.get("qid", ""),
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
            document_title=line.get("title", ""),
            document_url=line.get("url", ""),
            document_lang=line.get("lang", ""),
            document_content=line.get("content", ""),
            document_desc=line.get("summary", ""),
            document_corpus="wikipedia",
            document_details=self._get_details_from_line(line),
        )

        return current
