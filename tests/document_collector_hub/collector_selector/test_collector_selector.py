import csv
import os
from pathlib import Path
from typing import List, Tuple
from unittest import TestCase

from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.exceptions import InvalidPluginType, PluginNotFoundError
from welearn_datastack.modules import collector_selector
from welearn_datastack.plugins.interface import (
    IPlugin,
    IPluginFilesCollector,
    IPluginRESTCollector,
    IPluginScrapeCollector,
)


class TestPluginFiles(IPluginFilesCollector):
    related_corpus: str = "test"

    def __init__(self):
        super().__init__()

    def run(
        self, urls_or_external_ids: List[str], is_external_id=False
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        res: List[ScrapedWeLearnDocument] = []
        errors: List[str] = []
        return res, errors


class TestPluginRest(IPluginRESTCollector):
    related_corpus: str = "test_rest"

    def run(
        self, urls_or_external_ids: List[str], is_external_id=False
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        res: List[ScrapedWeLearnDocument] = []
        errors: List[str] = []
        return res, errors


class TestPluginScrape(IPluginScrapeCollector):
    related_corpus: str = "test_scrape"

    def run(
        self, urls_or_external_ids: List[str], is_external_id=False
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        res: List[ScrapedWeLearnDocument] = []
        errors: List[str] = []
        return res, errors


class TestPluginType(IPluginScrapeCollector):
    related_corpus: str = "invalid_type"

    def run(
        self, urls_or_external_ids: List[str], is_external_id=False
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        res: List[ScrapedWeLearnDocument] = []
        errors: List[str] = []
        return res, errors


class InvalidPluginRest(IPluginRESTCollector):
    related_corpus: str = "another_corpus"
    collector_type_name = "invalid_type"  # type: ignore

    def run(
        self, urls_or_external_ids: List[str], is_external_id=False
    ) -> Tuple[List[ScrapedWeLearnDocument], List[str]]:
        res: List[ScrapedWeLearnDocument] = []
        errors: List[str] = []
        return res, errors


class Test(TestCase):
    def setUp(self) -> None:
        # Mock the plugins list
        collector_selector.plugins_files_list = [
            TestPluginFiles,
            TestPluginRest,  # type: ignore
            TestPluginScrape,  # type: ignore
            InvalidPluginRest,  # type: ignore
        ]

    def test_select_collector_files(self):
        r = collector_selector.select_collector(corpus="test")
        self.assertTrue(isinstance(r, TestPluginFiles))
        self.assertIn(IPluginFilesCollector, type(r).__bases__)

    def test_select_collector_files_path_gen(self) -> None:
        os.environ["TESTPLUGINFILES_FILE_NAME"] = "test.csv"
        os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"] = "./resources/"
        mock_file_path = Path("./resources/TestPluginFiles/test.csv")
        mock_file_path.parent.mkdir(parents=True, exist_ok=True)

        with mock_file_path.open(mode="w") as f:
            pass

        r: IPluginFilesCollector | IPlugin = collector_selector.select_collector(
            corpus="test"
        )

        if not isinstance(r, IPluginFilesCollector):
            raise AssertionError("r is not an instance of IPluginFilesCollector")

        for fp in r._files_locations:
            self.assertTrue(fp.exists())
            self.assertEqual(fp, mock_file_path)

        os.remove(path=mock_file_path.as_posix())
        mock_file_path.parent.rmdir()

    def test_select_collector_rest(self):
        r = collector_selector.select_collector(corpus="test_rest")
        self.assertTrue(isinstance(r, TestPluginRest))
        self.assertIn(IPluginRESTCollector, type(r).__bases__)

    def test_select_collector_scrape(self):
        r = collector_selector.select_collector(corpus="test_scrape")
        self.assertTrue(isinstance(r, TestPluginScrape))
        self.assertIn(IPluginScrapeCollector, type(r).__bases__)

    def test_select_collector_not_found(self):
        with self.assertRaises(PluginNotFoundError):
            collector_selector.select_collector(corpus="test_not_found")

    def test_select_collector_invalid_type(self):
        with self.assertRaises(InvalidPluginType):
            collector_selector.select_collector(corpus="another_corpus")
