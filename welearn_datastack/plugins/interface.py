import csv
import logging
import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator, List, Tuple

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.utils_.virtual_environement_utils import load_dotenv_local

logger = logging.getLogger(__name__)


def get_list_of_related_env_vars(class_name: str, suffix: str) -> List[str]:
    """
    Get list of related env vars
    :param class_name: Classname of the plugin
    :param suffix: String suffix of the env var
    :return: List of related env vars
    """
    res: List[str] = []
    load_dotenv_local()

    for k, v in os.environ.items():
        if k.startswith(f"{class_name.upper()}_{suffix.upper()}"):
            res.append(v)
    return res


class IPlugin:
    collector_type_name: PluginType
    related_corpus: str

    @abstractmethod
    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        pass


class IPluginFilesCollector(IPlugin, ABC):
    collector_type_name: PluginType = PluginType.FILES
    _resource_folder_root: Path = Path(f"../../plugins_resources/")
    resource_files_names: List[str]

    def __init__(self) -> None:
        self._files_locations: List[Path] = []
        self.resource_files_names: List[str] = []

        if os.environ.get("PLUGINS_RESOURCES_FOLDER_ROOT", None):
            plugins_resources_folder_root: str = os.environ.get(
                "PLUGINS_RESOURCES_FOLDER_ROOT", ""
            )
            self._resource_folder_root = Path(plugins_resources_folder_root)

        # Get list of related env vars and append to resource_files_names
        for var in get_list_of_related_env_vars(
            class_name=type(self).__name__, suffix="FILE_NAME"
        ):
            self.resource_files_names.append(var)

        # Create the files locations
        for file_name in self.resource_files_names:
            self._files_locations.append(
                self._resource_folder_root / type(self).__name__ / file_name
            )

    @staticmethod
    def _filter_file_line(
        dr: csv.DictReader | List[Dict[str, Any]],
        urls: List[str],
        url_label: str = "url",
    ) -> Generator[dict, None, None]:
        """
        Filter csv line
        :param dr: DictReader from CSV
        :param urls: List of urls to filter
        :param url_label: Label of the url location in file (column or field)
        :return: Generator of filtered lines
        """
        for line in dr:  # type: ignore
            if line.get(url_label) in urls:
                yield line


class IPluginRESTCollector(IPlugin, ABC):
    collector_type_name: PluginType = PluginType.REST


class IPluginScrapeCollector(IPlugin, ABC):
    collector_type_name: PluginType = PluginType.SCRAPE

    @staticmethod
    def _clean_str(string: str) -> str:
        """
        Clean string from \n, \t, \r and strip it
        Example : "Hello\n\t\r" -> "Hello"

        :param string: String to clean
        :return: Cleaned string
        """
        return re.sub(r"([\n\t\r])", "", string).strip()


class IPluginCSVReader(IPluginFilesCollector, ABC):
    def run(self, urls: List[str]) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        """
        Run the plugin
        :param urls: List of urls to filter
        :return: List of ScrapedWeLearnDocument
        """
        logger.info("Running plugin %s", type(self).__name__)
        res: List[ScrapedWeLearnDocument] = []
        error_urls: List[str] = []

        csv.field_size_limit(sys.maxsize)

        # Iterate over files
        for fp in self._files_locations:
            logger.info("File found: %s", fp)
            with fp.open(mode="r") as fin:
                # Read each file as dict
                logger.info("Reading file: %s", fp)
                dr = csv.DictReader(fin, delimiter=";", quotechar='"')
                lines_to_keep, error_lines = self.filter_and_convert_lines(
                    dr=dr, urls=urls
                )
                res.extend(lines_to_keep)
                error_urls.extend(error_lines)
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
        for line in self._filter_file_line(dr=dr, urls=urls):
            try:
                logger.info("Converting line: %s", line.get("url", ""))
                res.append(self._convert_csv_line_to_welearndoc(line=line))
            except Exception as e:
                error_urls.append(line.get("url", ""))
                logger.error("Error when converting line: %s", e)
                logger.error("This url : %s cannot be scraped", line.get("url"))
        return res, error_urls

    @abstractmethod
    def _convert_csv_line_to_welearndoc(self, line: dict) -> ScrapedWeLearnDocument:
        """
        Convert a csv line to a ScrapedWeLearnDocument
        :param line: CSV line
        :return: ScrapedWeLearnDocument
        """
        pass
