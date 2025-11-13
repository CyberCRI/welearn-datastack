import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.scrapers.plos import PlosCollector


class TestScrapePlosPlugin(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        req_page_content_path1 = (
            Path(__file__).parent.parent / "resources/file_plugin_input/page_plos1.xml"
        )

        with req_page_content_path1.open(mode="r") as file1:
            self.page_content_1 = file1.read()

        self.pages_list = [self.page_content_1]

        os.environ["SCRAPING_SERVICE_ADRESS"] = "http://example.org/scrape"
        self.plos_scraper = PlosCollector()

        details_file_path: Path = (
            Path(__file__).parent.parent
            / "resources/file_plugin_input/details_plos.json"
        )
        with details_file_path.open(mode="r") as file:
            self.awaited_details = json.load(file)

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        self.assertEqual(PluginType.SCRAPE, PlosCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(PlosCollector.related_corpus, "plos")

    @patch("requests.sessions.Session.get")
    def test_plugin_run(self, mock_get) -> None:
        # Simulate a successful scrape with a valid XML response
        class MockResponse:
            def __init__(self, text, status_code):
                self.text = text
                self.status_code = status_code

            def raise_for_status(self):
                pass

        mock_get.side_effect = [MockResponse(text, 200) for text in self.pages_list]

        docs = [
            WeLearnDocument(
                id=1,
                url="https://example.org/plosone/article?id=10.1371/journal.pone.0265511",
            )
        ]
        scraped_docs = self.plos_scraper.run(docs)

        self.assertEqual(len(scraped_docs), 1)

        doc = scraped_docs[0]

        # Check document fields
        self.assertFalse(doc.document.description.split()[0] == "Abstract")
        self.assertEqual(
            doc.document.title,
            "The stress sigma factor σS/RpoS counteracts Fur repression of genes involved in iron and manganese "
            "metabolism and modulates the ionome of Salmonella enterica serovar Typhimurium",
        )
        self.assertEqual(
            "https://example.org/plosone/article?id=10.1371/journal.pone.0265511",
            doc.document.url,
        )
        self.assertTrue(hasattr(doc.document, "lang"))
        self.assertTrue(hasattr(doc.document, "details"))
        self.assertTrue(hasattr(doc.document, "full_content"))
        # Optionally check details content
        details = dict(doc.document.details)
        if "tags" in details:
            del details["tags"]
        if "publication_date" in details:
            del details["publication_date"]
        if "readability" in details:
            del details["readability"]
        if "tags" in self.awaited_details:
            del self.awaited_details["tags"]
        if "publication_date" in self.awaited_details:
            del self.awaited_details["publication_date"]
        if "readability" in self.awaited_details:
            del self.awaited_details["readability"]
        self.assertDictEqual(details, self.awaited_details)

    @patch("requests.sessions.Session.get")
    def test_plugin_run_http_error(self, mock_get):
        # Simulate an HTTP error (e.g., 500)
        class MockResponse:
            def __init__(self):
                self.status_code = 500
                self.text = ""

            def raise_for_status(self):
                raise Exception("HTTP 500 error")

        mock_get.return_value = MockResponse()

        docs = [
            WeLearnDocument(
                id=1,
                url="https://example.org/plosone/article?id=10.1371/journal.pone.0265511",
            )
        ]
        result = self.plos_scraper.run(docs)

        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIsInstance(result[0].document, WeLearnDocument)

    @patch("requests.sessions.Session.get")
    def test_plugin_run_invalid_xml(self, mock_get):
        # Simulate an invalid XML (missing required fields)
        class MockResponse:
            def __init__(self):
                self.status_code = 200
                self.text = "<html><body>No article meta</body></html>"

            def raise_for_status(self):
                pass

        mock_get.return_value = MockResponse()

        docs = [
            WeLearnDocument(
                id=1,
                url="https://example.org/plosone/article?id=10.1371/journal.pone.0265511",
            )
        ]
        result = self.plos_scraper.run(docs)

        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIsInstance(result[0].document, WeLearnDocument)

    @patch("requests.sessions.Session.get")
    def test_plugin_run_empty_input(self, mock_get):
        # Test with empty input list
        result = self.plos_scraper.run([])
        self.assertEqual(result, [])

    def test_generate_api_url(self):
        # Test the API URL generation logic
        awaited_url = "https://example.org/plosone/article/file?id=10.1371/journal.pone.0265511&type=manuscript"
        input_url = (
            "https://example.org/plosone/article?id=10.1371/journal.pone.0265511"
        )
        generated_url = self.plos_scraper._generate_api_url(input_url)
        self.assertEqual(awaited_url, generated_url)
