import csv
import datetime
import logging
from datetime import timezone
from typing import Any, Dict, Generator, List, Tuple

import ijson  # type: ignore

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import NoContent
from welearn_datastack.plugins.interface import IPluginFilesCollector

logger = logging.getLogger(__name__)

explicit_types = {
    "ART": "article",
    "COMM": "communication",
    "COUV": "chapter",
    "THESE": "thesis",
    "OUV": "book",
    "MEM": "dissertation",
    "REPORT": "report",
    "UNDEFINED": "preprint",
}


class JsonHALCollector(IPluginFilesCollector):
    """
    This class is a plugin to read CSV files from hal corpus
    """

    related_corpus = "json_hal"

    def __init__(self):
        super().__init__()

    @staticmethod
    def _convert_hal_date_to_ts(hal_dt: str) -> float | None:
        """
        Convert a HAL date to a timestamp
        :param hal_dt: HAL date
        :return: Timestamp
        """
        only_date = hal_dt.split("T")[0]
        time_format = "%Y-%m-%d"

        if not hal_dt:
            return None
        dt = datetime.datetime.strptime(only_date, time_format)
        dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    def _get_details_from_dict(self, json_dict: dict) -> dict[str, Any]:
        """
        Get details from a JSON dict
        :param json_dict: JSON dict
        :return: Details
        """
        raw_pub_date = json_dict.get("publicationDate_tdate", "")
        raw_prod_date = json_dict.get("producedDate_tdate", "")
        pubdate_timestamp: float | None = None
        prod_date_timestamp: float | None = None
        if raw_pub_date:
            pubdate_timestamp = self._convert_hal_date_to_ts(raw_pub_date)

        if raw_prod_date:
            prod_date_timestamp = self._convert_hal_date_to_ts(raw_prod_date)

        raw_authors: List[str] = json_dict.get("authFullName_s", [])

        details: dict[str, Any] = {
            "docid": json_dict.get("docid", ""),
            "produced_date": prod_date_timestamp,
            "type": explicit_types.get(json_dict.get("docType_s", ""), "UNDEFINED"),
            "publication_date": pubdate_timestamp,
            "authors": [{"name": author, "misc": ""} for author in raw_authors],
        }
        return details

    def _convert_json_dict_to_welearndoc(
        self, json_dict: dict
    ) -> ScrapedWeLearnDocument:
        """
        Convert a json dict to ScrapedWeLearnDocument
        :param json_dict: JSON dict
        :return: ScrapedWeLearnDocument
        """

        url = json_dict.get("uri_s", None)
        if not url:
            raise KeyError("This line : '%s' cannot be scraped, no url", str(json_dict))

        lang_list: List[str] | None = json_dict.get("language_s", None)
        if not lang_list or len(lang_list) == 0:
            raise KeyError(
                "This line : '%s' cannot be scraped, no lang", str(json_dict)
            )
        lang: str = lang_list[0]

        if lang == "und":
            raise KeyError(
                "This line : '%s' cannot be scraped, lang undefined",
                str(json_dict["uri_s"]),
            )

        titles: List[str] | None = json_dict.get("title_s", None)
        if not titles or len(titles) == 0:
            raise KeyError(
                "This line : '%s' cannot be scraped, no titles", str(json_dict["uri_s"])
            )
        title: str = titles[0]

        contents: List[str] | None = json_dict.get("abstract_s", None)
        if not contents or len(contents) == 0:
            raise KeyError(
                "This line : '%s' cannot be scraped, no content",
                str(json_dict["uri_s"]),
            )
        content: str = "".join(contents)
        if content == "absent":
            raise NoContent(
                "This line : '%s' cannot be scraped, content is absent",
                str(json_dict["uri_s"]),
            )

        first_sentence = content.split(".")[0]

        current = ScrapedWeLearnDocument(
            document_title=title,
            document_url=url,
            document_lang=lang,
            document_content=content,
            document_desc=first_sentence.strip() + "...",
            document_corpus="hal",
            document_details=self._get_details_from_dict(json_dict),
        )

        return current

    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        """
        Run the plugin
        :param urls: List of urls to filter
        :return: List of ScrapedWeLearnDocument
        """
        res: List[ScrapedWeLearnDocument] = []
        error_urls: List[str] = []

        # Iterate over files
        for fp in self._files_locations:
            try:
                with fp.open(mode="rb") as fin:
                    # Load each JSON
                    logger.info("Reading file %s", fp)
                    json_docs = ijson.items(fin, "response.docs.item")
                    # Filter lines and convert them to ScrapedWeLearnDocument
                    lines_to_keep, error_lines = self.filter_and_convert_lines(
                        dr=json_docs, urls=urls
                    )
                    res.extend(lines_to_keep)
                    error_urls.extend(error_lines)
                logger.info("File %s closed", fp)
            except Exception as e:
                logger.error("Error when reading file %s: %s", fp, e)
                continue
        return res, error_urls

    def filter_and_convert_lines(
        self, dr: csv.DictReader, urls: List[str]
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        """
        Filter lines and convert them to ScrapedWeLearnDocument
        :param dr: DictReader from CSV
        :param urls: List of urls to filter
        :return: List of ScrapedWeLearnDocument
        """

        res: List[ScrapedWeLearnDocument] = []
        error_urls: List[str] = []

        # Filter lines and convert them to ScrapedWeLearnDocument
        i = 0
        for line in self._filter_file_line(dr=dr, urls=urls, url_label="uri_s"):
            try:
                res.append(self._convert_json_dict_to_welearndoc(json_dict=line))
                if i % 10000 == 0:
                    logger.info("Line %s converted", i)
                i += 1
            except Exception as e:
                logger.error(
                    "This url : %s cannot be scraped : %s",
                    line.get("uri_s", ""),
                    str(e),
                )
                error_urls.append(line.get("uri_s", ""))
        return res, error_urls
