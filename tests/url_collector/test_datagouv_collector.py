import unittest
from unittest.mock import patch

from pydantic import ValidationError
from welearn_database.data.models import Corpus

from welearn_datastack.collectors.datagouv_collector import (
    DataGouvURLCollector,
)
from welearn_datastack.data.source_models.datagouv import RootDataGouvModel


class TestDataGouvURLCollector(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus(source_name="datagouv", is_fix=True)
        self.collector = DataGouvURLCollector(self.corpus)
        self.dataset = {
            "created_at": "2026-10-20T12:00:00",
            "description": "Example dataset",
            "doi": None,
            "frequency": "daily",
            "id": "dataset-id",
            "last_modified": "2026-10-20T12:00:00",
            "license": "lov2",
            "organization": {},
            "page": "https://www.data.gouv.fr/datasets/example-dataset",
            "slug": "example-dataset",
            "tags": [],
            "title": "Example dataset",
        }

    def test_validate_nullable_doi(self):
        for doi in (None, "10.1234/example"):
            with self.subTest(doi=doi):
                payload = {
                    "data": [{**self.dataset, "doi": doi}],
                    "total": 1,
                    "page_size": 100,
                }
                result = RootDataGouvModel.model_validate(payload)
                self.assertEqual(result.data[0].doi, doi)

    def test_validate_omitted_optional_fields(self):
        payload = self.dataset.copy()
        for field in (
            "doi",
            "frequency",
            "license",
            "organization",
            "page",
            "slug",
            "tags",
        ):
            payload.pop(field)

        dataset = RootDataGouvModel.model_validate(
            {"data": [payload], "total": 1, "page_size": 100}
        ).data[0]

        self.assertIsNone(dataset.doi)
        self.assertEqual(dataset.frequency, "unknown")
        self.assertEqual(dataset.license, "notspecified")
        self.assertIsNone(dataset.organization)
        self.assertIsNone(dataset.page)
        self.assertIsNone(dataset.slug)
        self.assertEqual(dataset.tags, [])

    def test_validate_invalid_doi(self):
        payload = {
            "data": [{**self.dataset, "doi": 123}],
            "total": 1,
            "page_size": 100,
        }

        with self.assertRaises(ValidationError) as error:
            RootDataGouvModel.model_validate(payload)

        self.assertEqual(
            error.exception.errors()[0]["loc"], ("data", 0, "doi")
        )
        self.assertEqual(error.exception.errors()[0]["type"], "string_type")

    def test_validate_invalid_organization(self):
        payload = {
            "data": [{**self.dataset, "organization": "invalid"}],
            "total": 1,
            "page_size": 100,
        }

        with self.assertRaises(ValidationError) as error:
            RootDataGouvModel.model_validate(payload)

        self.assertEqual(
            error.exception.errors()[0]["loc"], ("data", 0, "organization")
        )
        self.assertEqual(error.exception.errors()[0]["type"], "model_type")

    @patch(
        "welearn_datastack.collectors.datagouv_collector.get_new_https_session"
    )
    def test_collect_with_null_organization(self, mock_get_session):
        self.dataset["organization"] = None
        response = mock_get_session.return_value.get.return_value
        response.json.return_value = {
            "data": [self.dataset],
            "total": 1,
            "page_size": 100,
        }

        documents = self.collector.collect()

        response.raise_for_status.assert_called_once_with()
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].url, self.dataset["page"])
        self.assertEqual(documents[0].external_id, self.dataset["id"])
        self.assertIs(documents[0].corpus, self.corpus)

    @patch(
        "welearn_datastack.collectors.datagouv_collector.get_new_https_session"
    )
    def test_collect_skips_dataset_without_page(self, mock_get_session):
        self.dataset.pop("page")
        response = mock_get_session.return_value.get.return_value
        response.json.return_value = {
            "data": [self.dataset],
            "total": 1,
            "page_size": 100,
        }

        with self.assertLogs(
            "welearn_datastack.collectors.datagouv_collector", level="WARNING"
        ):
            documents = self.collector.collect()

        self.assertEqual(documents, [])

    @patch(
        "welearn_datastack.collectors.datagouv_collector.get_new_https_session"
    )
    def test_collect_uses_api_page_url(self, mock_get_session):
        self.dataset["page"] = (
            "https://www.data.gouv.fr/datasets/canonical-url"
        )
        response = mock_get_session.return_value.get.return_value
        response.json.return_value = {
            "data": [self.dataset],
            "total": 1,
            "page_size": 100,
        }

        documents = self.collector.collect()

        response.raise_for_status.assert_called_once_with()
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].url, self.dataset["page"])
        self.assertEqual(documents[0].external_id, self.dataset["id"])
        self.assertIs(documents[0].corpus, self.corpus)

    @patch(
        "welearn_datastack.collectors.datagouv_collector.get_new_https_session"
    )
    def test_collect_returns_empty_for_invalid_first_page(
        self, mock_get_session
    ):
        response = mock_get_session.return_value.get.return_value
        response.json.return_value = {
            "data": [{**self.dataset, "doi": 123}],
            "total": 201,
            "page_size": 100,
        }

        with self.assertLogs(
            "welearn_datastack.collectors.datagouv_collector", level="WARNING"
        ) as logs:
            documents = self.collector.collect()

        self.assertEqual(documents, [])
        mock_get_session.return_value.get.assert_called_once()
        self.assertIn("Skipping DataGouv page 1", logs.output[0])

    @patch(
        "welearn_datastack.collectors.datagouv_collector.get_new_https_session"
    )
    def test_collect_continues_after_invalid_page(self, mock_get_session):
        response = mock_get_session.return_value.get.return_value
        response.json.side_effect = [
            {"data": [self.dataset], "total": 201, "page_size": 100},
            {
                "data": [{**self.dataset, "doi": 123}],
                "total": 201,
                "page_size": 100,
            },
            {
                "data": [{**self.dataset, "id": "last-dataset"}],
                "total": 201,
                "page_size": 100,
            },
        ]

        with self.assertLogs(
            "welearn_datastack.collectors.datagouv_collector", level="WARNING"
        ) as logs:
            documents = self.collector.collect()

        self.assertEqual(
            [document.external_id for document in documents],
            [self.dataset["id"], "last-dataset"],
        )
        self.assertEqual(
            [
                call.kwargs["params"]["page"]
                for call in mock_get_session.return_value.get.call_args_list
            ],
            [1, 2, 3],
        )
        self.assertIn("Skipping DataGouv page 2", logs.output[0])

    @patch(
        "welearn_datastack.collectors.datagouv_collector.get_new_https_session"
    )
    def test_collect_retrieves_all_pages(self, mock_get_session):
        first_page = [
            {
                **self.dataset,
                "id": f"dataset-id-{index}",
                "slug": f"dataset-{index}",
            }
            for index in range(100)
        ]
        second_page = [{**self.dataset, "id": "dataset-id-100"}]
        response = mock_get_session.return_value.get.return_value
        response.json.side_effect = [
            {"data": first_page, "total": 101, "page_size": 100},
            {"data": second_page, "total": 101, "page_size": 100},
        ]

        documents = self.collector.collect()

        self.assertEqual(len(documents), 101)
        self.assertEqual(
            [
                call.kwargs["params"]["page"]
                for call in mock_get_session.return_value.get.call_args_list
            ],
            [1, 2],
        )
        self.assertTrue(
            all(
                call.kwargs["params"]["page_size"] == 100
                for call in mock_get_session.return_value.get.call_args_list
            )
        )
