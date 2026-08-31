import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.zenodo_collector import ZenodoCollector
from welearn_datastack.exceptions import (
    NoDOIFoundError,
    NoExternalID,
    WrongExternalIdFormat,
)


class TestZenodoCollector(unittest.TestCase):
    def setUp(self):
        self.mock_corpus = Corpus(source_name="zenodo_corpus", is_fix=True)
        self.collector = ZenodoCollector(self.mock_corpus)

        self.zenodo_ipbes_file_path = (
            Path(__file__).parent / "resources" / "zenodo_ipbes_answer.json"
        )
        with self.zenodo_ipbes_file_path.open(mode="r") as f:
            self.zenodo_ipbes_content = json.loads(f.read())

    def test__compute_search_parameters(self):
        awaited_query_params = {
            "communities": "test_community",
            "sort": "mostrecent",
            "type": "type_test",
        }

        self.assertDictEqual(
            self.collector._compute_search_parameters(
                community_name="test_community", doc_type="type_test"
            ),
            awaited_query_params,
        )

    def test__compute_search_parameters_not_ascending(self):
        awaited_query_params = {
            "communities": "test_community",
            "sort": "-mostrecent",
            "type": "type_test",
        }

        self.assertDictEqual(
            self.collector._compute_search_parameters(
                community_name="test_community", doc_type="type_test", ascending=False
            ),
            awaited_query_params,
        )

    def test__compute_subdocument(self):
        test_hit = self.zenodo_ipbes_content["hits"]["hits"][11]
        res = self.collector._compute_subdocument(test_hit)

        self.assertEqual(len(res), 7)
        awaited_dois = [
            "10.5281/zenodo.15369060",
            "10.5281/zenodo.17074175",
            "10.5281/zenodo.17074303",
            "10.5281/zenodo.17074410",
            "10.5281/zenodo.17074500",
            "10.5281/zenodo.17074573",
            "10.5281/zenodo.17074600",
        ]

        awaited_zenodo_ids = [i.split(".")[-1] for i in awaited_dois]

        awaited_urls = [
            f"{self.collector.application_base_url}{i.split('.')[-1]}"
            for i in awaited_dois
        ]

        for r in res:
            self.assertIn(r.doi, awaited_dois)
            self.assertIn(r.external_id, awaited_zenodo_ids)
            self.assertIn(r.url, awaited_urls)

    def test__compute_subdocument_no_subdocs(self):
        test_hit = self.zenodo_ipbes_content["hits"]["hits"][0]
        res = self.collector._compute_subdocument(test_hit)
        self.assertEqual(len(res), 0)

    def test__compute_subdocument_wrong_identifier_schema(self):
        test_hit = self.zenodo_ipbes_content["hits"]["hits"][11]
        test_hit["metadata"]["related_identifiers"][0]["schema"] = "url"

        with self.assertRaises(WrongExternalIdFormat):
            self.collector._compute_subdocument(test_hit)

    def test__convert_hit_into_documents(self):
        test_hit = self.zenodo_ipbes_content["hits"]["hits"][11]
        res = self.collector._convert_hit_into_documents(
            test_hit, only_sub_documents=True
        )

        self.assertEqual(len(res), 7)
        awaited_dois = [
            "10.5281/zenodo.15369060",
            "10.5281/zenodo.17074175",
            "10.5281/zenodo.17074303",
            "10.5281/zenodo.17074410",
            "10.5281/zenodo.17074500",
            "10.5281/zenodo.17074573",
            "10.5281/zenodo.17074600",
        ]

        awaited_zenodo_ids = [i.split(".")[-1] for i in awaited_dois]

        awaited_urls = [
            f"{self.collector.application_base_url}{i.split('.')[-1]}"
            for i in awaited_dois
        ]

        for r in res:
            self.assertIn(r.doi, awaited_dois)
            self.assertIn(r.external_id, awaited_zenodo_ids)
            self.assertIn(r.url, awaited_urls)

    def test__convert_hit_into_documents_main_docs_only(self):
        test_hit = self.zenodo_ipbes_content["hits"]["hits"][0]
        res = self.collector._convert_hit_into_documents(
            test_hit, only_sub_documents=False
        )

        self.assertEqual(len(res), 1)

    def test__convert_hit_into_documents_main_docs_only_no_zenodo_id(self):
        test_hit = self.zenodo_ipbes_content["hits"]["hits"][0]
        del test_hit["id"]
        with self.assertRaises(NoExternalID):
            self.collector._convert_hit_into_documents(
                test_hit, only_sub_documents=False
            )

    def test__convert_hit_into_documents_main_docs_only_no_doi(self):
        test_hit = self.zenodo_ipbes_content["hits"]["hits"][0]
        del test_hit["doi"]
        with self.assertRaises(NoDOIFoundError):
            self.collector._convert_hit_into_documents(
                test_hit, only_sub_documents=False
            )

    def test__convert_hits_to_documents(self):
        input_payload = {
            "hits": {
                "hits": [
                    self.zenodo_ipbes_content["hits"]["hits"][0],
                    self.zenodo_ipbes_content["hits"]["hits"][11],
                ]
            }
        }

        res = self.collector._convert_hits_to_documents(input_payload)

        self.assertEqual(len(res), 7)

    @patch("welearn_datastack.collectors.zenodo_collector.get_new_https_session")
    def test_collect(self, mock_get_new_https_session):
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "hits": {"hits": [self.zenodo_ipbes_content["hits"]["hits"][11]]}
        }

        fake_session = MagicMock()
        fake_session.get.return_value = fake_response
        mock_get_new_https_session.return_value = fake_session

        res = self.collector.collect(doc_type="report")

        fake_session.get.assert_called_once_with(
            self.collector.api_base_url,
            params={
                "communities": self.mock_corpus.source_name,
                "sort": "mostrecent",
                "type": "report",
            },
        )
        fake_response.raise_for_status.assert_called_once()
        self.assertEqual(len(res), 7)
