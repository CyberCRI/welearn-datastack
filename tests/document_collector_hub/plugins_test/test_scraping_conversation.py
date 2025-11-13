import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from welearn_database.data.models import WeLearnDocument

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

        with (
            req_page1.open(mode="r") as file1,
            req_page2.open(mode="r") as file2,
            req_page3.open(mode="r") as file3,
        ):
            self.page_1 = file1.read()
            self.page_2 = file2.read()
            self.page_3 = file3.read()

        self.pages_list = [self.page_1, self.page_2]

        os.environ["SCRAPING_SERVICE_ADRESS"] = "http://example.org/scape"
        self.conversation_scraper = ConversationCollector()

    def test_plugin_type(self):
        self.assertEqual(PluginType.SCRAPE, ConversationCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(ConversationCollector.related_corpus, "conversation")

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run(self, mock_get_session):
        # Mock the HTTPS session and its get method
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            MagicMock(text=text, status_code=200, raise_for_status=lambda: None)
            for text in self.pages_list
        ]
        mock_get_session.return_value = mock_session

        docs = [
            WeLearnDocument(id=1, url="https://example.org/1"),
            WeLearnDocument(id=2, url="https://example.org/2"),
        ]
        result = self.conversation_scraper.run(docs)
        # All documents should be successfully scraped
        self.assertEqual(len(result), 2)
        for doc in result:
            self.assertIsNone(doc.error_info)
            self.assertIsInstance(doc.document, WeLearnDocument)
            self.assertTrue(doc.document.title)
            self.assertTrue(doc.document.description)
            self.assertTrue(doc.document.full_content)
            self.assertIsInstance(doc.document.details, dict)

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_invalid_doc(self, mock_get_session):
        # One valid, one invalid HTML (missing required fields)
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            MagicMock(text=self.page_1, status_code=200, raise_for_status=lambda: None),
            MagicMock(text=self.page_3, status_code=200, raise_for_status=lambda: None),
        ]
        mock_get_session.return_value = mock_session

        docs = [
            WeLearnDocument(id=1, url="https://example.org/1"),
            WeLearnDocument(id=2, url="https://example.org/2"),
        ]
        result = self.conversation_scraper.run(docs)

        # One should succeed, one should fail
        self.assertEqual(len(result), 2)
        success = [r for r in result if r.error_info is None]
        errors = [r for r in result if r.error_info is not None]
        self.assertEqual(len(success), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(success[0].document, WeLearnDocument)
        self.assertIsInstance(errors[0].document, WeLearnDocument)
        self.assertTrue(errors[0].error_info)

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_http_error(self, mock_get_session):
        # Simulate an HTTP error (e.g., 500)
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500 error")
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        docs = [WeLearnDocument(id=1, url="https://example.org/1")]
        result = self.conversation_scraper.run(docs)
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIsInstance(result[0].document, WeLearnDocument)

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_empty_input(self, mock_get_session):
        # Test with empty input list
        result = self.conversation_scraper.run([])
        self.assertEqual(result, [])

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_missing_fields(self, mock_get_session):
        # Simulate HTML missing required fields (e.g., no title)
        html_missing_title = self.page_1.replace("headline", "not_headline")
        mock_session = MagicMock()
        mock_session.get.return_value = MagicMock(
            text=html_missing_title, status_code=200, raise_for_status=lambda: None
        )
        mock_get_session.return_value = mock_session
        docs = [WeLearnDocument(id=1, url="https://example.org/1")]
        result = self.conversation_scraper.run(docs)
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIsInstance(result[0].document, WeLearnDocument)
