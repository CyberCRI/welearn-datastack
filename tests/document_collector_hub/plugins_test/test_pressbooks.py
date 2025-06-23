import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.rest_requesters.pressbooks import PressBooksCollector


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError()


class TestPressBooksCollector(TestCase):
    def setUp(self):
        self.collector = PressBooksCollector()
        self.mock_base_path = Path(__file__).parent.parent / "resources"

        with open(self.mock_base_path / "pb_chapter_5_metadata.json") as f:
            self.mock_metadata = json.load(f)

        with open(self.mock_base_path / "pb_chapters.json") as f:
            self.mock_chapters = json.load(f)

    def test_plugin_type(self):
        self.assertEqual(PressBooksCollector.collector_type_name, PluginType.REST)

    def test_plugin_related_corpus(self):
        self.assertEqual(PressBooksCollector.related_corpus, "press-books")

    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.get_new_https_session")
    def test_run_success(self, mock_get_session):
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        def mock_get(url, *args, **kwargs):
            if url.endswith("/chapters"):
                return MockResponse(self.mock_chapters)
            elif url.endswith("/chapters/5/metadata/"):
                return MockResponse(self.mock_metadata)
            else:
                return MockResponse([], 404)

        mock_session.get.side_effect = mock_get

        urls = ["https://wtcs.pressbooks.pub/communications/?p=5"]
        collected_docs, error_docs = self.collector.run(urls)

        self.assertEqual(len(collected_docs), 1)
        doc = collected_docs[0]
        self.assertEqual(doc.document_title, self.mock_metadata["name"])
        self.assertTrue(
            doc.document_content.startswith(
                "Chapter 1: Introduction to Communication Situations"
            )
        )
        self.assertEqual(
            doc.document_details["license"], self.mock_metadata["license"]["url"]
        )
        self.assertEqual(doc.document_details["authors"][0]["name"], "Jane Doe")
        self.assertEqual(doc.document_details["editors"][0]["name"], "John Smith")
        self.assertEqual(doc.document_details["publisher"], "WisTech Open")
        self.assertEqual(doc.document_details["type"], "chapters")

    def test__extract_three_first_sentences(self):
        text = "This is one. This is two. This is three. This is four."
        result = self.collector._extract_three_first_sentences(text)
        self.assertEqual(result, "This is one. This is two. This is three.")

    def test__extract_books_main_url(self):
        urls = [
            "https://example.com/book/?p=42",
            "https://example.com/book/?p=99",
        ]
        result = self.collector._extract_books_main_url(urls)
        self.assertIn("https://example.com/book/", result)
        self.assertIn(42, result["https://example.com/book/"])
        self.assertIn(99, result["https://example.com/book/"])

    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.get_new_https_session")
    def test_run_unauthorized_license(self, mock_get_session):
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Modifier la licence pour une non autorisée
        bad_metadata = self.mock_metadata.copy()
        bad_metadata["license"]["url"] = "http://unauthorized.license.org"

        def mock_get(url, *args, **kwargs):
            if url.endswith("/chapters"):
                return MockResponse(self.mock_chapters)
            elif url.endswith("/chapters/5/metadata/"):
                return MockResponse(bad_metadata)
            return MockResponse([], 404)

        mock_session.get.side_effect = mock_get

        urls = ["https://wtcs.pressbooks.pub/communications/?p=5"]
        collected_docs, error_docs = self.collector.run(urls)

        self.assertEqual(len(collected_docs), 0)
        self.assertEqual(len(error_docs), 1)
        self.assertTrue(
            "https://wtcs.pressbooks.pub/communications/?p=5" in error_docs[0]
        )

    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.get_new_https_session")
    def test_run_http_error_on_container(self, mock_get_session):
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Simuler une erreur 500 sur les containers
        def mock_get(url, *args, **kwargs):
            if "chapters" in url:
                return MockResponse({}, status_code=500)
            return MockResponse([], 404)

        mock_session.get.side_effect = mock_get

        urls = ["https://wtcs.pressbooks.pub/communications/?p=5"]
        collected_docs, error_docs = self.collector.run(urls)

        self.assertEqual(collected_docs, [])
        self.assertEqual(error_docs, [])
