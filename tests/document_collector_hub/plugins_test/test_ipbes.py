import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pydantic
import requests
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
from welearn_datastack.data.source_models.zenodo import ZenodoRecord
from welearn_datastack.exceptions import (
    ClosedAccessContent,
    LegalException,
    NotEnoughData,
    NotExpectedAmountOfItems,
    PDFFileSizeExceedLimit,
    UnauthorizedLicense,
    WrongFormat,
)
from welearn_datastack.plugins.rest_requesters.ipbes import IPBESCollector


class TestIPBESCollector(unittest.TestCase):
    def setUp(self):
        self.collector = IPBESCollector()
        self.document = WeLearnDocument(
            url="https://zenodo.org/records/17074600",
            external_id="17074600",
        )

    @staticmethod
    def _build_lite_record(**overrides):
        data = {
            "creator_names": ["Alice", "Bob"],
            "access_right": "open",
            "licence": "cc-by-4.0",
            "external_id": "17074600",
            "doi": "10.5281/zenodo.17074600",
            "title": "IPBES title",
            "description": "Raw description",
            "pdf_url": "https://example.org/ipbes.pdf",
            "publication_date": "2025-01-01",
            "update_date": "2025-01-02",
            "type": "report",
            "status": "published",
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_extract_authors(self):
        lite_record = self._build_lite_record(creator_names=["Jane Doe", "John Doe"])
        authors = self.collector._extract_authors(lite_record)

        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0].name, "Jane Doe")
        self.assertEqual(authors[0].misc, "")

    @patch("welearn_datastack.plugins.rest_requesters.ipbes.format_cc_license")
    def test_check_usage_authorization_ok(self, mock_format_cc_license):
        lite_record = self._build_lite_record()
        mock_format_cc_license.return_value = (
            "https://creativecommons.org/licenses/by/4.0/"
        )

        with patch(
            "welearn_datastack.plugins.rest_requesters.ipbes.AUTHORIZED_LICENSES",
            [mock_format_cc_license.return_value],
        ):
            self.collector._check_usage_authorization(lite_record)

    def test_check_usage_authorization_closed_access(self):
        lite_record = self._build_lite_record(access_right="closed")

        with self.assertRaises(ClosedAccessContent):
            self.collector._check_usage_authorization(lite_record)

    @patch("welearn_datastack.plugins.rest_requesters.ipbes.format_cc_license")
    def test_check_usage_authorization_unauthorized_license(
        self, mock_format_cc_license
    ):
        lite_record = self._build_lite_record()
        mock_format_cc_license.return_value = "https://example.org/not-authorized"

        with patch(
            "welearn_datastack.plugins.rest_requesters.ipbes.AUTHORIZED_LICENSES",
            ["https://creativecommons.org/licenses/by/4.0/"],
        ):
            with self.assertRaises(UnauthorizedLicense):
                self.collector._check_usage_authorization(lite_record)

    @patch(
        "welearn_datastack.plugins.rest_requesters.ipbes.ZenodoRecord.model_validate"
    )
    @patch("welearn_datastack.plugins.rest_requesters.ipbes.get_new_https_session")
    def test_get_zenodo_rest_json(
        self, mock_get_new_https_session, mock_model_validate
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "17074600"}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_get_new_https_session.return_value = mock_client

        expected_record = MagicMock()
        mock_model_validate.return_value = expected_record

        ret = self.collector._get_zenodo_rest_json(self.document)

        mock_client.get.assert_called_once_with(
            f"{self.collector.api_base_url}{self.document.external_id}"
        )
        mock_response.raise_for_status.assert_called_once()
        mock_model_validate.assert_called_once_with({"id": "17074600"})
        self.assertEqual(ret, expected_record)

    @patch("welearn_datastack.plugins.rest_requesters.ipbes.format_cc_license")
    @patch("welearn_datastack.plugins.rest_requesters.ipbes.clean_text")
    @patch("welearn_datastack.plugins.rest_requesters.ipbes.get_pdf_content")
    def test_transform_converter_to_welearn_document(
        self, mock_get_pdf_content, mock_clean_text, mock_format_cc_license
    ):
        lite_record = self._build_lite_record()
        mock_get_pdf_content.return_value = (
            "This is a long enough mocked PDF content to satisfy validation."
        )
        mock_clean_text.return_value = "Clean description"
        mock_format_cc_license.return_value = (
            "https://creativecommons.org/licenses/by/4.0/"
        )

        ret = self.collector._transform_converter_to_welearn_document(
            welearn_document=self.document,
            lite_record=lite_record,
        )

        self.assertEqual(ret.external_id, "17074600")
        self.assertEqual(ret.doi, "10.5281/zenodo.17074600")
        self.assertEqual(ret.title, "IPBES title")
        self.assertEqual(ret.description, "Clean description")
        self.assertEqual(
            ret.full_content,
            "This is a long enough mocked PDF content to satisfy validation.",
        )
        self.assertEqual(ret.details["type"], "report")
        self.assertEqual(ret.details["status"], "published")
        self.assertEqual(ret.details["license"], mock_format_cc_license.return_value)
        self.assertEqual(ret.details["authors"][0].name, "Alice")

    @patch("welearn_datastack.plugins.rest_requesters.ipbes.get_pdf_content")
    def test_transform_converter_to_welearn_document_no_pdf_url(
        self, mock_get_pdf_content
    ):
        lite_record = self._build_lite_record(pdf_url=None)

        with self.assertRaises(NotEnoughData):
            self.collector._transform_converter_to_welearn_document(
                welearn_document=self.document,
                lite_record=lite_record,
            )

        mock_get_pdf_content.assert_not_called()

    @patch(
        "welearn_datastack.plugins.rest_requesters.ipbes.ZenodoRestResponseConverter"
    )
    @patch.object(IPBESCollector, "_transform_converter_to_welearn_document")
    @patch.object(IPBESCollector, "_check_usage_authorization")
    @patch.object(IPBESCollector, "_get_zenodo_rest_json")
    def test_run_success(
        self,
        mock_get_zenodo_rest_json,
        mock_check_usage_authorization,
        mock_transform,
        mock_converter,
    ):
        mock_get_zenodo_rest_json.return_value = MagicMock()
        mock_converter.return_value = self._build_lite_record()

        updated_doc = WeLearnDocument(
            url=self.document.url,
            external_id=self.document.external_id,
            title="Updated title",
        )
        mock_transform.return_value = updated_doc

        ret = self.collector.run([self.document])

        self.assertEqual(len(ret), 1)
        self.assertIsInstance(ret[0], WrapperRetrieveDocument)
        self.assertFalse(ret[0].is_error)
        self.assertEqual(ret[0].document.title, "Updated title")
        mock_check_usage_authorization.assert_called_once()

    @patch(
        "welearn_datastack.plugins.rest_requesters.ipbes.get_http_code_from_exception"
    )
    @patch.object(IPBESCollector, "_get_zenodo_rest_json")
    def test_run_request_exception(self, mock_get_zenodo_rest_json, mock_get_http_code):
        err = requests.exceptions.HTTPError("boom")
        err.response = MagicMock(status_code=502)
        mock_get_zenodo_rest_json.side_effect = err
        mock_get_http_code.return_value = 502

        ret = self.collector.run([self.document])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertEqual(ret[0].http_error_code, 502)
        self.assertIn("Error while retrieving IPBES", ret[0].error_info)

    @patch.object(IPBESCollector, "_get_zenodo_rest_json")
    def test_run_validation_error(self, mock_get_zenodo_rest_json):
        with self.assertRaises(pydantic.ValidationError) as ctx:
            ZenodoRecord.model_validate({})
        mock_get_zenodo_rest_json.side_effect = ctx.exception

        ret = self.collector.run([self.document])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertIsNone(ret[0].http_error_code)
        self.assertIn("Error while validating IPBES", ret[0].error_info)

    @patch(
        "welearn_datastack.plugins.rest_requesters.ipbes.ZenodoRestResponseConverter"
    )
    @patch.object(IPBESCollector, "_transform_converter_to_welearn_document")
    @patch.object(IPBESCollector, "_check_usage_authorization")
    @patch.object(IPBESCollector, "_get_zenodo_rest_json")
    def test_run_not_enough_data(
        self,
        mock_get_zenodo_rest_json,
        mock_check_usage_authorization,
        mock_transform,
        mock_converter,
    ):
        mock_get_zenodo_rest_json.return_value = MagicMock()
        mock_converter.return_value = self._build_lite_record()
        mock_transform.side_effect = NotEnoughData("missing PDF")

        ret = self.collector.run([self.document])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertIn("Not enough data", ret[0].error_info)

    @patch(
        "welearn_datastack.plugins.rest_requesters.ipbes.ZenodoRestResponseConverter"
    )
    @patch.object(IPBESCollector, "_transform_converter_to_welearn_document")
    @patch.object(IPBESCollector, "_check_usage_authorization")
    @patch.object(IPBESCollector, "_get_zenodo_rest_json")
    def test_run_not_expected_amount_of_items(
        self,
        mock_get_zenodo_rest_json,
        mock_check_usage_authorization,
        mock_transform,
        mock_converter,
    ):
        mock_get_zenodo_rest_json.return_value = MagicMock()
        mock_converter.return_value = self._build_lite_record()
        mock_transform.side_effect = NotExpectedAmountOfItems("invalid amount")

        ret = self.collector.run([self.document])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertIn("Not expected this amount item", ret[0].error_info)

    @patch(
        "welearn_datastack.plugins.rest_requesters.ipbes.ZenodoRestResponseConverter"
    )
    @patch.object(IPBESCollector, "_transform_converter_to_welearn_document")
    @patch.object(IPBESCollector, "_check_usage_authorization")
    @patch.object(IPBESCollector, "_get_zenodo_rest_json")
    def test_run_legal_exception(
        self,
        mock_get_zenodo_rest_json,
        mock_check_usage_authorization,
        mock_transform,
        mock_converter,
    ):
        mock_get_zenodo_rest_json.return_value = MagicMock()
        mock_converter.return_value = self._build_lite_record()
        mock_check_usage_authorization.side_effect = UnauthorizedLicense("forbidden")

        ret = self.collector.run([self.document])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertIn("Legal exception", ret[0].error_info)
        self.assertIsInstance(
            mock_check_usage_authorization.side_effect, LegalException
        )
        mock_transform.assert_not_called()

    @patch(
        "welearn_datastack.plugins.rest_requesters.ipbes.ZenodoRestResponseConverter"
    )
    @patch.object(IPBESCollector, "_transform_converter_to_welearn_document")
    @patch.object(IPBESCollector, "_check_usage_authorization")
    @patch.object(IPBESCollector, "_get_zenodo_rest_json")
    def test_run_wrong_format(
        self,
        mock_get_zenodo_rest_json,
        mock_check_usage_authorization,
        mock_transform,
        mock_converter,
    ):
        mock_get_zenodo_rest_json.return_value = MagicMock()
        mock_converter.return_value = self._build_lite_record()
        mock_transform.side_effect = WrongFormat("bad format")

        ret = self.collector.run([self.document])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertIn("Formatting error", ret[0].error_info)

    @patch(
        "welearn_datastack.plugins.rest_requesters.ipbes.ZenodoRestResponseConverter"
    )
    @patch.object(IPBESCollector, "_transform_converter_to_welearn_document")
    @patch.object(IPBESCollector, "_check_usage_authorization")
    @patch.object(IPBESCollector, "_get_zenodo_rest_json")
    def test_run_pdf_file_too_large(
        self,
        mock_get_zenodo_rest_json,
        mock_check_usage_authorization,
        mock_transform,
        mock_converter,
    ):
        mock_get_zenodo_rest_json.return_value = MagicMock()
        mock_converter.return_value = self._build_lite_record()
        mock_transform.side_effect = PDFFileSizeExceedLimit("too large")

        ret = self.collector.run([self.document])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertIn("PDF is too large", ret[0].error_info)


if __name__ == "__main__":
    unittest.main()
