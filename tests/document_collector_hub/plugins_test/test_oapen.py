import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.rest_requesters.oapen import OAPenCollector


class MockResponse:
    def __init__(self, text_json, status_code):
        self.status_code = status_code
        self._json = text_json

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


class TestOAPenCollector(TestCase):
    def setUp(self) -> None:
        self.oapen_collector = OAPenCollector()
        self.desc_en = "At the end of the Western Middle Ages, the new notions of the legitimacy of royal power"

        self.desc_fr = "Test d'abstract pour un texte en français, je dois le faire un peu long quand même"

        self.mocked_json_ret = {
            "name": "Sample Title",
            "handle": "20.500.12657/12345",
            "bitstreams": [
                {
                    "bundleName": "original",
                    "retrieveLink": "https://example.com/sample.pdf",
                    "code": "CC-BY",
                }
            ],
            "metadata": [
                {
                    "key": "dc.description.abstract",
                    "value": self.desc_en,
                },
                {
                    "key": "oapen.abstract.otherlanguage",
                    "value": self.desc_fr,
                },
                {
                    "key": "dc.contributor.author",
                    "value": "Name, Author",
                },
                {
                    "key": "dc.language",
                    "value": "English",
                },
            ],
        }

    def test_plugin_type(self):
        self.assertEqual(OAPenCollector.collector_type_name, PluginType.REST)

    def test_plugin_related_corpus(self):
        self.assertEqual(OAPenCollector.related_corpus, "oapen")

    def test_extract_oapen_ids(self):
        tested_list = [
            "https://library.oapen.org/handle/20.500.12657/12345",
            "https://library.oapen.org/handle/20.500.12657/67890",
        ]
        self.assertEqual(
            self.oapen_collector._extract_oapen_ids(tested_list),
            ["20.500.12657/12345", "20.500.12657/67890"],
        )

    def test_get_oapen_url_from_handle_id(self):
        handle_id = "20.500.12657/12345"
        self.assertEqual(
            self.oapen_collector._get_oapen_url_from_handle_id(handle_id),
            "https://library.oapen.org/handle/20.500.12657/12345",
        )

    @patch("welearn_datastack.modules.pdf_extractor._send_pdf_to_tika")
    @patch("welearn_datastack.plugins.rest_requesters.oapen.get_new_https_session")
    def test_get_pdf_content(self, mock_get_new_https_session, mock_send_pdf_to_tika):
        class MockResponse:
            def __init__(self, status_code):
                self.content = (
                    Path(__file__).parent.parent
                    / "resources"
                    / "file_plugin_input"
                    / "hal_pdf.pdf"
                ).read_bytes()
                self.status_code = status_code

            def raise_for_status(self):
                pass

        os.environ["PDF_SIZE_PAGE_LIMIT"] = "100000"
        mock_send_pdf_to_tika.return_value = {
            "X-TIKA:content": "<div class='page'>For primary vpiRNAs that are produced from the abundant</div>"
        }

        mock_response = MockResponse(200)
        mock_get_new_https_session.return_value.get.return_value = mock_response
        pdf_content = self.oapen_collector._get_pdf_content(
            "https://example.com/sample.pdf"
        )

        self.assertIn(
            "For primary vpiRNAs that are produced from the abundant",
            pdf_content,
        )

    @patch("welearn_datastack.plugins.rest_requesters.oapen.get_new_https_session")
    def test_get_txt_content(self, mock_get_new_https_session):
        mock_response = Mock()
        mock_response.encoding = "latin-1"
        mock_response.text = "Sample TXT content. éè".encode("utf-8").decode(
            mock_response.encoding
        )
        mock_response.raise_for_status = Mock()
        mock_get_new_https_session.return_value.get.return_value = mock_response

        content = self.oapen_collector._get_txt_content(
            "https://example.com/sample.txt"
        )
        self.assertEqual(content, "Sample TXT content. éè")

    @patch("welearn_datastack.plugins.rest_requesters.oapen.get_new_https_session")
    def test_get_jsons(self, mock_get_new_https_session):
        return_json = [{"content": "Lorem ipsum"}]

        mock_session = Mock()
        mock_get_new_https_session.return_value = mock_session

        mock_response = MockResponse(return_json, status_code=200)

        mock_session.get.side_effect = [mock_response]

        oapen_ids = ["20.500.12657/12345"]
        jsons = self.oapen_collector._get_jsons(oapen_ids)
        self.assertEqual(jsons, return_json)

    def test_format_metadata(self):
        metadata = [
            {"key": "dc.title", "value": "Sample Title"},
            {"key": "dc.contributor.author", "value": "Author Name"},
        ]
        formatted_metadata = self.oapen_collector._format_metadata(metadata)
        self.assertEqual(formatted_metadata["dc.title"], "Sample Title")
        self.assertEqual(formatted_metadata["dc.contributor.author"], "Author Name")

    @patch(
        "welearn_datastack.plugins.rest_requesters.oapen.OAPenCollector._get_pdf_content"
    )
    @patch(
        "welearn_datastack.plugins.rest_requesters.oapen.OAPenCollector._get_txt_content"
    )
    def test_convert_json_dict_to_welearndoc(
        self, mock_get_txt_content, mock_get_pdf_content
    ):
        mock_get_txt_content.return_value = "Sample TXT content, lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        mock_get_pdf_content.return_value = "Sample PDF content, lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."

        json_dict = self.mocked_json_ret

        doc = self.oapen_collector._convert_json_dict_to_welearndoc(json_dict)
        self.assertIsInstance(doc, ScrapedWeLearnDocument)
        self.assertEqual(doc.document_title, "Sample Title")
        self.assertEqual(
            doc.document_content,
            "Sample PDF content, lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        )
        self.assertEqual(doc.document_desc, self.desc_en)
        self.assertEqual(doc.document_details["authors"][0]["name"], "Author Name")
        self.assertEqual(doc.document_lang, "en")

    @patch(
        "welearn_datastack.plugins.rest_requesters.oapen.OAPenCollector._get_pdf_content"
    )
    @patch(
        "welearn_datastack.plugins.rest_requesters.oapen.OAPenCollector._get_txt_content"
    )
    def test_convert_json_dict_to_welearndoc_in_other_lang(
        self, mock_get_txt_content, mock_get_pdf_content
    ):
        mock_get_txt_content.return_value = "Sample TXT content, lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        mock_get_pdf_content.return_value = "Sample PDF content, lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."

        json_dict = self.mocked_json_ret
        json_dict["metadata"][3]["value"] = "French"

        doc = self.oapen_collector._convert_json_dict_to_welearndoc(json_dict)
        self.assertIsInstance(doc, ScrapedWeLearnDocument)
        self.assertEqual(doc.document_title, "Sample Title")
        self.assertEqual(
            doc.document_content,
            "Sample PDF content, lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        )
        self.assertEqual(
            doc.document_desc,
            self.desc_fr,
        )
        self.assertEqual(doc.document_details["authors"][0]["name"], "Author Name")
        self.assertEqual(doc.document_lang, "fr")

    @patch(
        "welearn_datastack.plugins.rest_requesters.oapen.OAPenCollector._get_pdf_content"
    )
    @patch(
        "welearn_datastack.plugins.rest_requesters.oapen.OAPenCollector._get_txt_content"
    )
    @patch("welearn_datastack.plugins.rest_requesters.oapen.OAPenCollector._get_jsons")
    def test_run(self, mock_get_jsons, mock_get_txt_content, mock_get_pdf):
        mock_get_txt_content.return_value = "Sample TXT content, lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
        json_dict = self.mocked_json_ret
        json_dict["bitstreams"].append(
            {
                "bundleName": "text",
                "retrieveLink": "https://example.com/sample.pdf.txt",
                "code": "Other license",
            }
        )
        mock_get_jsons.return_value = [json_dict]

        urls = ["https://library.oapen.org/handle/20.500.12657/12345"]
        res, errors = self.oapen_collector.run(urls_or_external_ids=urls)
        self.assertEqual(len(res), 1)
        self.assertEqual(len(errors), 0)
        self.assertEqual(
            res[0].document_url, "https://library.oapen.org/handle/20.500.12657/12345"
        )
        self.assertEqual(res[0].document_title, "Sample Title")
        self.assertEqual(
            res[0].document_content,
            "Sample TXT content, lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        )
        self.assertEqual(res[0].document_desc, self.desc_en)
        self.assertEqual(res[0].document_details["authors"][0]["name"], "Author Name")
        self.assertEqual(res[0].document_lang, "en")
        self.assertEqual(res[0].document_corpus, "oapen")
        self.assertEqual(
            res[0].document_details["license"],
            "https://creativecommons.org/licenses/by/4.0/",
        )

    def test_clean_backline(self):
        tested_line0 = "Lin-\nguistique"
        awaited0 = "Linguistique"

        tested_line1 = "lorem ipsum\n \nLe Volume :"
        awaited1 = "lorem ipsum Le Volume :"

        self.assertEqual(self.oapen_collector.clean_backline(tested_line0), awaited0)
        self.assertEqual(self.oapen_collector.clean_backline(tested_line1), awaited1)

        test_line2 = """La Tribune de Genève : 03�11�2015�\n \nLe Volume : 05�10�1901�\n 587\n \n \nCorpus consultés\n \nCorpus oraux\n \nCorpus Enquêtes SocioLinguistiques à Orléans (ESLO1 et ESLO2)\nLe corpus ESLO est un projet du LLL (Laboratoire Ligérien de Lin-\nguistique) de l’Université d’Orléans�\nRéférence : BAUDE Olivier & DUGUA Céline (2016), «\xa0Les ESLO, du \nportrait sonore au paysage digital\xa0», Corpus 15, p� 29–56�\nLien du corpus : http://eslo.huma-num.fr\n"""
        awaited2 = "La Tribune de Genève : 03�11�2015� Le Volume : 05�10�1901� 587 Corpus consultés Corpus oraux Corpus Enquêtes SocioLinguistiques à Orléans (ESLO1 et ESLO2) Le corpus ESLO est un projet du LLL (Laboratoire Ligérien de Linguistique) de l’Université d’Orléans� Référence : BAUDE Olivier & DUGUA Céline (2016), « Les ESLO, du portrait sonore au paysage digital », Corpus 15, p� 29–56� Lien du corpus : http://eslo.huma-num.fr"

        self.assertEqual(self.oapen_collector.clean_backline(test_line2), awaited2)
