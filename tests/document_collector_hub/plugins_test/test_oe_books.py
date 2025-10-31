import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from requests import Session  # type: ignore
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.constants import MD_OE_BOOKS_BASE_URL
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
    def test_run_book_success(self, mock_get_new_https_session):
        # Simulate a successful book fetch with valid XML
        mock_get_new_https_session.return_value = self.mock_session
        with self.xml_file_path.open() as f:
            mock_response = MockResponse(text=f.read(), status_code=200)
        self.mock_session.get.return_value = mock_response

        doc = WeLearnDocument(
            id=1, url="https://books.openedition.org/ariadnaediciones/8043"
        )
        result = self.collector.run([doc])

        self.assertEqual(len(result), 1)
        oe_doc = result[0]
        self.assertIsNone(oe_doc.error_info)
        # Check all main document properties
        self.assertEqual(oe_doc.document.url, doc.url)
        self.assertEqual(
            oe_doc.document.title, "A Southern Perspective on Development Studies"
        )
        # self.assertEqual(oe_doc.document.corpus, "open-edition-books")
        details = oe_doc.document.details
        self.assertEqual(details["doi"], "10.4000/books.ariadnaediciones.8043")
        self.assertEqual(details["isbn"], "978-956-6095-09-5")
        self.assertEqual(
            details["authors"], [{"name": "Carlos Mallorquin", "misc": ""}]
        )
        self.assertEqual(
            details["license"], "https://creativecommons.org/licenses/by/4.0/"
        )
        self.assertEqual(details["publisher"], "Ariadna Ediciones")
        # Check that all expected keys are present
        for key in ["doi", "isbn", "authors", "license", "publisher"]:
            self.assertIn(key, details)
        # Check that no unexpected keys are present
        allowed_keys = {
            "doi",
            "isbn",
            "authors",
            "license",
            "publisher",
            "tags",
            "type",
            "partOf",
            "publication_date",
        }
        self.assertTrue(set(details.keys()).issubset(allowed_keys))

    @patch("welearn_datastack.plugins.scrapers.oe_books.get_new_https_session")
    def test_run_chapter_success(self, mock_get_new_https_session):
        # Simulate a successful chapter fetch with valid HTML and XML
        mock_get_new_https_session.return_value = self.mock_session
        se = [
            MockResponse(text="", status_code=404),
            MockResponse(text=self.html_file_path.read_text(), status_code=200),
            MockResponse(text=self.xml_file_path.read_text(), status_code=200),
        ]
        self.mock_session.get.side_effect = se

        doc = WeLearnDocument(
            id=2, url="https://books.openedition.org/ariadnaediciones/8068"
        )
        result = self.collector.run([doc])

        self.assertEqual(len(result), 1)
        oe_doc = result[0]
        self.assertIsNone(oe_doc.error_info)
        self.assertEqual(oe_doc.document.url, doc.url)
        self.assertEqual(
            oe_doc.document.title,
            "A Southern Perspective on Development Studies - Introduction",
        )
        # self.assertEqual(oe_doc.document.lang, "en")
        # self.assertEqual(oe_doc.document.corpus, "open-edition-books")
        details = oe_doc.document.details
        self.assertDictEqual(
            details["partOf"][0],
            {
                "element": "https://books.openedition.org/ariadnaediciones/8043",
                "order": 0,
            },
        )
        self.assertEqual(details["type"], "chapter")
        self.assertEqual(details["isbn"], "978-956-6095-09-5")
        self.assertEqual(
            details["authors"], [{"name": "Carlos Mallorquin", "misc": ""}]
        )
        self.assertListEqual(
            details["tags"],
            ["latin america", "social sciences", "thought", "sociology of development"],
        )
        self.assertEqual(
            details["license"], "https://creativecommons.org/licenses/by/4.0/"
        )
        self.assertEqual(details["publisher"], "Ariadna Ediciones")
        self.assertTrue(
            oe_doc.document.full_content.startswith(
                "Question everything and everyone. Be subversive, constantly questioning reality and the status quo. Be a poet, not a huckster. Don’t cater, don’t pander, especially not to possible audiences, readers, editors, or publishers. Come out of your closet. It’s dark in there. Raise the blinds, throw open your shuttered windows, raise the roof, unscrew the locks from the doors, but don’t throw away the screws. Be committed to something outside yourself. Be militant about it. Or ecstatic."
            )
        )
        self.assertTrue(
            oe_doc.document.full_content.endswith(
                "in more philosophical terms, there is no general form of being given its diverse set of social and historical conditions."
            )
        )
        # Check that all expected keys are present
        for key in [
            "partOf",
            "type",
            "isbn",
            "authors",
            "tags",
            "license",
            "publisher",
            "publication_date",
        ]:
            self.assertIn(key, details)
        allowed_keys = {
            "doi",
            "isbn",
            "authors",
            "license",
            "publisher",
            "tags",
            "type",
            "partOf",
            "publication_date",
        }
        self.assertTrue(set(details.keys()).issubset(allowed_keys))

    @patch("welearn_datastack.plugins.scrapers.oe_books.get_new_https_session")
    def test_run_http_error(self, mock_get_new_https_session):
        # Simulate an HTTP error (e.g. 500)
        mock_get_new_https_session.return_value = self.mock_session

        class ErrorResponse:
            def __init__(self):
                self.status_code = 500

            def raise_for_status(self):
                raise Exception("HTTP error")

        self.mock_session.get.return_value = ErrorResponse()
        doc = WeLearnDocument(
            id=3, url="https://books.openedition.org/ariadnaediciones/9999"
        )
        result = self.collector.run([doc])
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIn("HTTP error", result[0].error_info)
        self.assertEqual(
            result[0].document.url,
            "https://books.openedition.org/ariadnaediciones/9999",
        )

    @patch("welearn_datastack.plugins.scrapers.oe_books.get_new_https_session")
    def test_run_invalid_xml(self, mock_get_new_https_session):
        # Simulate a response with invalid XML
        mock_get_new_https_session.return_value = self.mock_session

        class InvalidXMLResponse:
            def __init__(self):
                self.status_code = 200
                self.text = "<invalid>"

            def raise_for_status(self):
                pass

        self.mock_session.get.return_value = InvalidXMLResponse()

        doc = WeLearnDocument(
            id=4, url="https://books.openedition.org/ariadnaediciones/8888"
        )
        result = self.collector.run([doc])
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIn("invalid", result[0].error_info.lower())
        self.assertEqual(
            result[0].document.url,
            "https://books.openedition.org/ariadnaediciones/8888",
        )

    @patch("welearn_datastack.plugins.scrapers.oe_books.get_new_https_session")
    def test_run_empty_input(self, mock_get_new_https_session):
        # Should return an empty list if no documents are provided
        result = self.collector.run([])
        self.assertEqual(result, [])
