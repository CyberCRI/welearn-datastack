from unittest import TestCase
from unittest.mock import Mock, patch

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.unesdoc_collector import UNESDOCURLCollector


class TestUNESDOCURLCollector(TestCase):
    def setUp(self):
        corpus = Corpus(id=1, source_name="unesdoc")
        self.url_collector = UNESDOCURLCollector(corpus=corpus)
        self.api_ret_json = {
            "total_count": 283889,
            "results": [
                {"url": "https://unesdoc.unesco.org/ark:/48223/pf0000396769/fre"},
                {"url": "https://unesdoc.unesco.org/ark:/48223/pf0000396769"},
                {"url": "https://unesdoc.unesco.org/ark:/48223/pf0000396877/chi"},
            ],
        }

    @patch("welearn_datastack.collectors.unesdoc_collector.get_new_https_session")
    def test__get_unesdoc_url(self, mock_get_new_https_session):
        # Mock the HTTP session and its get() method
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.api_ret_json
        mock_client.get.return_value = mock_response
        mock_get_new_https_session.return_value = mock_client
        awaited_result = [
            "https://unesdoc.unesco.org/ark:/48223/pf0000396769/fre",
            "https://unesdoc.unesco.org/ark:/48223/pf0000396769",
            "https://unesdoc.unesco.org/ark:/48223/pf0000396877/chi",
        ]
        res = self.url_collector._get_unesdoc_url()
        self.assertEqual(res, awaited_result)

    def test__correct_unesdoc_url_w_lang(self):
        tested_url = "https://unesdoc.unesco.org/ark:/48223/pf0000396769/fre"
        awaited_url = "https://unesdoc.unesco.org/ark:/48223/pf0000396769_fre"
        result = self.url_collector._correct_unesdoc_url(tested_url)
        self.assertEqual(awaited_url, result)

    def test__correct_unesdoc_url_wout_lang(self):
        tested_url = "https://unesdoc.unesco.org/ark:/48223/pf0000396769"
        awaited_url = "https://unesdoc.unesco.org/ark:/48223/pf0000396769"
        result = self.url_collector._correct_unesdoc_url(tested_url)
        self.assertEqual(awaited_url, result)

    def test__extract_unesdoc_id_from_url(self):
        # Test extraction of the unesdoc id from a valid URL
        url = "https://unesdoc.unesco.org/ark:/48223/pf0000396769/fre"
        expected_id = "48223/pf0000396769/fre"
        result = self.url_collector._extract_unesdoc_id_from_url(url)
        self.assertEqual(result, expected_id)

    def test__extract_unesdoc_id_from_url_wout_lang(self):
        # Test extraction of the unesdoc id from a valid URL
        url = "https://unesdoc.unesco.org/ark:/48223/pf0000396769"
        expected_id = "48223/pf0000396769"
        result = self.url_collector._extract_unesdoc_id_from_url(url)
        self.assertEqual(result, expected_id)

    def test_collect(self):
        # Mock _get_unesdoc_url and _correct_unesdoc_url for collect
        self.url_collector._get_unesdoc_url = Mock(
            return_value=[
                "https://unesdoc.unesco.org/ark:/48223/pf0000396769/fre",
                "https://unesdoc.unesco.org/ark:/48223/pf0000396769",
                "https://unesdoc.unesco.org/ark:/48223/pf0000396877/chi",
            ]
        )
        docs = self.url_collector.collect()
        self.assertEqual(len(docs), 3)
