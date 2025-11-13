import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.rest_requesters.ted import TEDCollector


class TestAPITedPlugin(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        req_json_content_path1 = (
            Path(__file__).parent.parent / "resources/file_plugin_input/ted_page.json"
        )

        with req_json_content_path1.open(mode="r") as file1:
            self.json_content_1 = json.load(file1)

        self.jsons_list = [
            self.json_content_1,
        ]

        self.ted_scraper = TEDCollector()

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        self.assertEqual(PluginType.REST, TEDCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(TEDCollector.related_corpus, "ted")

    @patch("welearn_datastack.plugins.rest_requesters.ted.get_new_https_session")
    def test_run_successful_document(self, mock_session):
        # Simulate a successful TED API response with valid JSON and all fields
        class MockResponse:
            def __init__(self, json_data, status_code=200):
                self._json = json_data
                self.status_code = status_code

            def raise_for_status(self):
                pass

            def json(self):
                return self._json

        mock_client = unittest.mock.MagicMock()
        mock_client.post.return_value = MockResponse(self.json_content_1)
        mock_session.return_value = mock_client

        doc = WeLearnDocument(id=1, url="https://example.org/4")
        result = self.ted_scraper.run([doc])

        self.assertEqual(len(result), 1)

        ted_doc = result[0]

        self.assertIsNone(getattr(ted_doc, "error_info", None))
        self.assertEqual(
            ted_doc.document.document_url,
            self.json_content_1["data"]["video"]["canonicalUrl"],
        )
        self.assertEqual(
            ted_doc.document.document_title,
            self.json_content_1["data"]["video"]["title"],
        )
        self.assertEqual(
            ted_doc.document.document_desc,
            self.json_content_1["data"]["video"]["description"],
        )
        self.assertIn("duration", ted_doc.document.document_details)
        self.assertIn("authors", ted_doc.document.document_details)
        self.assertIn("publication_date", ted_doc.document.document_details)
        self.assertIn("type", ted_doc.document.document_details)

    @patch("welearn_datastack.plugins.rest_requesters.ted.get_new_https_session")
    def test_run_http_error(self, mock_session):
        # Simulate an HTTP error (e.g. 500)
        mock_client = unittest.mock.MagicMock()

        class MockResponse:
            def raise_for_status(self):
                raise Exception("HTTP error")

            def json(self):
                return {}

        mock_client.post.return_value = MockResponse()
        mock_session.return_value = mock_client

        from welearn_database.data.models import WeLearnDocument

        doc = WeLearnDocument(id=2, url="https://example.org/404")
        result = self.ted_scraper.run([doc])

        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIn("HTTP error", result[0].error_info)
        self.assertEqual(result[0].document.url, "https://example.org/404")

    @patch("welearn_datastack.plugins.rest_requesters.ted.get_new_https_session")
    def test_run_invalid_json_structure(self, mock_session):
        # Simulate a response with invalid JSON structure (missing 'data' or 'video')
        mock_client = unittest.mock.MagicMock()

        class MockResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"unexpected": "structure"}

        mock_client.post.return_value = MockResponse()
        mock_session.return_value = mock_client

        from welearn_database.data.models import WeLearnDocument

        doc = WeLearnDocument(id=3, url="https://example.org/invalid")
        result = self.ted_scraper.run([doc])

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].is_error)

    @patch("welearn_datastack.plugins.rest_requesters.ted.get_new_https_session")
    def test_run_empty_input(self, mock_session):
        # Should return an empty list if no documents are provided
        result = self.ted_scraper.run([])
        self.assertEqual(result, [])

    @patch("welearn_datastack.plugins.rest_requesters.ted.get_new_https_session")
    def test_run_partial_success_and_error(self, mock_session):
        # One valid, one error (simulate HTTP error on second)
        class MockResponse:
            def __init__(self, json_data, status_code=200):
                self._json = json_data
                self.status_code = status_code

            def raise_for_status(self):
                if self.status_code != 200:
                    raise Exception("HTTP error")

            def json(self):
                return self._json

        mock_client = unittest.mock.MagicMock()
        valid_json = self.json_content_1
        mock_client.post.side_effect = [
            MockResponse(valid_json, 200),
            Exception("HTTP error"),
        ]
        mock_session.return_value = mock_client

        from welearn_database.data.models import WeLearnDocument

        doc1 = WeLearnDocument(id=4, url="https://example.org/ok")
        doc2 = WeLearnDocument(id=5, url="https://example.org/fail")
        result = self.ted_scraper.run([doc1, doc2])

        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0].error_info)
        self.assertEqual(
            result[0].document.document_url, valid_json["data"]["video"]["canonicalUrl"]
        )
        self.assertIsNotNone(result[1].error_info)
        self.assertIn("HTTP error", result[1].error_info)
        self.assertEqual(result[1].document.url, "https://example.org/fail")

    def test_concat_content_from_json_empty(self):
        # Should return empty string if paragraphs is empty or None
        self.assertEqual(self.ted_scraper._concat_content_from_json([]), "")
        self.assertEqual(self.ted_scraper._concat_content_from_json(None), "")
