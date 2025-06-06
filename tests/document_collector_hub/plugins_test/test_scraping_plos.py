import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup  # type: ignore
from requests import HTTPError  # type: ignore

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.scrapers.plos import PlosCollector


class TestScrapePlosPlugin(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        req_page_content_path1 = (
            Path(__file__).parent.parent / "resources/file_plugin_input/page_plos1.xml"
        )

        with req_page_content_path1.open(mode="r") as file1:
            self.page_content_1 = file1.read()

        self.pages_list = [self.page_content_1]

        os.environ["SCRAPING_SERVICE_ADRESS"] = "http://example.org/scrape"
        self.plos_scraper = PlosCollector()

        details_file_path: Path = (
            Path(__file__).parent.parent
            / "resources/file_plugin_input/details_plos.json"
        )
        with details_file_path.open(mode="r") as file:
            self.awaited_details = json.load(file)

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        self.assertEqual(PluginType.SCRAPE, PlosCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(PlosCollector.related_corpus, "plos")

    @patch("requests.sessions.Session.get")
    def test_plugin_run(self, mock_get) -> None:
        awaited_details_1: dict = {
            "authors": [
                {
                    "name": "Metaane Selma",
                    "misc": "Institut Pasteur, Université de Paris, CNRS UMR3528, Biochimie des Interactions Macromoléculaires, F-75015, Paris, France",
                },
                {
                    "name": "Monteil Véronique",
                    "misc": "Institut Pasteur, Université de Paris, CNRS UMR3528, Biochimie des Interactions Macromoléculaires, F-75015, Paris, France",
                },
                {
                    "name": "Ayrault Sophie",
                    "misc": "Laboratoire des Sciences du Climat et de l’Environnement, LSCE/IPSL, CEA-CNRS-UVSQ, Université Paris-Saclay, 91191, Gif-sur-Yvette, France",
                },
                {
                    "name": "Bordier Louise",
                    "misc": "Laboratoire des Sciences du Climat et de l’Environnement, LSCE/IPSL, CEA-CNRS-UVSQ, Université Paris-Saclay, 91191, Gif-sur-Yvette, France",
                },
                {
                    "name": "Levi-Meyreuis Corinne",
                    "misc": "Institut Pasteur, Université de Paris, CNRS UMR3528, Biochimie des Interactions Macromoléculaires, F-75015, Paris, France",
                },
                {
                    "name": "Norel Françoise",
                    "misc": "Institut Pasteur, Université de Paris, CNRS UMR3528, Biochimie des Interactions Macromoléculaires, F-75015, Paris, France",
                },
            ],
            "doi": "10.1371/journal.pone.0265511",
            "published_id": "PONE-D-21-39826",
            "journal": "PLOS ONE",
            "type": "Research Article",
            "publication_date": 1648684800,
            "issn": "1932-6203",
            "license_url": "http://creativecommons.org/licenses/by/4.0/",
            "publisher": "Public Library of Science, San Francisco, CA USA",
            "readability": "49.66",
            "duration": "1578",
            "content_and_description_lang": {
                "are_different": False,
                "content_lang": "en",
                "description_lang": "en",
            },
        }

        class MockResponse:
            def __init__(self, text, status_code):
                self.text = text
                self.status_code = status_code

            def raise_for_status(self):
                pass

        mock_get.side_effect = [MockResponse(text, 200) for text in self.pages_list]

        scraped_docs, error_docs = self.plos_scraper.run(
            urls=["https://example.org/plosone/article?id=10.1371/journal.pone.0265511"]
        )

        self.assertEqual(len(scraped_docs), 1)
        self.assertEqual(len(error_docs), 0)

        doc = scraped_docs[0]
        self.assertEqual(doc.document_corpus, "plos")

        self.assertFalse(doc.document_desc.split()[0] == "Abstract")

        self.assertEqual(
            doc.document_title,
            "The stress sigma factor σS/RpoS counteracts Fur repression of genes involved in iron and manganese "
            "metabolism and modulates the ionome of Salmonella enterica serovar Typhimurium",
        )
        self.assertEqual(
            "https://example.org/plosone/article?id=10.1371/journal.pone.0265511",
            doc.document_url,
        )
        self.assertEqual(doc.document_lang, "en")
        self.assertEqual(doc.trace, 2540387952)

        del doc.document_details["tags"]  # Tags are annoying to test
        self.assertDictEqual(doc.document_details, awaited_details_1)

    def test_generate_api_url(self):
        awaited_url = "https://example.org/plosone/article/file?id=10.1371/journal.pone.0265511&type=manuscript"
        input_url = (
            "https://example.org/plosone/article?id=10.1371/journal.pone.0265511"
        )
        generated_url = self.plos_scraper._generate_api_url(input_url)
        self.assertEqual(awaited_url, generated_url)
