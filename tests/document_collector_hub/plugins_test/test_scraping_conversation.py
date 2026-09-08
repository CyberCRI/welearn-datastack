import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from bs4 import BeautifulSoup
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.exceptions import NotExpectedMoreThanOneItem
from welearn_datastack.plugins.scrapers.conversation import (
    ConversationCollector,
    format_news_keywords,
)


class FakeResponse:
    """Minimal Response-like object used by mocked HTTP sessions."""

    def __init__(
        self, text: str = "", status_code: int = 200, error: Exception | None = None
    ):
        self.text = text
        self.status_code = status_code
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error


class TestScrapeConversationPlugin(unittest.TestCase):
    def setUp(self) -> None:
        base_path = Path(__file__).parent.parent / "resources/file_plugin_input"
        with (
            (base_path / "page_conversation.html").open(mode="r") as file_1,
            (base_path / "page_conversation2.html").open(mode="r") as file_2,
            (base_path / "page_conversation3.html").open(mode="r") as file_3,
        ):
            self.page_1 = file_1.read()
            self.page_2 = file_2.read()
            self.page_3 = file_3.read()

        os.environ["SCRAPING_SERVICE_ADRESS"] = "http://example.org/scrape"
        self.conversation_scraper = ConversationCollector()

    def test_plugin_type(self):
        self.assertEqual(PluginType.SCRAPE, ConversationCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(ConversationCollector.related_corpus, "conversation")

    def test_format_news_keywords(self):
        self.assertEqual(format_news_keywords(None), [])
        self.assertEqual(
            format_news_keywords("science, environment, engineering"),
            ["science", "environment", "engineering"],
        )
        self.assertEqual(format_news_keywords("single-keyword"), ["single-keyword"])

    def test_retrieve_lang_from_js_script(self):
        soup = BeautifulSoup(self.page_1, "html.parser")
        scripts = soup.find_all("script")
        self.assertEqual(
            self.conversation_scraper._retrieve_lang_from_js_script(scripts),
            "fr",
        )

    def test_retrieve_lang_from_js_script_no_match(self):
        soup = BeautifulSoup(
            "<html><body><script>const x='en';</script></body></html>", "html.parser"
        )
        scripts = soup.find_all("script")
        self.assertEqual(
            self.conversation_scraper._retrieve_lang_from_js_script(scripts),
            "",
        )

    def test_get_document_details_full_page(self):
        soup = BeautifulSoup(self.page_1, "html.parser")
        details = self.conversation_scraper._get_document_details(soup)

        self.assertEqual(
            sorted(details.keys()),
            [
                "authors",
                "commissioning-region",
                "news_keywords",
                "publication_date",
                "update_date",
            ],
        )
        author_names = [author["name"] for author in details["authors"]]
        self.assertGreaterEqual(len(details["authors"]), 2)
        self.assertIn("Srinivas Garimella", author_names)
        self.assertIn("Matthew T. Hughes", author_names)
        self.assertTrue(
            any(
                "Professor of Mechanical Engineering" in author["misc"]
                for author in details["authors"]
            )
        )
        self.assertIn("UN-explication", details["news_keywords"])
        self.assertEqual(details["commissioning-region"], "fr")

        expected_publication_ts = datetime.strptime("20230906", "%Y%m%d").timestamp()
        expected_update_ts = datetime.strptime(
            "2024-02-06T12:56:31Z", "%Y-%m-%dT%H:%M:%SZ"
        ).timestamp()
        self.assertEqual(details["publication_date"], expected_publication_ts)
        self.assertEqual(details["update_date"], expected_update_ts)

    def test_get_document_details_missing_optional_meta(self):
        html = """
        <html>
          <body>
            <li class='vcard'>
              <span>Ada Lovelace</span>
              <p class='role'>Researcher</p>
            </li>
          </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        details = self.conversation_scraper._get_document_details(soup)

        self.assertEqual(
            details["authors"], [{"name": "Ada Lovelace", "misc": "Researcher"}]
        )
        self.assertEqual(details["news_keywords"], [])
        self.assertIsNone(details["commissioning-region"])
        self.assertIsNone(details["publication_date"])
        self.assertIsNone(details["update_date"])

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_success_two_documents(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            FakeResponse(text=self.page_1, status_code=200),
            FakeResponse(text=self.page_2, status_code=200),
        ]
        mock_get_session.return_value = mock_session

        docs = [
            WeLearnDocument(id=1, url="https://example.org/212649"),
            WeLearnDocument(id=2, url="https://example.org/209538"),
        ]

        result = self.conversation_scraper.run(docs)

        self.assertEqual(len(result), 2)
        for wrapper in result:
            self.assertIsNone(wrapper.error_info)
            self.assertIsNone(wrapper.http_error_code)
            self.assertIsInstance(wrapper.document, WeLearnDocument)
            self.assertTrue(wrapper.document.title)
            self.assertTrue(wrapper.document.description)
            self.assertTrue(wrapper.document.full_content)
            self.assertIsInstance(wrapper.document.details, dict)

        first_doc = result[0].document
        second_doc = result[1].document

        self.assertEqual(first_doc.external_id, 212649)
        self.assertIn("Comment les machines succombent", first_doc.title)
        self.assertIn("Plus il fait chaud", first_doc.description)
        self.assertIn("Les humains ne sont pas les seuls", first_doc.full_content)
        first_author_names = [author["name"] for author in first_doc.details["authors"]]
        self.assertIn("Srinivas Garimella", first_author_names)
        self.assertIn("Matthew T. Hughes", first_author_names)

        self.assertEqual(second_doc.external_id, 209538)
        self.assertIn("Une chasse au", second_doc.title)
        self.assertIn("Des archives font", second_doc.description)
        self.assertIn("Provins", second_doc.description)
        self.assertIn("de creuser au hasard", second_doc.full_content)
        self.assertEqual(len(second_doc.details["authors"]), 1)

        self.assertEqual(mock_session.get.call_count, 2)

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_mixed_valid_and_invalid_html(self, mock_get_session):
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            FakeResponse(text=self.page_1, status_code=200),
            FakeResponse(text=self.page_3, status_code=200),
        ]
        mock_get_session.return_value = mock_session

        docs = [
            WeLearnDocument(id=1, url="https://example.org/212649"),
            WeLearnDocument(id=2, url="https://example.org/209538"),
        ]

        result = self.conversation_scraper.run(docs)

        self.assertEqual(len(result), 2)
        success = [wrapper for wrapper in result if wrapper.error_info is None]
        errors = [wrapper for wrapper in result if wrapper.error_info is not None]

        self.assertEqual(len(success), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Description not found", errors[0].error_info)
        self.assertIsNone(errors[0].http_error_code)

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_http_error_sets_http_error_code(self, mock_get_session):
        http_error = requests.HTTPError("HTTP 500 error")
        response = requests.Response()
        response.status_code = 500
        http_error.response = response

        mock_session = MagicMock()
        mock_session.get.return_value = FakeResponse(
            text="", status_code=500, error=http_error
        )
        mock_get_session.return_value = mock_session

        docs = [WeLearnDocument(id=1, url="https://example.org/500")]
        result = self.conversation_scraper.run(docs)

        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertEqual(result[0].http_error_code, 500)

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_empty_input(self, mock_get_session):
        result = self.conversation_scraper.run([])
        self.assertEqual(result, [])
        mock_get_session.assert_not_called()

    @patch("welearn_datastack.plugins.scrapers.conversation.get_new_https_session")
    def test_plugin_run_missing_title_returns_error(self, mock_get_session):
        html_missing_title = self.page_1.replace(
            'itemprop="headline"', 'itemprop="not_headline"'
        )
        mock_session = MagicMock()
        mock_session.get.return_value = FakeResponse(
            text=html_missing_title, status_code=200
        )
        mock_get_session.return_value = mock_session

        docs = [WeLearnDocument(id=1, url="https://example.org/212649")]
        result = self.conversation_scraper.run(docs)

        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIn("Title not found", result[0].error_info)
        self.assertIsInstance(result[0].document, WeLearnDocument)

    def test_handle_external_id_valid(self):
        doc = WeLearnDocument(
            id=1, url="https://example.org/title-explaining-stuff-123"
        )
        self.assertEqual(self.conversation_scraper.handle_external_id(doc), 123)

    def test_handle_external_id_invalid_raises(self):
        doc = WeLearnDocument(id=1, url="https://example.org/title-explaining-stuff")
        with self.assertRaises(NotExpectedMoreThanOneItem):
            self.conversation_scraper.handle_external_id(doc)
