import unittest
import uuid
from unittest.mock import patch

import requests
from welearn_database.data.models.document_related import WeLearnDocument

from welearn_datastack.data.source_models.fao_open_knowledge import (
    BitstreamModel,
    BitstreamsLinksModel,
    Bundle,
    BundleLinksModel,
    ChecksumModel,
    Item,
    Link,
    MetadataEntry,
    _Links,
)
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
                        "place": 0,
                    }
                ],
                "dc.contributor.author": [
                    {
                        "value": "John Doe;Jane Smith",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": 0,
                    }
                ],
                "dc.description.abstract": [
                    {
                        "value": "A description.",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": 0,
                    }
                ],
                "dc.identifier.doi": [
                    {
                        "value": "10.1234/fao.5678",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": 0,
                    }
                ],
                "dc.date.available": [
                    {
                        "value": "2023-01-01T00:00:00Z",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": 0,
                    }
                ],
                "dc.date.lastModified": [
                    {
                        "value": "2023-01-02T00:00:00Z",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": 0,
                    }
                ],
                "fao.taxonomy.type": [
                    {
                        "value": "Report",
                        "language": "en",
                        "authority": "FAO",
                        "confidence": 1,
                        "place": 0,
                    }
                ],
            },
            inArchive=True,
            discoverable=True,
            withdrawn=False,
            lastModified="2023-01-02T00:00:00Z",
            entityType=None,
            type="item",
            _links=_Links(
                item=Link(href=""),
                bitstreams=Link(href=""),
                primaryBitstream=Link(href=""),
                self=Link(href=""),
                bundles=Link(href=""),
                mappedCollections=Link(href=""),
                owningCollection=Link(href=""),
                relationships=Link(href=""),
                version=Link(href=""),
                templateItemOf=Link(href=""),
                thumbnail=Link(href=""),
                relateditemlistconfigs=Link(href=""),
            ),
        )
        self.bundle = Bundle(
            uuid="pdf-uuid",
            name="ORIGINAL",
            handle=None,
            metadata={},
            type="bundle",
            _links=BundleLinksModel(
                item=Link(href=""),
                bitstreams=Link(href=""),
                primaryBitstream=Link(href=""),
                self=Link(href=""),
            ),
        )

        self.bitstream = BitstreamModel(
            id=str(uuid.uuid4()),
            uuid=str(uuid.uuid4()),
            name="document.pdf",
            handle=None,
            metadata={},
            bundleName="ORIGINAL",
            sizeBytes=1024,
            checkSum=ChecksumModel(value="checksum-value", checkSumAlgorithm="MD5"),
            sequenceId=1,
            type="bitstream",
            _links=BitstreamsLinksModel(
                content=Link(href=""),
                bundle=Link(href=""),
                format=Link(href=""),
                thumbnail=Link(href=""),
                self=Link(href=""),
            ),
        )

    @patch.object(FAOOpenKnowledgeCollector, "get_bitstream_json")
    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_embargo(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf, mock_get_bitstream
    ):
        # Simulate an embargoed document (inArchive=False)
        embargoed_item = self.item.model_copy()
        embargoed_item.metadata["fao.embargo"] = MetadataEntry(
            value="Yes", language="en", authority="FAO", confidence=1, place=0
        )
        mock_get_metadata.return_value = embargoed_item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted. Lorem Ipsum."
        mock_get_bitstream.return_value = self.bitstream
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNotNone(doc_result.error_info)
        self.assertIn("embargo", doc_result.error_info)

    @patch.object(FAOOpenKnowledgeCollector, "get_bitstream_json")
    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_http_error(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf, mock_get_bitstream
    ):
        error = requests.HTTPError("HTTP error")
        error.response = requests.Response()
        error.response.status_code = 404
        mock_get_metadata.side_effect = error
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted. Lorem Ipsum."
        mock_get_bitstream.return_value = self.bitstream
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNotNone(doc_result.error_info)
        self.assertIn("HTTP error", doc_result.error_info)

    @patch.object(FAOOpenKnowledgeCollector, "get_bitstream_json")
    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_multiple_documents(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf, mock_get_bitstream
    ):
        mock_get_metadata.return_value = self.item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted. Lorem Ipsum."
        mock_get_bitstream.return_value = self.bitstream
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

    @patch.object(FAOOpenKnowledgeCollector, "get_bitstream_json")
    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_no_pdf(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf, mock_get_bitstream
    ):
        mock_get_metadata.return_value = self.item
        mock_get_bundle.return_value = []
        mock_get_pdf.return_value = ""
        mock_get_bitstream.return_value = self.bitstream
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNotNone(doc_result.error_info)
        self.assertIn("no content", doc_result.error_info)

    @patch.object(FAOOpenKnowledgeCollector, "get_bitstream_json")
    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_pdf_content_empty(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf, mock_get_bitstream
    ):
        mock_get_metadata.return_value = self.item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = ""
        mock_get_bitstream.return_value = self.bitstream
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNotNone(doc_result.error_info)

    @patch.object(FAOOpenKnowledgeCollector, "get_bitstream_json")
    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_success(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf, mock_get_bitstream
    ):
        mock_get_metadata.return_value = self.item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted. Lorem Ipsum."
        mock_get_bitstream.return_value = self.bitstream

        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNone(doc_result.error_info)
        self.assertIn("full_content", doc_result.document.__dict__)
        self.assertEqual(
            doc_result.document.full_content, "PDF content extracted. Lorem Ipsum."
        )

    @patch.object(FAOOpenKnowledgeCollector, "get_bitstream_json")
    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_unauthorized_license(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf, mock_get_bitstream
    ):
        unauthorized_item = self.item.model_copy(
            update={"metadata": {"dc.rights.license": [{"value": "NO-LICENSE"}]}}
        )
        mock_get_metadata.return_value = unauthorized_item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted. Lorem Ipsum."
        mock_get_bitstream.return_value = self.bitstream
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNotNone(doc_result.error_info)
        self.assertIn("unauthorized", doc_result.error_info)

    @patch.object(FAOOpenKnowledgeCollector, "get_bitstream_json")
    @patch.object(FAOOpenKnowledgeCollector, "_get_pdf_content")
    @patch.object(FAOOpenKnowledgeCollector, "get_bundle_json")
    @patch.object(FAOOpenKnowledgeCollector, "get_metadata_json")
    def test_run_withdrawn(
        self, mock_get_metadata, mock_get_bundle, mock_get_pdf, mock_get_bitstream
    ):
        withdrawn_item = self.item.model_copy(update={"withdrawn": True})
        mock_get_metadata.return_value = withdrawn_item
        mock_get_bundle.return_value = [self.bundle]
        mock_get_pdf.return_value = "PDF content extracted. Lorem Ipsum."
        mock_get_bitstream.return_value = self.bitstream
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNotNone(doc_result.error_info)
        self.assertIn("withdrawn", doc_result.error_info)
