import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.oe_books_collector import OpenEditionBooksURLCollector
from welearn_datastack.collectors.press_books_collector import PressBooksURLCollector
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.plugins.scrapers import OpenEditionBooksCollector


class MockResponse:
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(self.text)


class TestPressBooksURLCollector(unittest.TestCase):
    def setUp(self):
        self.path_json_algolia_resp = (
            Path(__file__).parent / "resources/pb_algolia_response.json"
        )
        self.content_json_algolia_resp = self.path_json_algolia_resp.read_text()
        self.path_json_toc1 = Path(__file__).parent / "resources/pb_toc1.json"
        self.content_json_toc1 = self.path_json_toc1.read_text()
        self.path_json_toc2 = Path(__file__).parent / "resources/pb_toc2.json"
        self.content_json_toc2 = self.path_json_toc2.read_text()

    @patch("welearn_datastack.collectors.press_books_collector.get_new_https_session")
    def test_collect_book_accessible_license_authorized(
        self, mock_get_new_http_session
    ):
        mock_session = Mock()
        mock_session.post.return_value = MockResponse(
            self.content_json_algolia_resp, 200
        )
        mock_session.get.side_effect = [
            MockResponse(self.content_json_toc1, 200),
            MockResponse(self.content_json_toc2, 200),
        ]
        mock_get_new_http_session.return_value = mock_session

        collector = PressBooksURLCollector(
            corpus=Corpus(source_name="press-books"),
            qty_books=2,
            api_key="such api key",
            application_id="such app id",
        )
        collected = collector.collect()

        self.assertEqual(len(collected), 57)
        awaited_url = "https://ecampusontario.pressbooks.pub/2023prehealth/?p=17"
        awaited_url2 = "https://iu.pressbooks.pub/resourceconveniencestore/?p=181"
        external_ids = [u.external_id for u in collected]
        urls = [u.url for u in collected]
        self.assertIn(awaited_url, urls)
        self.assertIn(awaited_url2, urls)
        self.assertIn(
            "2023prehealth/?p=17",
            external_ids,
        )
        self.assertIn(
            "resourceconveniencestore/?p=181",
            external_ids,
        )
