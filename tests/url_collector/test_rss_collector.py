from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.rss_collector import RssURLCollector


class Test(TestCase):
    def setUp(self) -> None:
        self.mock_corpus = Corpus(source_name="test", is_fix=False)
        self.rss_file_path = Path(__file__).parent / "resources" / "rss_file.rss"
        with self.rss_file_path.open(mode="r") as f:
            self.rss_content = f.read()

    @patch("welearn_datastack.collectors.rss_collector.get_new_https_session")
    def test_rss_urlcollector(self, mock_get_new_https_session):
        """
        Test the collect method of the RSSURLCollector class, on a rss file with 3 rows
        """

        mock_session = Mock()
        mock_response = Mock()
        mock_get_new_https_session.return_value = mock_session
        mock_session.ok.return_value = True
        mock_session.get.return_value = mock_response

        mock_response.content = self.rss_content.encode("utf-8")

        rss_collector = RssURLCollector(
            feed_url="https://www.example.com", corpus=self.mock_corpus
        )
        collected = rss_collector.collect()
        self.assertEqual(3, len(collected))

        for i in range(0, len(collected)):
            self.assertEqual(collected[i].url, f"https://www.example.com/article{i+1}")
            self.assertEqual(collected[i].corpus.source_name, "test")
            self.assertEqual(collected[i].corpus.is_fix, False)
            self.assertEqual(collected[i].external_id, f"guid-article-{i+1}")
