import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup  # type: ignore
from requests import HTTPError  # type: ignore

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.scrapers.peerj import PeerJCollector


class TestScrapePeerJPlugin(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        req_page_content_path1 = (
            Path(__file__).parent.parent
            / "resources/file_plugin_input/page_peerj1.html"
        )

        with req_page_content_path1.open(mode="r") as file1:
            self.page_1 = file1.read()

        self.pages_list = [self.page_1]

        self.conversation_scraper = PeerJCollector()

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        self.assertEqual(PluginType.SCRAPE, PeerJCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(PeerJCollector.related_corpus, "peerj")

    @patch("requests.sessions.Session.get")
    def test_plugin_run(self, mock_get) -> None:
        awaited_details_1: dict = {
            "publication_date": 1641772800.0,
            "doi": "10.7717/peerj.12713",
            "tags": [
                "Pareas",
                "Asthenodipsas",
                "Aplopeltura",
                "Eberhardtia",
                "Spondylodipsas",
                "Molecular phylogeny",
                "Biogeography",
                "Southeast Asia",
                "Sundaland",
                "Cryptic species",
            ],
            "journal": "PeerJ",
            "publisher": "PeerJ Inc.",
            "issn": "2167-8359",
            "authors": [
                {
                    "name": "Nikolay A. Poyarkov",
                    "misc": "Laboratory of Tropical Ecology, Joint Russian-Vietnamese Tropical Research and Technological Center, Hanoi, Vietnam, Faculty of Biology, Department of Vertebrate Zoology, Moscow State University, Moscow, Russia",
                },
                {
                    "name": "Tan Van Nguyen",
                    "misc": "Department of Species Conservation, Save Vietnam’s Wildlife, Ninh Binh, Vietnam",
                },
                {
                    "name": "Parinya Pawangkhanant",
                    "misc": "Division of Fishery, School of Agriculture and Natural Resources, University of Phayao, Phayao, Thailand",
                },
                {
                    "name": "Platon V. Yushchenko",
                    "misc": "Faculty of Biology, Department of Vertebrate Zoology, Moscow State University, Moscow, Russia",
                },
                {"name": "Peter Brakels", "misc": "IUCN Laos PDR, Vientiane, Lao PDR"},
                {
                    "name": "Linh Hoang Nguyen",
                    "misc": "Department of Zoology, Southern Institute of Ecology, Vietnam Academy of Science and Technology, Ho Chi Minh City, Vietnam",
                },
                {
                    "name": "Hung Ngoc Nguyen",
                    "misc": "Department of Zoology, Southern Institute of Ecology, Vietnam Academy of Science and Technology, Ho Chi Minh City, Vietnam",
                },
                {
                    "name": "Chatmongkon Suwannapoom",
                    "misc": "Division of Fishery, School of Agriculture and Natural Resources, University of Phayao, Phayao, Thailand",
                },
                {
                    "name": "Nikolai Orlov",
                    "misc": "Department of Herpetology, Zoological Institute, Russian Academy of Sciences, St. Petersburg, Russia",
                },
                {
                    "name": "Gernot Vogel",
                    "misc": "Society for Southeast Asian Herpetology, Heidelberg, Germany",
                },
            ],
            "readability": "57.8",
            "duration": "8596",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
        }

        class MockResponse:
            def __init__(self, text, status_code):
                self.text = text
                self.status_code = status_code

            def raise_for_status(self):
                pass

        mock_get.side_effect = [
            MockResponse(text, 200) for text in self.pages_list[0:1]
        ]

        scraped_docs, error_docs = self.conversation_scraper.run(
            urls=["https://example.org/1"]
        )

        self.assertEqual(len(scraped_docs), 1)
        self.assertEqual(len(error_docs), 0)

        doc = scraped_docs[0]
        self.assertEqual(doc.document_corpus, "peerj")
        self.assertEqual(doc.document_url, "https://example.org/1")
        self.assertEqual(
            doc.document_title,
            "An integrative taxonomic revision of slug-eating snakes (Squamata: Pareidae: Pareineae) reveals "
            "unprecedented diversity in Indochina",
        )
        self.assertEqual(doc.document_lang, "en")
        self.assertDictEqual(doc.document_details, awaited_details_1)

    @patch("requests.sessions.Session.get")
    def test_plugin_run_but_503_occured(self, mock_get):
        mock_get.return_value.status_code = 503
        mock_get.return_value.raise_for_status.side_effect = HTTPError(
            "503 Server Error: Service Unavailable"
        )
        mock_get.return_value.json.side_effect = self.pages_list[0:1]

        scraped_docs, error_urls = self.conversation_scraper.run(
            urls=["https://example.org/1"]
        )

        self.assertEqual(len(scraped_docs), 0)
        self.assertEqual(len(error_urls), 1)

        url = error_urls[0]
        self.assertEqual(url, "https://example.org/1")

    def test_figure_to_paragraph(self):
        awaited_paragraph = """Species-level scientific names erected for the members of the subgenus Pareas: No: 1, Authority: Wagler (1830), Original taxon name: Pareas carinata, Type locality: Java, Indonesia, Previous taxonomy: Pareas carinatus, New taxonomy: Pareas carinatus.
Species-level scientific names erected for the members of the subgenus Pareas: No: 2, Authority: Theobald (1868), Original taxon name: Pareas berdmorei, Type locality: Mon State, Myanmar, Previous taxonomy: synonym of Pareas carinatus, New taxonomy: Pareas berdmorei.
Species-level scientific names erected for the members of the subgenus Pareas: No: 3, Authority: Boulenger (1900), Original taxon name: Amblycephalus nuchalis, Type locality: Matang, Kidi District, Sarawak, Malaysia, Previous taxonomy: Pareas nuchalis, New taxonomy: Pareas nuchalis.
Species-level scientific names erected for the members of the subgenus Pareas: No: 4, Authority: Bourret (1934), Original taxon name: Amblycephalus carinatus unicolor, Type locality: Kampong Speu Province, Cambodia, Previous taxonomy: synonym of Pareas carinatus, New taxonomy: Pareas berdmorei unicolor comb. nov.
Species-level scientific names erected for the members of the subgenus Pareas: No: 5, Authority: Wang et al. (2020), Original taxon name: Pareas menglaensis, Type locality: Mengla County, Yunnan Province, China, Previous taxonomy: Pareas menglaensis, New taxonomy: synonym of Pareas berdmorei.
Species-level scientific names erected for the members of the subgenus Pareas: No: 6, Authority: Le et al. (2021), Original taxon name: Pareas temporalis, Type locality: Doan Ket Commune, Da Huoai District, Lam Dong Province, Vietnam, Previous taxonomy: Pareas temporalis, New taxonomy: Pareas temporalis.
Species-level scientific names erected for the members of the subgenus Pareas: No: 7, Authority: this paper, Original taxon name: Pareas carinatus tenasserimicus, Type locality: Suan Phueng District, Ratchaburi Province, Thailand, Previous taxonomy: -, New taxonomy: Pareas carinatus tenasserimicus ssp. nov.
Species-level scientific names erected for the members of the subgenus Pareas: No: 8, Authority: this paper, Original taxon name: Pareas berdmorei truongsonicus, Type locality: Nahin District, Khammouan Province, Laos, Previous taxonomy: -, New taxonomy: Pareas berdmorei truongsonicus ssp. nov.
Species-level scientific names erected for the members of the subgenus Pareas: No: 9, Authority: this paper, Original taxon name: Pareas kuznetsovorum, Type locality: Song Hinh District, Phu Yen Province, Vietnam, Previous taxonomy: -, New taxonomy: Pareas kuznetsovorum sp. nov.
Species-level scientific names erected for the members of the subgenus Pareas: No: 10, Authority: this paper, Original taxon name: Pareas abros, Type locality: Song Thanh N.P., Quang Nam Province, Vietnam, Previous taxonomy: -, New taxonomy: Pareas abros sp. nov.
"""

        html_table_path = Path(__file__).parent.parent / "resources/test_table.html"

        with open(html_table_path, "r") as file:
            soup = BeautifulSoup(file, "html.parser")

        self.assertEqual(
            self.conversation_scraper._figure_to_paragraph(soup),
            awaited_paragraph,
        )
