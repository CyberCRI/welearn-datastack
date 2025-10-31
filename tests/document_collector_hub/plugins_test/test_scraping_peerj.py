import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup  # type: ignore
from requests import HTTPError  # type: ignore
from welearn_database.data.models import WeLearnDocument

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

        self.collector = PeerJCollector()
        self.doc = WeLearnDocument(id=1, url="https://example.org/1")

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        self.assertEqual(PluginType.SCRAPE, PeerJCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(PeerJCollector.related_corpus, "peerj")

    @patch("welearn_datastack.plugins.scrapers.peerj.get_new_https_session")
    def test_plugin_run_success(self, mock_get_session):
        # Mock the HTTPS session and its get method for a successful scrape
        mock_session = MagicMock()
        mock_session.get.return_value.text = self.page_1
        mock_session.get.return_value.status_code = 200
        mock_session.get.return_value.raise_for_status = lambda: None
        mock_get_session.return_value = mock_session

        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        doc_result = result[0]
        self.assertIsNone(doc_result.error_info)
        self.assertIsInstance(doc_result.document, WeLearnDocument)
        self.assertEqual(doc_result.document.url, self.doc.url)
        self.assertTrue(doc_result.document.title)
        self.assertTrue(doc_result.document.description)
        self.assertTrue(doc_result.document.full_content)
        self.assertIsInstance(doc_result.document.details, dict)
        self.assertIn("license_url", doc_result.document.details)
        self.assertIn("authors", doc_result.document.details)
        self.assertIn("journal", doc_result.document.details)
        self.assertIn("tags", doc_result.document.details)
        self.assertIn("doi", doc_result.document.details)
        self.assertIn("issn", doc_result.document.details)
        self.assertIn("publisher", doc_result.document.details)
        self.assertIn("publication_date", doc_result.document.details)

    @patch("welearn_datastack.plugins.scrapers.peerj.get_new_https_session")
    def test_plugin_run_http_error(self, mock_get_session):
        # Simulate an HTTP error (e.g., 503)
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        # Patch the HTTPError to have a response with status_code
        http_error = HTTPError("503 Server Error: Service Unavailable")
        http_error.response = MagicMock()
        http_error.response.status_code = 503
        mock_response.raise_for_status.side_effect = http_error
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIsInstance(result[0].document, WeLearnDocument)
        self.assertEqual(result[0].document.url, self.doc.url)

    @patch("welearn_datastack.plugins.scrapers.peerj.get_new_https_session")
    def test_plugin_run_invalid_html(self, mock_get_session):
        # Simulate invalid HTML (missing required fields)
        mock_session = MagicMock()
        mock_session.get.return_value.text = "<html><body>No article meta</body></html>"
        mock_session.get.return_value.status_code = 200
        mock_session.get.return_value.raise_for_status = lambda: None
        mock_get_session.return_value = mock_session
        result = self.collector.run([self.doc])
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIsInstance(result[0].document, WeLearnDocument)
        self.assertEqual(result[0].document.url, self.doc.url)

    @patch("welearn_datastack.plugins.scrapers.peerj.get_new_https_session")
    def test_plugin_run_empty_input(self, mock_get_session):
        # Test with empty input list
        result = self.collector.run([])
        self.assertEqual(result, [])

    def test_figure_to_paragraph(self):
        # Test the conversion of a table/figure to paragraph
        awaited_paragraph = """Species-level scientific names erected for the members of the subgenus Pareas: No: 1, Authority: Wagler (1830), Original taxon name: Pareas carinata, Type locality: Java, Indonesia, Previous taxonomy: Pareas carinatus, New taxonomy: Pareas carinatus.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 2, Authority: Theobald (1868), Original taxon name: Pareas berdmorei, Type locality: Mon State, Myanmar, Previous taxonomy: synonym of Pareas carinatus, New taxonomy: Pareas berdmorei.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 3, Authority: Boulenger (1900), Original taxon name: Amblycephalus nuchalis, Type locality: Matang, Kidi District, Sarawak, Malaysia, Previous taxonomy: Pareas nuchalis, New taxonomy: Pareas nuchalis.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 4, Authority: Bourret (1934), Original taxon name: Amblycephalus carinatus unicolor, Type locality: Kampong Speu Province, Cambodia, Previous taxonomy: synonym of Pareas carinatus, New taxonomy: Pareas berdmorei unicolor comb. nov.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 5, Authority: Wang et al. (2020), Original taxon name: Pareas menglaensis, Type locality: Mengla County, Yunnan Province, China, Previous taxonomy: Pareas menglaensis, New taxonomy: synonym of Pareas berdmorei.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 6, Authority: Le et al. (2021), Original taxon name: Pareas temporalis, Type locality: Doan Ket Commune, Da Huoai District, Lam Dong Province, Vietnam, Previous taxonomy: Pareas temporalis, New taxonomy: Pareas temporalis.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 7, Authority: this paper, Original taxon name: Pareas carinatus tenasserimicus, Type locality: Suan Phueng District, Ratchaburi Province, Thailand, Previous taxonomy: -, New taxonomy: Pareas carinatus tenasserimicus ssp. nov.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 8, Authority: this paper, Original taxon name: Pareas berdmorei truongsonicus, Type locality: Nahin District, Khammouan Province, Laos, Previous taxonomy: -, New taxonomy: Pareas berdmorei truongsonicus ssp. nov.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 9, Authority: this paper, Original taxon name: Pareas kuznetsovorum, Type locality: Song Hinh District, Phu Yen Province, Vietnam, Previous taxonomy: -, New taxonomy: Pareas kuznetsovorum sp. nov.\nSpecies-level scientific names erected for the members of the subgenus Pareas: No: 10, Authority: this paper, Original taxon name: Pareas abros, Type locality: Song Thanh N.P., Quang Nam Province, Vietnam, Previous taxonomy: -, New taxonomy: Pareas abros sp. nov.\n"""
        html_table_path = Path(__file__).parent.parent / "resources/test_table.html"
        with open(html_table_path, "r") as file:
            soup = BeautifulSoup(file, "html.parser")
        self.assertEqual(
            self.collector._figure_to_paragraph(soup),
            awaited_paragraph,
        )
