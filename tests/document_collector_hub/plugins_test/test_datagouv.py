import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import requests
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.plugins.rest_requesters import datagouv


class TestDataGouvCollector(unittest.TestCase):
    def setUp(self):
        self.collector = datagouv.DataGouvCollector()
        self.payload = {
            "created_at": "2026-10-19T00:00:00+00:00",
            "description": "Example dataset description",
            "doi": None,
            "frequency": "daily",
            "id": "dataset-id",
            "last_modified": "2026-10-14T00:00:00+00:00",
            "license": "lov2",
            "organization": {"name": "Example organization"},
            "page": "https://www.data.gouv.fr/datasets/example-dataset",
            "slug": "example-dataset",
            "tags": ["example"],
            "title": "Example dataset",
        }
        self.document = WeLearnDocument(
            url=self.payload["page"],
            external_id=self.payload["id"],
        )

    @patch.object(datagouv, "get_new_https_session")
    def test_run_extracts_metadata(self, mock_get_session):
        response = mock_get_session.return_value.get.return_value
        response.json.return_value = self.payload

        for timestamp in (
            "2026-10-19T00:00:00+00:00",
            "2026-10-19T00:00:00.123456+02:00",
            "2026-10-19T00:00:00.123456",
            "2026-10-19T00:00:00Z",
        ):
            with self.subTest(timestamp=timestamp):
                parsed_timestamp = datetime.fromisoformat(timestamp)
                if parsed_timestamp.tzinfo is None:
                    parsed_timestamp = parsed_timestamp.replace(
                        tzinfo=timezone.utc
                    )

                self.payload["created_at"] = timestamp
                self.payload["last_modified"] = timestamp

                results = self.collector.run([self.document])

                self.assertEqual(len(results), 1)
                self.assertFalse(results[0].is_error, results[0].error_info)
                self.assertEqual(self.document.title, self.payload["title"])
                self.assertEqual(
                    self.document.full_content, self.payload["description"]
                )
                self.assertIsNone(self.document.doi)
                self.assertEqual(
                    self.document.details,
                    {
                        "doi": None,
                        "frequency": "daily",
                        "main_institution": "Example organization",
                        "license": "lov2",
                        "resource_link": self.payload["page"],
                        "tags": ["example"],
                        "publication_date": parsed_timestamp.timestamp(),
                        "update_date": parsed_timestamp.timestamp(),
                    },
                )

        response.raise_for_status.assert_called()

    @patch.object(datagouv, "get_new_https_session")
    def test_run_without_organization(self, mock_get_session):
        self.payload["organization"] = None
        response = mock_get_session.return_value.get.return_value
        response.json.return_value = self.payload

        results = self.collector.run([self.document])

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].is_error, results[0].error_info)
        self.assertIsNone(self.document.details["main_institution"])
        self.assertEqual(
            self.document.details["resource_link"], self.payload["page"]
        )
        self.assertEqual(
            self.document.full_content, self.payload["description"]
        )

    @patch.object(datagouv, "get_new_https_session")
    def test_run_reuses_session_and_sets_timeout(self, mock_get_session):
        response = mock_get_session.return_value.get.return_value
        second_document = WeLearnDocument(
            url=self.payload["page"],
            external_id="second-dataset-id",
        )
        response.json.side_effect = [
            self.payload,
            {**self.payload, "id": second_document.external_id},
        ]
        expected_urls = [
            f"{self.collector.base_url}/api/1/datasets/{document.external_id}"
            for document in (self.document, second_document)
        ]

        results = self.collector.run([self.document, second_document])

        self.assertEqual(len(results), 2)
        self.assertTrue(all(not result.is_error for result in results))
        mock_get_session.assert_called_once_with()
        get_calls = mock_get_session.return_value.get.call_args_list
        self.assertEqual(
            [call_args.args[0] for call_args in get_calls],
            expected_urls,
        )
        for call_args in get_calls:
            self.assertEqual(call_args.kwargs, {"timeout": 30})

    @patch.object(datagouv, "get_new_https_session")
    def test_run_accepts_missing_optional_metadata_fields(
        self, mock_get_session
    ):
        for field in (
            "doi",
            "frequency",
            "license",
            "organization",
            "page",
            "tags",
        ):
            self.payload.pop(field)
        response = mock_get_session.return_value.get.return_value
        response.json.return_value = self.payload

        results = self.collector.run([self.document])

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].is_error, results[0].error_info)
        self.assertEqual(
            self.document.details,
            {
                "doi": None,
                "frequency": "unknown",
                "main_institution": None,
                "license": "notspecified",
                "resource_link": None,
                "tags": [],
                "publication_date": datetime.fromisoformat(
                    self.payload["created_at"]
                ).timestamp(),
                "update_date": datetime.fromisoformat(
                    self.payload["last_modified"]
                ).timestamp(),
            },
        )

    @patch.object(datagouv, "get_new_https_session")
    def test_run_without_organization_name(self, mock_get_session):
        self.payload["organization"] = {"slug": "example-organization"}
        response = mock_get_session.return_value.get.return_value
        response.json.return_value = self.payload

        results = self.collector.run([self.document])

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].is_error, results[0].error_info)
        self.assertIsNone(self.document.details["main_institution"])

    @patch.object(datagouv, "get_new_https_session")
    def test_run_reports_http_error(self, mock_get_session):
        response = mock_get_session.return_value.get.return_value
        http_response = requests.Response()
        http_response.status_code = 404
        response.raise_for_status.side_effect = requests.HTTPError(
            "Not found", response=http_response
        )

        with self.assertLogs(
            "welearn_datastack.plugins.rest_requesters.datagouv", level="ERROR"
        ):
            results = self.collector.run([self.document])

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].is_error)
        self.assertEqual(results[0].http_error_code, 404)
        self.assertIn("Not found", results[0].error_info)
