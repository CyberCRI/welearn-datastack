import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from welearn_datastack.collectors.ted_collector import TedURLCollector
from welearn_datastack.data.db_models import Corpus


class Test(TestCase):
    def setUp(self) -> None:
        self.mock_corpus = Corpus(source_name="ted", is_fix=True)

        self.ted_file_path = Path(__file__).parent / "resources" / "ted_file.json"
        with self.ted_file_path.open(mode="r") as f:
            self.ted_content = f.read()

    @patch("welearn_datastack.collectors.ted_collector.requests.post")
    def test_ted_urlcollector(self, mock_post):
        """
        Test the collect method of the TedURLCollector class, on a json file with 3 rows
        """

        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = json.loads(self.ted_content)

        ted_collector = TedURLCollector(
            corpus=self.mock_corpus,
        )
        collected = ted_collector.collect()
        self.assertEqual(3, len(collected))

        for i in range(0, len(collected)):
            self.assertEqual(
                collected[i].url, f"https://www.ted.com/talks/ted_talk_{i+1}"
            )
            self.assertEqual(collected[i].corpus.source_name, "ted")
            self.assertEqual(collected[i].corpus.is_fix, True)
