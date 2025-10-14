import json
import shutil
import unittest
from pathlib import Path

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.json_collector import JSONURLCollector


class TestJSONCollector(unittest.TestCase):
    def setUp(self) -> None:
        # Generate a json file in the resources folder for testing
        self.mock_corpus = Corpus(source_name="test", is_fix=False)
        self.json_fp = Path(__file__).parent / "data" / "test.json"
        self.json_fp.parent.mkdir(parents=True, exist_ok=True)
        with self.json_fp.open(mode="w") as f:
            json.dump(
                {
                    "other": "random",
                    "docs": [
                        {"url": "https://example.com/0", "id": 123},
                        {"url": "https://example.com/1", "id": 456},
                        {"url": "https://example.com/2", "id": 789},
                    ],
                    "docs_bis": [
                        {"url_bis": "https://example.org/0", "id": 9123},
                        {"url_bis": "https://example.org/1", "id": 9456},
                        {"url_bis": "https://example.org/2", "id": 9789},
                    ],
                },
                f,
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.json_fp.parent)

    def test_collect(self):
        """
        Test the collect method of the JSONURLCollector class, on a json file with 3 rows
        """

        json_collector = JSONURLCollector(
            json_fp=self.json_fp,
            corpus=self.mock_corpus,
            url_field="url",
        )
        collected = json_collector.collect()
        self.assertEqual(len(collected), 3)

        for i in range(0, len(collected)):
            self.assertEqual(collected[i].url, f"https://example.com/{i}")
            self.assertEqual(collected[i].corpus.source_name, "test")
            self.assertEqual(collected[i].corpus.is_fix, False)
            self.assertEqual(collected[i].trace, None)
            self.assertEqual(collected[i].id, None)

    def test_collect_url_bis(self):
        """
        Test the collect method of the JSONURLCollector class, on a json file with 3 rows
        """

        json_collector = JSONURLCollector(
            json_fp=self.json_fp,
            corpus=self.mock_corpus,
            url_field="url_bis",
        )
        collected = json_collector.collect()
        self.assertEqual(len(collected), 3)

        for i in range(0, len(collected)):
            self.assertEqual(collected[i].url, f"https://example.org/{i}")
            self.assertEqual(collected[i].corpus.source_name, "test")
            self.assertEqual(collected[i].corpus.is_fix, False)
            self.assertEqual(collected[i].trace, None)
            self.assertEqual(collected[i].id, None)
