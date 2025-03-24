import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from welearn_datastack.collectors.oe_books_collector import OpenEditionBooksURLCollector
from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.plugins.scrapers import OpenEditionBooksCollector


class MockResponse:
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        pass


class TestOpenEditionBooksURLCollector(unittest.TestCase):
    def setUp(self):
        self.xml_file_path = Path(__file__).parent / "resources/oe_mets_test.xml"
        self.rss_feed = "https://example.com/feed"
        self.feed_content = open(
            Path(__file__).parent / "resources/oe_books_rss.xml"
        ).read()

        self.url_list = [
            "https://books.openedition.org/examplepub0/0",
            "https://books.openedition.org/examplepub0/1",
            "https://books.openedition.org/examplepub0/2",
            "https://books.openedition.org/examplepub0/3",
            "https://books.openedition.org/examplepub0/4",
            "https://books.openedition.org/examplepub1/5",
            "https://books.openedition.org/examplepub1/6",
            "https://books.openedition.org/examplepub1/7",
            "https://books.openedition.org/examplepub1/8",
            "https://books.openedition.org/examplepub1/9",
        ]

    def test__get_descriptive_metadata_sections(self):
        xml_to_test = self.xml_file_path.read_text()
        collector = OpenEditionBooksURLCollector("example.org", "oe_books")
        ret = collector._get_descriptive_metadata_sections(xml_to_test)
        self.assertEqual(len(ret), 9)
        self.assertDictEqual(
            ret[0],
            {
                "type": "book",
                "rights": "https://creativecommons.org/licenses/by/4.0/",
                "access_rights": "info:eu-repo/semantics/openAccess",
                "url": "https://books.openedition.org/examplepub0/0",
            },
        )

    def test__is_open_access(self):
        xml_to_test = self.xml_file_path.read_text()
        collector = OpenEditionBooksCollector()
        self.assertTrue(collector._is_open_access(XMLExtractor(xml_to_test)))

        xml_negative_content = xml_to_test.replace(
            "info:eu-repo/semantics/openAccess",
            "info:eu-repo/semantics/restrictedAccess",
        )
        self.assertFalse(collector._is_open_access(XMLExtractor(xml_negative_content)))

    @patch("welearn_datastack.collectors.oe_books_collector.get_new_https_session")
    @patch("welearn_datastack.collectors.oe_books_collector.RssURLCollector.collect")
    def test_collect_book_not_accessible(
        self, mock_rss_collector, mock_get_new_http_session
    ):

        xml_content = self.xml_file_path.open().read()

        xml_content = xml_content.replace(
            "info:eu-repo/semantics/openAccess",
            "info:eu-repo/semantics/restrictedAccess",
        )

        mock_rss_collector.return_value = [WeLearnDocument(url=self.url_list[0])]

        mock_session = Mock()
        mock_get_new_http_session.return_value = mock_session

        mock_session.get.return_value = MockResponse(xml_content, 200)
        mock_rss_collector.return_value = [WeLearnDocument(url=self.url_list[0])]

        collector = OpenEditionBooksURLCollector(
            self.rss_feed, Corpus(source_name="oe_books")
        )
        collected = collector.collect()

        self.assertEqual(len(collected), 0)

    @patch("welearn_datastack.collectors.oe_books_collector.get_new_https_session")
    @patch("welearn_datastack.collectors.oe_books_collector.RssURLCollector.collect")
    def test_collect_book_accessible_no_chapters(
        self, mock_rss_collector, mock_get_new_http_session
    ):

        xml_content = self.xml_file_path.open().read()
        cut_place = xml_content.find('<mets:dmdSec ID="MD_OB_examplepub0_8078">')

        xml_content = xml_content[
            :cut_place
        ]  # Cut the xml content to have only one book and 0 chapters

        mock_rss_collector.return_value = [WeLearnDocument(url=self.url_list[0])]

        mock_session = Mock()
        mock_get_new_http_session.return_value = mock_session

        mock_session.get.return_value = MockResponse(xml_content, 200)
        mock_rss_collector.return_value = [WeLearnDocument(url=self.url_list[0])]

        collector = OpenEditionBooksURLCollector(
            self.rss_feed, Corpus(source_name="oe_books")
        )
        collected = collector.collect()

        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0].url, self.url_list[0])

    @patch("welearn_datastack.collectors.oe_books_collector.get_new_https_session")
    @patch("welearn_datastack.collectors.oe_books_collector.RssURLCollector.collect")
    def test_collect_book_accessible_license_unauthorized(
        self, mock_rss_collector, mock_get_new_http_session
    ):

        xml_content = self.xml_file_path.open().read()

        xml_content = xml_content.replace(
            "<dcterms:rights>https://creativecommons.org/licenses/by/4.0/</dcterms:rights>",
            "<dcterms:rights>All rights reserved</dcterms:rights>",
        )

        mock_rss_collector.return_value = [WeLearnDocument(url=self.url_list[0])]

        mock_session = Mock()
        mock_get_new_http_session.return_value = mock_session

        mock_session.get.return_value = MockResponse(xml_content, 200)
        mock_rss_collector.return_value = [WeLearnDocument(url=self.url_list[0])]

        collector = OpenEditionBooksURLCollector(
            self.rss_feed, Corpus(source_name="oe_books")
        )
        collected = collector.collect()

        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0].url, self.url_list[0])

    @patch("welearn_datastack.collectors.oe_books_collector.get_new_https_session")
    @patch("welearn_datastack.collectors.oe_books_collector.RssURLCollector.collect")
    def test_collect_book_accessible_license_authorized(
        self, mock_rss_collector, mock_get_new_http_session
    ):

        xml_content = self.xml_file_path.open().read()
        mock_session = Mock()
        mock_get_new_http_session.return_value = mock_session

        mock_session.get.return_value = MockResponse(xml_content, 200)
        mock_rss_collector.return_value = [WeLearnDocument(url=self.url_list[0])]

        # mock_get_new_http_session.side_effect = [MockResponse(xml_content, 200)]

        collector = OpenEditionBooksURLCollector(
            self.rss_feed, Corpus(source_name="oe_books")
        )
        collected = collector.collect()

        self.assertEqual(len(collected), 7)

        collected_url = [doc.url for doc in collected]
        wanted_urls = [
            "https://books.openedition.org/examplepub0/8078",
            "https://books.openedition.org/examplepub0/8068",
            "https://books.openedition.org/examplepub0/8083",
            "https://books.openedition.org/examplepub0/8098",
            "https://books.openedition.org/examplepub0/8073",
            "https://books.openedition.org/examplepub0/8093",
            "https://books.openedition.org/examplepub0/8088",
        ]

        collected_url.sort()
        wanted_urls.sort()
        self.assertListEqual(collected_url, wanted_urls)
