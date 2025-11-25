import unittest
from unittest.mock import MagicMock, patch

from requests import HTTPError
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.source_models.pressbooks import (
    Address,
    AuthorItem,
    Content,
    EditorItem,
    License,
    PressBooksMetadataModel,
    PressBooksModel,
    Publisher,
)
from welearn_datastack.plugins.rest_requesters.pressbooks import PressBooksCollector


def build_pressbooks_model():
    content = Content(
        raw="Raw content, test test test test test test",
        rendered="Rendered content.",
        protected=False,
    )
    return PressBooksModel(content=content, links_={})


def build_pressbooks_metadata_model(
    license_url="https://creativecommons.org/licenses/by/4.0/",
):
    license = License(**{"@type": "License"}, url=license_url, name="CC BY 4.0")
    editor = [EditorItem(name="Editor Name", slug="editor-name", **{"@type": "Person"})]
    author = [
        AuthorItem(
            name="Author Name",
            slug="author-name",
            contributor_institution="Institution",
            **{"@type": "Person"},
        )
    ]
    address = Address(**{"@type": "PostalAddress"}, addressLocality="Paris")
    publisher = Publisher(
        **{"@type": "Organization"}, name="Publisher Name", address=address
    )
    return PressBooksMetadataModel(
        name="Element Title",
        editor=editor,
        author=author,
        publisher=publisher,
        datePublished="2022-01-01",
        date_gmt="2022-01-01T12:00:00",
        modified_gmt="2022-01-02T12:00:00",
        license=license,
        links_={},
        isPartOf="Part of this book",
    )


