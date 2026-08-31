from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import pydantic
import requests
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRawData
from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.data.source_models.world_bank_okr import WorldBankOKRRecord
from welearn_datastack.exceptions import (
    FileTypeUnsupported,
    NoContent,
    UnauthorizedLicense,
)
from welearn_datastack.modules.xml_extractor import XMLExtractor
from welearn_datastack.plugins.rest_requesters import WorldBankOpenKnowledgeRepository


class TestWorldBankOpenKnowledgeRepository(TestCase):

    def setUp(self):
        self.collector = WorldBankOpenKnowledgeRepository()
        path_document = (
            Path(__file__).parent.parent
            / "resources"
            / "file_plugin_input"
            / "world_bank_okr_example.xml"
        )

        self.example_content = open(path_document).read()
        self.example_record = WorldBankOKRRecord.model_validate(
            XMLExtractor(self.example_content)
        )

    def test__process_authors(self):
        input_lst = ["Good, Alice", "Foo, Bob", "De Loin Sur Perdu, Alain"]
        ret = self.collector._process_authors(input_lst)
        for a in ret:
            self.assertIsInstance(a, AuthorDetails)
            self.assertIn(a.name, ["Alice Good", "Bob Foo", "Alain De Loin Sur Perdu"])
            self.assertEqual(a.misc, "")

    def test__process_authors_one_author(self):
        input_lst = ["World Bank"]
        ret = self.collector._process_authors(input_lst)
        for a in ret:
            self.assertIsInstance(a, AuthorDetails)
            self.assertIn(a.name, ["World Bank"])
            self.assertEqual(a.misc, "")

    def test__extract_licence(self):
        ret = self.collector._extract_licence(self.example_record)
        awaited = "https://creativecommons.org/licenses/by/3.0/igo/"
        self.assertEqual(ret, awaited)

    def test__extract_licence_other_valid_format(self):
        local_example_record = WorldBankOKRRecord.model_validate(
            XMLExtractor(self.example_content.replace("CC BY 3.0 IGO", "CC BY 3.0"))
        )
        ret = self.collector._extract_licence(local_example_record)
        awaited = "https://creativecommons.org/licenses/by/3.0/"
        self.assertEqual(ret, awaited)

    def test__extract_licence_other_valid_format2(self):
        local_example_record = WorldBankOKRRecord.model_validate(
            XMLExtractor(self.example_content.replace("CC BY 3.0 IGO", "CC BY-NC 4.0"))
        )
        ret = self.collector._extract_licence(local_example_record)
        awaited = "https://creativecommons.org/licenses/by-nc/4.0/"
        self.assertEqual(ret, awaited)

    def test__extract_licence_wrong_format(self):
        local_example_record = WorldBankOKRRecord.model_validate(
            XMLExtractor(self.example_content.replace("CC BY 3.0 IGO", "lorem ipsum"))
        )
        ret = self.collector._extract_licence(local_example_record)
        awaited = "lorem ipsum"
        self.assertEqual(ret, awaited)

    def test__retrieve_record_from_oai(self):
        client = Mock()
        response = Mock()
        response.text = self.example_content
        client.get.return_value = response

        ret = self.collector._retrieve_record_from_oai(
            "oai:openknowledge.worldbank.org:10986/3284", client
        )

        self.assertIsInstance(ret, WorldBankOKRRecord)
        response.raise_for_status.assert_called_once()
        client.get.assert_called_once()

    @patch(
        "welearn_datastack.plugins.rest_requesters.world_bank_okr.extract_txt_from_pdf_with_tika"
    )
    @patch(
        "welearn_datastack.plugins.rest_requesters.world_bank_okr.get_new_https_session"
    )
    def test__extract_full_content_prefers_pdf(
        self, mock_get_new_https_session, mock_tika
    ):
        session = Mock()
        response = Mock()
        response.content = b"pdf-content"
        session.get.return_value = response
        mock_get_new_https_session.return_value = session
        mock_tika.return_value = [["Hello", "World"]]

        full_content, is_txt = self.collector._extract_full_content(self.example_record)

        self.assertEqual(full_content, "Hello World")
        self.assertFalse(is_txt)
        response.raise_for_status.assert_called_once()

    @patch(
        "welearn_datastack.plugins.rest_requesters.world_bank_okr.get_new_https_session"
    )
    def test__extract_full_content_txt_fallback(self, mock_get_new_https_session):
        session = Mock()
        response = Mock()
        response.text = "plain text"
        session.get.return_value = response
        mock_get_new_https_session.return_value = session

        record = self.example_record.model_copy(deep=True)
        text_file = record.fileGrp[0].model_copy(deep=True)
        text_file.mimetype = "text/plain"
        text_file.flocat.href = "https://example.org/fallback.txt"
        record.fileGrp = [text_file]

        full_content, is_txt = self.collector._extract_full_content(record)

        self.assertEqual(full_content, "plain text")
        self.assertTrue(is_txt)

    def test__extract_full_content_no_file_group(self):
        record = self.example_record.model_copy(deep=True)
        record.fileGrp = []

        with self.assertRaises(NoContent):
            self.collector._extract_full_content(record)

    def test__extract_full_content_no_supported_file(self):
        record = self.example_record.model_copy(deep=True)
        unsupported_file = record.fileGrp[0].model_copy(deep=True)
        unsupported_file.mimetype = "application/zip"
        record.fileGrp = [unsupported_file]

        with self.assertRaises(FileTypeUnsupported):
            self.collector._extract_full_content(record)

    def test__build_details(self):
        details = self.collector._build_details(self.example_record)

        self.assertIn("authors", details)
        self.assertIn("topics", details)
        self.assertIsNotNone(details["publication_date"])
        self.assertTrue(
            all(topic.name == topic.name.lower() for topic in details["topics"])
        )

    @patch.object(WorldBankOpenKnowledgeRepository, "_extract_full_content")
    def test__update_welearn_document(self, mock_extract_full_content):
        full_content = "Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet."
        mock_extract_full_content.return_value = (full_content, True)
        doc = WeLearnDocument(
            url="https://openknowledge.worldbank.org/handle/10986/3284",
            external_id="oai:openknowledge.worldbank.org:10986/3284",
        )
        wrapper = WrapperRawData(raw_data=self.example_record, document=doc)

        ret = self.collector._update_welearn_document(wrapper)

        self.assertEqual(ret.title, self.example_record.title)
        # self.assertEqual(ret.full_content, full_content) # We use description as full content
        self.assertEqual(
            ret.full_content, ret.description
        )  # We use description as full content

        self.assertTrue(
            ret.description.startswith("International river basins will likely")
        )
        self.assertFalse(ret.details["content_from_txt"])
        # self.assertTrue(ret.details["content_from_txt"])
        self.assertTrue(ret.details["content_from_description"])
        self.assertFalse(ret.details["content_from_pdf"])

    @patch.object(WorldBankOpenKnowledgeRepository, "_extract_licence")
    def test__update_welearn_document_unauthorized_license(self, mock_extract_licence):
        mock_extract_licence.return_value = "https://example.org/unauthorized"
        doc = WeLearnDocument(
            url="https://openknowledge.worldbank.org/handle/10986/3284"
        )
        wrapper = WrapperRawData(raw_data=self.example_record, document=doc)

        with self.assertRaises(UnauthorizedLicense):
            self.collector._update_welearn_document(wrapper)

    @patch.object(WorldBankOpenKnowledgeRepository, "_update_welearn_document")
    @patch.object(WorldBankOpenKnowledgeRepository, "_retrieve_record_from_oai")
    def test_run_success(
        self, mock_retrieve_record_from_oai, mock_update_welearn_document
    ):
        doc = WeLearnDocument(
            url="https://openknowledge.worldbank.org/handle/10986/3284",
            external_id="oai:openknowledge.worldbank.org:10986/3284",
        )
        updated_doc = WeLearnDocument(
            url="https://openknowledge.worldbank.org/handle/10986/3284",
            external_id="oai:openknowledge.worldbank.org:10986/3284",
            title="updated",
        )
        mock_retrieve_record_from_oai.return_value = self.example_record
        mock_update_welearn_document.return_value = updated_doc

        ret = self.collector.run([doc])

        self.assertEqual(len(ret), 1)
        self.assertFalse(ret[0].is_error)
        self.assertEqual(ret[0].document.title, "updated")

    @patch.object(WorldBankOpenKnowledgeRepository, "_retrieve_record_from_oai")
    def test_run_retrieve_request_exception(self, mock_retrieve_record_from_oai):
        doc = WeLearnDocument(
            url="https://openknowledge.worldbank.org/handle/10986/3284",
            external_id="oai:openknowledge.worldbank.org:10986/3284",
        )
        err = requests.exceptions.HTTPError("boom")
        err.response = Mock(status_code=404)
        mock_retrieve_record_from_oai.side_effect = err

        ret = self.collector.run([doc])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertEqual(ret[0].http_error_code, 404)

    @patch.object(WorldBankOpenKnowledgeRepository, "_retrieve_record_from_oai")
    def test_run_retrieve_validation_error(self, mock_retrieve_record_from_oai):
        doc = WeLearnDocument(
            url="https://openknowledge.worldbank.org/handle/10986/3284",
            external_id="oai:openknowledge.worldbank.org:10986/3284",
        )
        with self.assertRaises(pydantic.ValidationError) as ctx:
            WorldBankOKRRecord.model_validate({})
        validation_error = ctx.exception

        mock_retrieve_record_from_oai.side_effect = validation_error

        ret = self.collector.run([doc])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertIsNone(ret[0].http_error_code)

    @patch.object(WorldBankOpenKnowledgeRepository, "_update_welearn_document")
    @patch.object(WorldBankOpenKnowledgeRepository, "_retrieve_record_from_oai")
    def test_run_update_no_content(
        self, mock_retrieve_record_from_oai, mock_update_welearn_document
    ):
        doc = WeLearnDocument(
            url="https://openknowledge.worldbank.org/handle/10986/3284",
            external_id="oai:openknowledge.worldbank.org:10986/3284",
        )
        mock_retrieve_record_from_oai.return_value = self.example_record
        mock_update_welearn_document.side_effect = NoContent("missing content")

        ret = self.collector.run([doc])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertIn("No content found", ret[0].error_info)

    @patch.object(WorldBankOpenKnowledgeRepository, "_update_welearn_document")
    @patch.object(WorldBankOpenKnowledgeRepository, "_retrieve_record_from_oai")
    def test_run_update_request_exception(
        self, mock_retrieve_record_from_oai, mock_update_welearn_document
    ):
        doc = WeLearnDocument(
            url="https://openknowledge.worldbank.org/handle/10986/3284",
            external_id="oai:openknowledge.worldbank.org:10986/3284",
        )
        mock_retrieve_record_from_oai.return_value = self.example_record
        err = requests.exceptions.HTTPError("boom")
        err.response = Mock(status_code=503)
        mock_update_welearn_document.side_effect = err

        ret = self.collector.run([doc])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertEqual(ret[0].http_error_code, 503)
