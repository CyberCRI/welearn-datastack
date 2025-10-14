import unittest
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from requests import Session  # type: ignore
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import MD_OE_BOOKS_BASE_URL
from welearn_datastack.exceptions import UnauthorizedLicense
from welearn_datastack.plugins.scrapers.oe_books import OpenEditionBooksCollector


class MockResponse:
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        pass


class TestOpenEditionBooksCollector(unittest.TestCase):
    def setUp(self):
        self.collector = OpenEditionBooksCollector()
        self.mock_session = Mock(spec=Session)
        self.xml_file_path = Path(__file__).parent.parent / "resources/oe_mets_test.xml"
        self.html_file_path = (
            Path(__file__).parent.parent / "resources/oe_book_chapter.html"
        )

    def test_get_doi_and_isbn(self):
        mock_xml_extractor = Mock()
        mock_xml_extractor.extract_content_attribute_filter.return_value = [
            Mock(content="urn:doi:10.1000/xyz123"),
            Mock(content="urn:isbn:978-3-16-148410-0"),
        ]

        doi, isbn = self.collector._get_doi_and_isbn(mock_xml_extractor)

        self.assertEqual(doi, "10.1000/xyz123")
        self.assertEqual(isbn, "978-3-16-148410-0")
        mock_xml_extractor.extract_content_attribute_filter.assert_called_once_with(
            tag="dcterms:identifier", attribute_name="scheme", attribute_value="URN"
        )

    def test_get_authors(self):
        mock_xml_extractor = Mock()
        mock_xml_extractor.extract_content.return_value = [
            Mock(content="Doe, John"),
            Mock(content="Smith, Jane"),
        ]

        authors = self.collector._get_authors(mock_xml_extractor)

        self.assertListEqual(
            authors,
            [
                {"name": "John Doe", "misc": ""},
                {"name": "Jane Smith", "misc": ""},
            ],
        )
        mock_xml_extractor.extract_content.assert_called_once_with("dcterms:creator")

    def test_get_current_license(self):
        mock_root_extractor = Mock()
        mock_root_extractor.extract_content.return_value = [
            Mock(content="https://creativecommons.org/licenses/by/4.0/")
        ]

        license = self.collector._get_current_license(mock_root_extractor)

        self.assertEqual(license, "https://creativecommons.org/licenses/by/4.0/")
        mock_root_extractor.extract_content.assert_called_once_with(
            tag="dcterms:rights"
        )

    def test_get_description(self):
        mock_root_extractor = Mock()
        mock_root_extractor.extract_content_attribute_filter.return_value = [
            Mock(content="This is an abstract in English.")
        ]

        description = self.collector._get_description(
            root_extractor=mock_root_extractor, lang="en"
        )

        self.assertEqual(description, "This is an abstract in English.")
        mock_root_extractor.extract_content_attribute_filter.assert_called_once_with(
            tag="dcterms:abstract",
            attribute_name="xml:lang",
            attribute_value="en",
        )

    def test_get_mets_metadata(self):
        mock_response = Mock()
        self.mock_session.get.return_value = mock_response
        url = "https://books.openedition.org/editor/01"

        md_id, response = self.collector._get_mets_metadata(self.mock_session, url)

        expected_md_id = "editor/01"
        expected_md_url = MD_OE_BOOKS_BASE_URL.replace("<md_id>", expected_md_id)

        self.assertEqual(md_id, expected_md_id)
        self.assertEqual(response, mock_response)
        self.mock_session.get.assert_called_once_with(
            url=expected_md_url, timeout=self.collector.timeout
        )

    @patch("welearn_datastack.plugins.scrapers.oe_books.get_new_https_session")
    def test_run_book_case(self, mock_get_new_https_session):
        mock_get_new_https_session.return_value = self.mock_session
        mock_response = MockResponse(
            text=self.xml_file_path.open().read(), status_code=200
        )
        self.mock_session.get.return_value = mock_response
        url = "https://books.openedition.org/ariadnaediciones/8043"

        result = self.collector.run([url])

        scraped_docs = result[0]
        error_urls = result[1]

        self.assertEqual(scraped_docs[0].document_url, url)
        self.assertEqual(
            scraped_docs[0].document_title,
            "A Southern Perspective on Development Studies",
        )
        self.assertEqual(scraped_docs[0].document_lang, "en")
        self.assertEqual(scraped_docs[0].document_corpus, "open-edition-books")
        result_details = scraped_docs[0].document_details
        self.assertEqual(result_details["doi"], "10.4000/books.ariadnaediciones.8043")
        self.assertEqual(result_details["isbn"], "978-956-6095-09-5")
        self.assertEqual(
            result_details["authors"], [{"name": "Carlos Mallorquin", "misc": ""}]
        )
        self.assertEqual(
            result_details["license"], "https://creativecommons.org/licenses/by/4.0/"
        )
        self.assertEqual(result_details["publisher"], "Ariadna Ediciones")

    @patch("welearn_datastack.plugins.scrapers.oe_books.get_new_https_session")
    def test_run_chapter_case(self, mock_get_new_https_session):
        mock_get_new_https_session.return_value = self.mock_session
        se = [
            MockResponse(text="", status_code=404),
            MockResponse(text=self.html_file_path.read_text(), status_code=200),
            MockResponse(text=self.xml_file_path.read_text(), status_code=200),
        ]
        self.mock_session.get.side_effect = se
        url = "https://books.openedition.org/ariadnaediciones/8068"

        result = self.collector.run([url])

        scraped_docs = result[0]

        self.assertEqual(scraped_docs[0].document_url, url)
        self.assertEqual(
            scraped_docs[0].document_title,
            "A Southern Perspective on Development Studies - Introduction",
        )
        self.assertEqual(scraped_docs[0].document_lang, "en")
        self.assertEqual(scraped_docs[0].document_corpus, "open-edition-books")
        result_details = scraped_docs[0].document_details
        self.assertDictEqual(
            result_details["partOf"][0],
            {
                "element": "https://books.openedition.org/ariadnaediciones/8043",
                "order": 0,
            },
        )
        self.assertEqual(result_details["type"], "chapter")
        self.assertEqual(result_details["isbn"], "978-956-6095-09-5")
        self.assertEqual(
            result_details["authors"], [{"name": "Carlos Mallorquin", "misc": ""}]
        )
        self.assertListEqual(
            result_details["tags"],
            ["latin america", "social sciences", "thought", "sociology of development"],
        )
        self.assertEqual(
            result_details["license"], "https://creativecommons.org/licenses/by/4.0/"
        )
        self.assertEqual(result_details["publisher"], "Ariadna Ediciones")
        self.assertTrue(
            scraped_docs[0].document_content.startswith(
                "Question everything and everyone. Be subversive, constantly questioning reality and the status quo. Be a poet, not a huckster. Don’t cater, don’t pander, especially not to possible audiences, readers, editors, or publishers. Come out of your closet. It’s dark in there. Raise the blinds, throw open your shuttered windows, raise the roof, unscrew the locks from the doors, but don’t throw away the screws. Be committed to something outside yourself. Be militant about it. Or ecstatic."
            )
        )
        self.assertTrue(
            scraped_docs[0].document_content.endswith(
                "in more philosophical terms, there is no general form of being given its diverse set of social and historical conditions."
            )
        )