class TestPressBooksCollector(unittest.TestCase):
    def setUp(self):
        self.collector = PressBooksCollector()
        self.metadata = build_pressbooks_metadata_model()
        self.doc = WeLearnDocument(
            url="https://example.com/book/?p=123",
            title="",
            description="",
            full_content="",
            details={},
        )

    def test_extract_post_id(self):
        url_to_test = "https://wtcs.pressbooks.pub/communications/?p=5"
        awaited_result = "5"
        result = self.collector._extract_post_id(url_to_test)
        self.assertEqual(result, awaited_result)

    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.get_new_https_session")
    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.PressBooksModel")
    @patch(
        "welearn_datastack.plugins.rest_requesters.pressbooks.PressBooksMetadataModel"
    )
    def test_run_successful_document_retrieval(
        self, mock_metadata_model, mock_model, mock_session
    ):
        # Mock HTTP client and responses
        mock_client = MagicMock()
        mock_session.return_value = mock_client
        # Mock HEAD for _extract_pressbook_type
        mock_head = MagicMock()
        mock_head.url = "https://example.com/book/chapters/123"
        mock_head.raise_for_status = lambda: None
        mock_client.head.return_value = mock_head
        # Mock GET for post content and metadata
        mock_get_content = MagicMock()
        mock_get_content.json.return_value = build_pressbooks_model().model_dump()
        mock_get_content.raise_for_status = lambda: None
        mock_get_metadata = MagicMock()
        mock_get_metadata.json.return_value = (
            build_pressbooks_metadata_model().model_dump()
        )
        mock_get_metadata.raise_for_status = lambda: None
        mock_client.get.side_effect = [mock_get_content, mock_get_metadata]
        # Mock model_validate_json
        mock_model.model_validate_json.side_effect = lambda x: build_pressbooks_model()
        mock_metadata_model.model_validate_json.side_effect = (
            lambda x: build_pressbooks_metadata_model()
        )
        # Run
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WrapperRetrieveDocument)
        doc_result = result[0].document
        self.assertIsInstance(doc_result, WeLearnDocument)
        self.assertEqual(doc_result.title, "Part of this book - Element Title")
        self.assertIn("license", doc_result.details)
        self.assertEqual(
            doc_result.details["license"],
            "https://creativecommons.org/licenses/by/4.0/",
        )
        self.assertEqual(doc_result.details["authors"][0]["name"], "Author Name")
        self.assertEqual(doc_result.details["editors"][0]["name"], "Editor Name")
        self.assertEqual(doc_result.details["publisher"], "Publisher Name")
        self.assertEqual(doc_result.details["type"], "chapters")
        self.assertIsInstance(doc_result.full_content, str)
        self.assertIsInstance(doc_result.description, str)

    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.get_new_https_session")
    def test_run_http_error_on_content(self, mock_session):
        mock_client = MagicMock()
        mock_session.return_value = mock_client
        # Mock HEAD pour _extract_pressbook_type
        mock_head = MagicMock()
        mock_head.url = "https://example.com/book/chapters/123"
        mock_head.raise_for_status = lambda: None
        mock_client.head.return_value = mock_head

        # Mock GET pour le contenu qui lève l'erreur sur .raise_for_status()
        mock_get_content = MagicMock()
        http_error = HTTPError("500 Server Error")
        http_error.response = MagicMock()
        http_error.response.status_code = 500
        mock_get_content.raise_for_status.side_effect = http_error
        mock_get_content.json.return_value = {}
        mock_client.get.return_value = mock_get_content

        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WrapperRetrieveDocument)
        self.assertIn("Error while retrieving metadata", result[0].error_info)

    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.get_new_https_session")
    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.PressBooksModel")
    def test_run_http_error_on_metadata(self, mock_model, mock_session):
        mock_client = MagicMock()
        mock_session.return_value = mock_client
        # Mock HEAD for _extract_pressbook_type
        mock_head = MagicMock()
        mock_head.url = "https://example.com/book/chapters/123"
        mock_head.raise_for_status = lambda: None
        mock_client.head.return_value = mock_head
        # Mock GET for post content
        mock_get_content = MagicMock()
        mock_get_content.json.return_value = build_pressbooks_model().model_dump()
        mock_get_content.raise_for_status = lambda: None
        mock_get_metadata = MagicMock()

        http_error = HTTPError("500 Server Error")
        http_error.response = MagicMock()
        http_error.response.status_code = 500
        mock_get_metadata.raise_for_status.side_effect = http_error
        mock_client.get.side_effect = [mock_get_content, mock_get_metadata]
        mock_model.model_validate_json.side_effect = lambda x: build_pressbooks_model()
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WrapperRetrieveDocument)
        self.assertIn("Error while retrieving metadata", result[0].error_info)

    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.get_new_https_session")
    @patch("welearn_datastack.plugins.rest_requesters.pressbooks.PressBooksModel")
    @patch(
        "welearn_datastack.plugins.rest_requesters.pressbooks.PressBooksMetadataModel"
    )
    def test_run_unauthorized_license(
        self, mock_metadata_model, mock_model, mock_session
    ):
        mock_client = MagicMock()
        mock_session.return_value = mock_client
        # Mock HEAD for _extract_pressbook_type
        mock_head = MagicMock()
        mock_head.url = "https://example.com/book/chapters/123"
        mock_head.raise_for_status = lambda: None
        mock_client.head.return_value = mock_head
        # Mock GET for post content and metadata
        mock_get_content = MagicMock()
        mock_get_content.json.return_value = build_pressbooks_model().model_dump()
        mock_get_content.raise_for_status = lambda: None
        mock_get_metadata = MagicMock()
        # Unauthorized license
        mock_get_metadata.json.return_value = build_pressbooks_metadata_model(
            license_url="https://unauthorized.org/license"
        ).model_dump()
        mock_get_metadata.raise_for_status = lambda: None
        mock_client.get.side_effect = [mock_get_content, mock_get_metadata]
        mock_model.model_validate_json.side_effect = lambda x: build_pressbooks_model()
        mock_metadata_model.model_validate_json.side_effect = (
            lambda x: build_pressbooks_metadata_model(
                license_url="https://unauthorized.org/license"
            )
        )
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WrapperRetrieveDocument)
        self.assertIn("Unauthorized license", result[0].error_info)

    def test_extract_publisher(self):
        publisher = self.collector.extract_publisher(self.metadata)
        self.assertEqual(publisher, "Publisher Name")
        meta = build_pressbooks_metadata_model()
        meta.publisher = None
        publisher_none = self.collector.extract_publisher(meta)
        self.assertIsNone(publisher_none)

    def test_extract_editors(self):
        editors = self.collector._extract_editors(self.metadata)
        self.assertIsInstance(editors, list)
        self.assertEqual(editors[0]["name"], "Editor Name")

    def test_extract_authors(self):
        authors = self.collector._extract_authors(self.metadata)
        self.assertIsInstance(authors, list)
        self.assertEqual(authors[0]["name"], "Author Name")
        self.assertEqual(authors[0]["misc"], "Institution")

    def test_extract_updated_date(self):
        updated = self.collector._extract_updated_date("main_url", "123", self.metadata)
        self.assertIsInstance(updated, float)
        # Test avec modified_gmt=None
        meta = build_pressbooks_metadata_model()
        meta.modified_gmt = None
        updated_none = self.collector._extract_updated_date("main_url", "123", meta)
        self.assertIsNone(updated_none)

    def test_extract_publication_date(self):
        pubdate = self.collector._extract_publication_date(
            "main_url", "123", self.metadata
        )
        self.assertIsInstance(pubdate, float)
        # Test fallback avec datePublished
        meta = build_pressbooks_metadata_model()
        meta.date_gmt = None
        pubdate_fallback = self.collector._extract_publication_date(
            "main_url", "123", meta
        )
        self.assertIsInstance(pubdate_fallback, float)
        # Test avec aucune date
        meta.datePublished = None
        pubdate_none = self.collector._extract_publication_date("main_url", "123", meta)
        self.assertIsNone(pubdate_none)

    def test_extract_content(self):
        model = build_pressbooks_model()
        content = self.collector._extract_content(model)
        self.assertEqual(content, "Raw content, test test test test test test")

    def test_compose_title(self):
        title = self.collector._compose_title(self.metadata)
        self.assertEqual(title, "Part of this book - Element Title")
        # Test avec isPartOf vide
        meta = build_pressbooks_metadata_model()
        meta.isPartOf = ""
        title_simple = self.collector._compose_title(meta)
        self.assertEqual(title_simple, "Element Title")

    def test_extract_three_first_sentences(self):
        text = "Première phrase. Deuxième phrase! Troisième phrase? Quatrième phrase."
        result = self.collector._extract_three_first_sentences(text)
        self.assertTrue(result.startswith("Première phrase"))
