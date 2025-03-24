import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from welearn_datastack.collectors.hal_collector import HALURLCollector
from welearn_datastack.data.db_models import Corpus
from welearn_datastack.utils_.scraping_utils import get_url_without_hal_like_versionning


class TestHALURLCollector(TestCase):
    def setUp(self):
        self.mock_corpus = Corpus(source_name="hal", is_fix=True)
        self.hal_collector = HALURLCollector(
            corpus=self.mock_corpus, date_last_insert=1136073600
        )

        self.json_fp = Path(__file__).parent / "resources" / "hal_file.json"
        self.json_fp.parent.mkdir(parents=True, exist_ok=True)

        with self.json_fp.open(mode="r") as f:
            self.content_json = json.load(f)

    @patch("requests.Session.get")
    def test__get_json_hal_api(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = self.content_json

        awaited_res = self.hal_collector._get_json_hal_api()

        self.assertEqual(awaited_res, self.content_json["response"]["docs"])

    def test_generate_api_query(self):
        tested_data = self.hal_collector._generate_api_query()
        self.assertEqual(
            tested_data, "producedDate_tdate:[2006-01-01T00:00:00Z TO NOW]"
        )

    def test_get_url_without_hal_like_versionning(self):
        url = "https://hal.science/hal-04337383v1"
        tested_res = get_url_without_hal_like_versionning(url)
        self.assertEqual(tested_res, "https://hal.science/hal-04337383")

    @patch(
        "welearn_datastack.collectors.hal_collector.HAL_URL_BASE",
        "https://example.org/",
    )
    @patch("requests.Session.get")
    def test_collect(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = self.content_json

        url_in_file = [
            "https://example.org/" + i["halId_s"]
            for i in self.content_json["response"]["docs"]
        ]

        tested_res = self.hal_collector.collect()
        self.assertEqual(len(tested_res), 30)

        for i, url_from_file in enumerate(url_in_file):
            self.assertEqual(tested_res[i].url, url_from_file)
            self.assertEqual(tested_res[i].corpus.source_name, "hal")
            self.assertEqual(tested_res[i].corpus.is_fix, True)
