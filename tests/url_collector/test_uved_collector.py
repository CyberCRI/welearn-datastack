import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.uved_collector import UVEDURLCollector


class MockResponse:
    def __init__(self, text, status_code):
        self.text = text
        self.status_code = status_code
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(self.text)


class TestUVEDCollector(TestCase):
    def setUp(self) -> None:
        self.mock_corpus = Corpus(source_name="uved", is_fix=True)

        self.uved_file_path = Path(__file__).parent / "resources" / "uved_file.json"
        with self.uved_file_path.open(mode="r") as f:
            self.uved_content = f.read()

        self.slugs = [
            "parcours-20h-sur-les-enseignements-teds",
            "parcours-10h-sur-les-enseignements-teds",
            "le-socio-ecosysteme-portuaire-et-son-ecologisation",
        ]

        self.external_ids = [
            5159,
            5158,
            5157,
        ]

    @patch("welearn_datastack.collectors.uved_collector.get_new_https_session")
    def test_uved_urlcollector(self, mock_get_new_http_session):
        mock_session = Mock()
        mock_session.get.return_value = MockResponse(self.uved_content, 200)
        mock_get_new_http_session.return_value = mock_session

        uved_collector = UVEDURLCollector(
            corpus=self.mock_corpus,
        )
        collected = uved_collector.collect()
        self.assertEqual(3, len(collected))

        for i in range(0, len(collected)):
            self.assertEqual(
                collected[i].url,
                f"https://www.uved.fr/fiche/ressource/{self.slugs[i]}",
            )
            self.assertEqual(collected[i].external_id, self.external_ids[i])
            self.assertEqual(collected[i].corpus.source_name, "uved")
            self.assertEqual(collected[i].corpus.is_fix, True)
