import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.scrapers.conversation import ConversationCollector


class TestScrapeConversationPlugin(unittest.TestCase):
    def setUp(self) -> None:
        req_page1 = (
            Path(__file__).parent.parent
            / "resources/file_plugin_input/page_conversation.html"
        )
        req_page2 = (
            Path(__file__).parent.parent
            / "resources/file_plugin_input/page_conversation2.html"
        )
        req_page3 = (
            Path(__file__).parent.parent
            / "resources/file_plugin_input/page_conversation3.html"
        )

        with req_page1.open(mode="r") as file1, req_page2.open(
            mode="r"
        ) as file2, req_page3.open(mode="r") as file3:
            self.page_1 = file1.read()
            self.page_2 = file2.read()
            self.page_3 = file3.read()

        self.pages_list = [self.page_1, self.page_2]

        os.environ["SCRAPING_SERVICE_ADRESS"] = "http://example.org/scape"
        self.conversation_scraper = ConversationCollector()

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        self.assertEqual(PluginType.SCRAPE, ConversationCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(ConversationCollector.related_corpus, "conversation")

    @patch("requests.sessions.Session.get")
    def test_plugin_run(self, mock_get):
        class MockResponse:
            def __init__(self, text, status_code):
                self.text = text
                self.status_code = status_code

            def raise_for_status(self):
                pass

        mock_get.side_effect = [MockResponse(text, 200) for text in self.pages_list]

        scraped_docs, error_docs = self.conversation_scraper.run(
            urls=["https://example.org/1", "https://example.org/2"]
        )

        self.assertEqual(len(scraped_docs), 2)
        self.assertEqual(len(error_docs), 0)

    @patch("requests.sessions.Session.get")
    def test_plugin_run_invalid_doc(self, mock_get):
        class MockResponse:
            def __init__(self, text, status_code):
                self.text = text
                self.status_code = status_code

            def raise_for_status(self):
                pass

        mock_get.side_effect = [
            MockResponse(text, 200) for text in [self.page_1, self.page_3]
        ]

        scraped_docs, error_docs = self.conversation_scraper.run(
            urls=["https://example.org/1", "https://example.org/2"]
        )
        self.assertEqual(1, len(scraped_docs))
        self.assertEqual(1, len(error_docs))

    def test_plugin_run_error(self):
        pass
