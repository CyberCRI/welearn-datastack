from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from welearn_datastack.collectors.atom_collector import AtomURLCollector
from welearn_datastack.data.db_models import Corpus


class Test(TestCase):
    def setUp(self) -> None:
        self.rss_file_path = Path(__file__).parent / "resources" / "atom_file.xml"
        self.mock_corpus = Corpus(source_name="test", is_fix=True)
        with self.rss_file_path.open(mode="r") as f:
            self.rss_content = f.read()

    @patch("welearn_datastack.collectors.atom_collector.get_new_https_session")
    def test_atom_urlcollector(self, mock_get_new_https_session):
        """
        Test the collect method of the AtomURLCollector class, on a rss file with 3 rows
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_get_new_https_session.return_value = mock_session
        mock_session.ok.return_value = True
        mock_session.get.return_value = mock_response

        mock_response.content = self.rss_content.encode("utf-8")

        rss_collector = AtomURLCollector(
            feed_url="https://www.example.com",
            corpus=self.mock_corpus,
        )
        collected = rss_collector.collect()
        self.assertEqual(3, len(collected))

        for i in range(0, len(collected)):
            self.assertEqual(collected[i].url, f"https://www.example.com/entry{i+1}")
            self.assertEqual(collected[i].corpus.source_name, "test")
            self.assertEqual(collected[i].corpus.is_fix, True)
