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
        self.doc = WeLearnDocument(
            url="https://example.com/book/?p=123",
            title="",
            description="",
            full_content="",
            details={},
        )

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
        self.assertEqual(result, [])
        self.assertEqual(self.doc.title, "Part of this book - Element Title")
        self.assertIn("license", self.doc.details)
        self.assertEqual(
            self.doc.details["license"], "https://creativecommons.org/licenses/by/4.0/"
        )
        self.assertEqual(self.doc.details["authors"][0]["name"], "Author Name")
        self.assertEqual(self.doc.details["editors"][0]["name"], "Editor Name")
        self.assertEqual(self.doc.details["publisher"], "Publisher Name")
        self.assertEqual(self.doc.details["type"], "chapters")
        self.assertTrue(hasattr(self.doc, "full_content"))
        self.assertTrue(isinstance(self.doc.full_content, str))
        self.assertTrue(hasattr(self.doc, "description"))
        self.assertTrue(isinstance(self.doc.description, str))

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
