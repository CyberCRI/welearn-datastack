import csv
import logging
import os
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator, List

from welearn_database.data.models import ErrorRetrieval, WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.enumerations import PluginType
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


class IPlugin(ABC):
    collector_type_name: PluginType
    related_corpus: str

    @abstractmethod
    def run(self, documents: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        pass


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
