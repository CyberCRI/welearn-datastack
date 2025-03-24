import csv
import logging
from datetime import datetime
from typing import Dict, Generator, List

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.interface import IPluginCSVReader

logger = logging.getLogger(__name__)

eq_month: Dict[str, str] = {
    "janvier": "01",
    "février": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "août": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "décembre": "12",
}


class CSVFranceCultureCollector(IPluginCSVReader):
    """
    This class is a plugin to read CSV files from france_culture corpus
    """

    related_corpus = "csv_france_culture"

    def __init__(self):
        super().__init__()

    @staticmethod
    def _prepare_date(input_date: str) -> str:
        """
        Prepare date to be converted to timestamp (format: dd mm yyyy)
        :param input_date: Date to prepare
        :return: Timestamp
        """
        date: List[str] = input_date.split(" ")

        if len(date) != 4:
            logger.error("This date : %s cannot be scraped", input_date)
            return ""
        try:
            date_almost_prepared: str = (
                date[1] + "-" + eq_month.get(date[2].lower(), "01") + "-" + date[3]
            )
            date_struct = datetime.strptime(date_almost_prepared, "%d-%m-%Y")
            return str(date_struct.timestamp())
        except ValueError:
            logger.error("This date : %s cannot be scraped", input_date)
            return ""

    def _get_details_from_line(self, line: dict) -> dict[str, str]:
        """
        Get details from a csv line
        :param line: CSV line
        :return: Details
        """
        details: dict[str, str] = {
            "duration": line.get("duration", ""),
            "date": self._prepare_date(line.get("date", "")),
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
            document_lang="fr",
            document_content=line.get("content", ""),
            document_desc=line.get("description", ""),
            document_corpus="france_culture",
            document_details=self._get_details_from_line(line),
        )

        return current
