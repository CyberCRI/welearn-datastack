from unittest import TestCase

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.exceptions import InvalidPluginType, PluginNotFoundError
from welearn_datastack.modules import collector_selector
from welearn_datastack.plugins.interface import (
    IPluginRESTCollector,
    IPluginScrapeCollector,
)


class TestPluginRest(IPluginRESTCollector):
    related_corpus: str = "test_rest"

    def run(self, docs: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        res: list[WrapperRetrieveDocument] = []
        return res


class TestPluginScrape(IPluginScrapeCollector):
    related_corpus: str = "test_scrape"

    def run(self, docs: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        res: list[WrapperRetrieveDocument] = []
        return res


class TestPluginType(IPluginScrapeCollector):
    related_corpus: str = "invalid_type"

    def run(self, docs: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        res: list[WrapperRetrieveDocument] = []
        return res


class InvalidPluginRest(IPluginRESTCollector):
    related_corpus: str = "another_corpus"
    collector_type_name = "invalid_type"  # type: ignore

    def run(self, docs: list[WeLearnDocument]) -> list[WrapperRetrieveDocument]:
        res: list[WrapperRetrieveDocument] = []
        return res


class TestSelectCollector(TestCase):
    def setUp(self) -> None:
        # Mock the plugins list
        collector_selector.plugins_rest_list = [
            TestPluginRest,  # type: ignore
            TestPluginScrape,  # type: ignore
            InvalidPluginRest,  # type: ignore
        ]

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
