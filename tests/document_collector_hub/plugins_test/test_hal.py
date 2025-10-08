import json
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.rest_requesters.hal import HALCollector


class TestHALCollector(TestCase):
    def setUp(self) -> None:
        ressources_folder = (
            Path(__file__).parent.parent
            / "resources"
            / "file_plugin_input"
            / "JsonHALCollector"
        )

        os.environ["JSONHALCOLLECTOR_FILE_NAME"] = "hal_test.json"
        os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"] = (
            ressources_folder.parent.as_posix()
        )

        mock_file_path = ressources_folder / "hal_test.json"
        mock_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.mock_file_path = mock_file_path

        with self.mock_file_path.open(mode="r") as file:
            self.content_json = json.load(file)

        self.hal_collector = HALCollector()

    def tearDown(self) -> None:
        os.environ.clear()

    def test_plugin_type(self):
        self.assertEqual(HALCollector.collector_type_name, PluginType.REST)

    def test_plugin_related_corpus(self):
        self.assertEqual(HALCollector.related_corpus, "hal")

    def test__convert_hal_date_to_ts(self):
        tested_str = "2006-01-01T00:00:00Z"
        self.assertEqual(
            self.hal_collector._convert_hal_date_to_ts(tested_str), 1136073600.0
        )

    def test__get_url_without_hal_versionning(self):
        tested_json_dict = {
            "uri_s": "https://hal.archives-ouvertes.fr/hal-00006805v1",
            "docid": "00006805",
        }

        self.assertEqual(
            self.hal_collector._get_url_without_hal_versionning(tested_json_dict),
            "https://hal.archives-ouvertes.fr/hal-00006805",
        )

        tested_json_dict = {
            "uri_s": "https://in2p3.hal.science/in2p3-00006402v1",
            "docid": "10010",
        }

        self.assertEqual(
            "https://in2p3.hal.science/in2p3-00006402",
            self.hal_collector._get_url_without_hal_versionning(tested_json_dict),
        )

        tested_json_dict = {
            "uri_s": "https://unvip1.hal.science/univp1-00006402v1",
            "docid": "10010",
        }

        self.assertEqual(
            "https://unvip1.hal.science/univp1-00006402",
            self.hal_collector._get_url_without_hal_versionning(tested_json_dict),
        )

    def test__format_hal_ids(self):
        tested_list = ["hal-00006805", "hal-00333300"]
        self.assertEqual(
            self.hal_collector._create_halids_query(tested_list),
            "halId_s:(hal-00006805 OR hal-00333300)",
        )

        tested_list = ["hal-00006805"]
        self.assertEqual(
            self.hal_collector._create_halids_query(tested_list), "halId_s:hal-00006805"
        )

    def test_get_details_from_dict(self):
        details = self.hal_collector._get_details_from_dict(
            self.content_json["response"]["docs"][0]
        )
        self.assertListEqual(
            details["authors"],
            [
                {"name": name, "misc": ""}
                for name in self.content_json["response"]["docs"][0]["authFullName_s"]
            ],
        )
        self.assertEqual(details["docid"], "1057493")
        self.assertEqual(details["type"], "article")
        self.assertEqual(details["produced_date"], 1388534400.0)
        self.assertEqual(details["publication_date"], 1388534400.0)

    @patch(
        "welearn_datastack.plugins.rest_requesters.hal.HAL_URL_BASE",
        "https://example.org/",
    )
    def test__convert_json_dict_to_welearndoc(self):
        doc0 = self.content_json["response"]["docs"][0]

        doc = self.hal_collector._convert_json_dict_to_welearndoc(doc0)
        self.assertEqual(doc.document_url, doc0["uri_s"])
        self.assertEqual(doc.document_title, doc0["title_s"][0])
        self.assertEqual(doc.document_lang, doc0["language_s"][0])
        self.assertEqual(
            doc.document_content,
            doc0["abstract_s"][0],
        )
        self.assertEqual(
            doc.document_desc,
            doc0["abstract_s"][0].split(".")[0] + "...",
        )

    @patch("welearn_datastack.modules.pdf_extractor._send_pdf_to_tika")
    @patch(
        "welearn_datastack.plugins.rest_requesters.hal.HAL_URL_BASE",
        "https://example.org/",
    )
    @patch("requests.Session.get")
    def test__convert_json_dict_to_welearndoc_mode_pdf(
        self, mock_get, mock_send_pdf_to_tika
    ):
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

        mock_send_pdf_to_tika.return_value = {
            "X-TIKA:content": "<div class='page'>For primary vpiRNAs that are produced from the abundant</div>"
        }
        mock_get.side_effect = [MockResponse(200)]
        os.environ["PDF_SIZE_PAGE_LIMIT"] = "100000"
        doc0 = self.content_json["response"]["docs"][0]
        doc0["licence_s"] = "http://creativecommons.org/licenses/by/"
        doc0["fileMain_s"] = "https://hal.example.org/hal-01057493/file/2014-01-01.pdf"
        doc = self.hal_collector._convert_json_dict_to_welearndoc(doc0)
        self.assertEqual(doc.document_url, doc0["uri_s"])
        self.assertEqual(doc.document_title, doc0["title_s"][0])
        self.assertEqual(doc.document_lang, "en")
        self.assertIn(
            "For primary vpiRNAs that are produced from the abundant",
            doc.document_content,
        )
        self.assertEqual(
            doc.document_desc,
            doc0["abstract_s"][0].strip() + "...",
        )

    def test__extract_hal_ids(self):
        tested_list = [
            "https://hal.archives-ouvertes.fr/hal-00006805",
            "https://hal.archives-ouvertes.fr/hal-00333300",
        ]
        self.assertEqual(
            self.hal_collector._extract_hal_ids(tested_list),
            ["hal-00006805", "hal-00333300"],
        )

    @patch("requests.Session.get")
    def test__get_json(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = self.content_json
        res = self.hal_collector._get_jsons(hal_ids=["halshs-01057493", "hal-01057494"])
        self.assertEqual(res, self.content_json["response"]["docs"])
        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, "https://api.archives-ouvertes.fr/search/")
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(
            called_params["q"], "halId_s:(halshs-01057493 OR hal-01057494)"
        )
        self.assertEqual(
            called_params["doctype_s"], self.hal_collector._query_params_doctype_s
        )
        self.assertEqual(called_params["fl"], self.hal_collector._query_params_fl)
        self.assertEqual(called_params["wt"], self.hal_collector._query_params_wt)
        self.assertEqual(called_params["sort"], self.hal_collector._query_params_sort)

    @patch("welearn_datastack.plugins.rest_requesters.hal.HALCollector._get_jsons")
    def test_run(self, mock_get_jsons):
        docs_from_json = self.content_json["response"]["docs"]
        mock_get_jsons.return_value = docs_from_json

        list_of_awaited_scraped_welearn_doc = [
            self.hal_collector._convert_json_dict_to_welearndoc(doc)
            for doc in docs_from_json
        ]

        urls = [doc["uri_s"] for doc in docs_from_json]
        res, errors = self.hal_collector.run(urls_or_external_ids=urls)
        self.assertEqual(len(res), len(urls))
        self.assertEqual(len(errors), 0)

        for i in range(len(res)):
            self.assertEqual(
                res[i].document_url, list_of_awaited_scraped_welearn_doc[i].document_url
            )
            self.assertEqual(
                res[i].document_title,
                list_of_awaited_scraped_welearn_doc[i].document_title,
            )
            self.assertEqual(
                res[i].document_lang,
                list_of_awaited_scraped_welearn_doc[i].document_lang,
            )
            self.assertEqual(
                res[i].document_desc,
                list_of_awaited_scraped_welearn_doc[i].document_desc,
            )
            self.assertEqual(
                res[i].document_content,
                list_of_awaited_scraped_welearn_doc[i].document_content,
            )
            self.assertEqual(
                res[i].document_details,
                list_of_awaited_scraped_welearn_doc[i].document_details,
            )
            self.assertEqual(
                res[i].document_corpus,
                list_of_awaited_scraped_welearn_doc[i].document_corpus,
            )
