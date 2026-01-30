import unittest
from unittest.mock import Mock, patch

from welearn_database.data.models.document_related import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.source_models.fao_open_knowledge import Bundle, Item, Link
from welearn_datastack.plugins.rest_requesters.fao_open_knowledge import (
    FAOOpenKnowledgeCollector,
)


class TestFAOOpenKnowledgeCollector(unittest.TestCase):
    def setUp(self):
        self.collector = FAOOpenKnowledgeCollector()
        self.doc = WeLearnDocument(
            id=1,
            url="https://example.org/fao/resource/1234",
            external_id="abcd-1234",
            details={},
        )
        self.item = Item(
            id="abcd-1234",
            uuid="abcd-1234",
            name="FAO Document Title",
            handle="1234/5678",
            metadata={
                "dc.rights.license": [
                    {
                        "value": "CC-BY-4.0",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": "Rome",
                    }
                ],
                "dc.contributor.author": [
                    {
                        "value": "John Doe;Jane Smith",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": "Rome",
                    }
                ],
                "dc.description.abstract": [
                    {
                        "value": "A description.",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": "Rome",
                    }
                ],
                "dc.identifier.doi": [
                    {
                        "value": "10.1234/fao.5678",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": "Rome",
                    }
                ],
                "dc.date.available": [
                    {
                        "value": "2023-01-01T00:00:00Z",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": "Rome",
                    }
                ],
                "dc.date.lastModified": [
                    {
                        "value": "2023-01-02T00:00:00Z",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": "Rome",
                    }
                ],
                "fao.taxonomy.type": [
                    {
                        "value": "Report",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": "Rome",
                    }
                ],
            },
            inArchive=True,
            discoverable=True,
            withdrawn=False,
            lastModified="2023-01-02T00:00:00Z",
            entityType=None,
            type="item",
            _links={
                "item": {"href": ""},
                "bitstreams": {"href": ""},
                "primaryBitstream": {"href": ""},
                "self": {"href": ""},
                "bundles": {"href": ""},
                "mappedCollections": {"href": ""},
                "owningCollection": {"href": ""},
                "relationships": {"href": ""},
                "version": {"href": ""},
                "templateItemOf": {"href": ""},
                "thumbnail": {"href": ""},
                "relateditemlistconfigs": {"href": ""},
            },
        )
        self.bundle = Bundle(
            uuid="pdf-uuid",
            name="ORIGINAL",
            handle=None,
            metadata={},
            type="bundle",
            _links={
                "item": {"href": ""},
                "bitstreams": {"href": ""},
                "primaryBitstream": {"href": ""},
                "self": {"href": ""},
                "bundles": {"href": ""},
                "mappedCollections": {"href": ""},
                "owningCollection": {"href": ""},
                "relationships": {"href": ""},
                "version": {"href": ""},
                "templateItemOf": {"href": ""},
                "thumbnail": {"href": ""},
                "relateditemlistconfigs": {"href": ""},
            },
        )

    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_success(self, mock_get_metadata, mock_get_bundle, mock_get_pdf):
        # Simulate a successful run with valid PDF and metadata
        mock_get_metadata.return_value = self.item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted."
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNone(doc_result.error_info)
        self.assertIsInstance(doc_result.document, WeLearnDocument)
        self.assertEqual(doc_result.document.full_content, "PDF content extracted.")
        self.assertEqual(doc_result.document.title, "FAO Document Title")
        self.assertEqual(doc_result.document.description, "A description.")
        self.assertEqual(doc_result.document.details["doi"], "10.1234/fao.5678")
        self.assertEqual(doc_result.document.details["license_url"], "cc-by-4.0")
        self.assertEqual(doc_result.document.details["type"], "Report")
        self.assertTrue(
            doc_result.document.details["contrent_from_pdf"]
        )  # typo in code
        self.assertIsInstance(doc_result.document.details["authors"][0], AuthorDetails)

    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_no_pdf(self, mock_get_metadata, mock_get_bundle, mock_get_pdf):
        # Simulate no PDF bundle found
        mock_get_metadata.return_value = self.item
        mock_get_bundle.return_value = []
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WrapperRetrieveDocument)
        self.assertIn("No PDF bitstream found", result[0].error_info)
        self.assertTrue(result[0].is_error)

    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_pdf_content_empty(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf
    ):
        # Simulate empty PDF content
        mock_get_metadata.return_value = self.item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = ""
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIn("No content extracted from PDF", result[0].error_info)
        self.assertTrue(result[0].is_error)

    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_unauthorized_license(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf
    ):
        # Simulate unauthorized license
        item = self.item.model_copy()
        item.metadata["dc.rights.license"] = [{"value": "UNLICENSED"}]
        mock_get_metadata.return_value = item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted."
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIn("unauthorized license", result[0].error_info)
        self.assertTrue(result[0].is_error)

    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_withdrawn(self, mock_get_metadata, mock_get_bundle, mock_get_pdf):
        # Simulate withdrawn document
        item = self.item.model_copy()
        item.withdrawn = True
        mock_get_metadata.return_value = item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted."
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIn("unauthorized state", result[0].error_info)
        self.assertTrue(result[0].is_error)

    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_embargo(self, mock_get_metadata, mock_get_bundle, mock_get_pdf):
        # Simulate embargoed document
        item = self.item.model_copy()
        item.metadata["fao.embargo"] = {
            "value": "Yes",
            "language": "",
            "authority": None,
            "confidence": -1,
            "place": 0,
        }
        mock_get_metadata.return_value = item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted."
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIn("unauthorized state", result[0].error_info)
        self.assertTrue(result[0].is_error)

    # @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    # @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    # @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    # def test_run_pydantic_validation_error(
    #     self, mock_get_metadata, mock_get_bundle, mock_get_pdf
    # ):
    #     # Simulate pydantic validation error
    #     mock_get_metadata.side_effect = pydantic.ValidationError([], "error")
    #     result = self.collector.run([self.doc])
    #     self.assertEqual(len(result), 1)
    #     self.assertIn("validation error", result[0].error_info)
    #     self.assertTrue(result[0].is_error)

    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_http_error(self, mock_get_metadata, mock_get_bundle, mock_get_pdf):
        # Simulate HTTP error
        import requests

        exception = requests.HTTPError("HTTP error")
        exception.response = Mock(status_code=500)
        mock_get_metadata.side_effect = exception
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIn("HTTP error", result[0].error_info)

    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_multiple_documents(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf
    ):
        # Simulate multiple documents
        mock_get_metadata.return_value = self.item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted. Lorem Ipsum."
        doc2 = WeLearnDocument(
            id=2,
            url="https://example.org/fao/resource/5678",
            external_id="efgh-5678",
            details={},
        )
        result = self.collector.run([self.doc, doc2])
        self.assertEqual(len(result), 2)
        for doc_result in result:
            self.assertIsNone(doc_result.error_info)
            self.assertIsInstance(doc_result.document, WeLearnDocument)
