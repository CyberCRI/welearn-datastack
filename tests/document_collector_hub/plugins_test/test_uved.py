import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.source_models.uved import UVEDMemberItem
from welearn_datastack.plugins.rest_requesters.uved import UVEDCollector


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception("HTTP Error")


class TestUVEDCollector(unittest.TestCase):
    def setUp(self):
        self.collector = UVEDCollector()
        self.resource_path = Path(__file__).parent / "../resources/resource_uved.json"
        with self.resource_path.open() as f:
            self.resource_json = json.load(f)
        self.uved_item = UVEDMemberItem.model_validate(self.resource_json)
        self.base_doc = WeLearnDocument(
            id=1,
            url="https://www.uved.fr/ressource/agroforesterie-bien-etre-et-sante-mentale-1",
            external_id=self.uved_item.uid,
        )

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_transcript_used_as_full_content(self, mock_session):
        # Transcript is not empty, should be used as full_content
        item = self.uved_item.model_copy()
        item.transcription = "Transcript content here."
        mock_session.return_value.get.return_value = MockResponse(item.model_dump())
        # Check that the API is called with the correct external_id
        result = self.collector.run([self.base_doc])
        self.assertEqual(len(result), 1)
        doc = result[0].document
        self.assertEqual(doc.full_content, "Transcript content here.")
        self.assertEqual(doc.title, item.title)
        self.assertTrue(doc.details)
        self.assertEqual(doc.external_id, self.uved_item.uid)

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_transcription_file_used_as_full_content(self, mock_session):
        # Transcript is empty, transcriptionFile is present and used
        item = self.uved_item.model_copy()
        item.transcription = ""
        item.transcriptionFile["url"] = (
            "https://www.uved.fr/fileadmin/user_upload/Documents/pdf/Transcriptions/Arbres/MOOC_UVED_Arbres_Transcription_LeCadre_2.pdf"
        )
        mock_session.return_value.get.return_value = MockResponse(item.model_dump())
        with patch(
            "welearn_datastack.modules.pdf_extractor.extract_txt_from_pdf_with_tika",
            return_value="PDF extracted content.",
        ):
            result = self.collector.run([self.base_doc])
        self.assertEqual(len(result), 1)
        doc = result[0].document
        self.assertEqual(doc.full_content, "PDF extracted content.")
        self.assertTrue(doc.title)
        self.assertTrue(doc.details)
        self.assertEqual(doc.external_id, self.uved_item.uid)

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_description_used_as_full_content(self, mock_session):
        # Neither transcript nor transcriptionFile, fallback to description
        item = self.uved_item.model_copy()
        item.transcription = ""
        item.transcriptionFile = None
        mock_session.return_value.get.return_value = MockResponse(item.model_dump())
        result = self.collector.run([self.base_doc])
        self.assertEqual(len(result), 1)
        doc = result[0].document
        self.assertEqual(doc.full_content, item.description)
        self.assertTrue(doc.title)
        self.assertTrue(doc.details)
        self.assertEqual(doc.external_id, self.uved_item.uid)

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_http_error(self, mock_session):
        # Simulate HTTP error
        mock_session.return_value.get.return_value = MockResponse({}, status_code=500)
        with self.assertRaises(Exception):
            self.collector.run([self.base_doc])

    def test_extract_licence(self):
        # Should extract correct license from categories
        licence = self.collector._extract_licence(self.uved_item)
        self.assertTrue(isinstance(licence, str))
        self.assertIn("Creative Commons", licence)

    def test_extract_metadata(self):
        # Should extract metadata dict
        metadata = self.collector._extract_metadata(self.uved_item)
        self.assertTrue(isinstance(metadata, dict))
        self.assertIn("authors", metadata)
        self.assertIn("publisher", metadata)

    def test_extract_external_sdg_id(self):
        # Should extract SDG id from categories
        sdg_id = self.collector._extract_external_sdg_id(self.uved_item.categories)
        self.assertTrue(isinstance(sdg_id, str))
        self.assertIn("Objectifs de Développement Durable", sdg_id)

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_multiple_documents(self, mock_session):
        # Should process multiple documents
        item = self.uved_item.model_copy()
        item.transcription = "Transcript content here."
        mock_session.return_value.get.return_value = MockResponse(item.model_dump())
        docs = [
            self.base_doc,
            self.base_doc.model_copy(
                update={"id": 2, "external_id": self.uved_item.uid}
            ),
        ]
        result = self.collector.run(docs)
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertEqual(r.document.full_content, "Transcript content here.")
            self.assertEqual(r.document.external_id, self.uved_item.uid)
