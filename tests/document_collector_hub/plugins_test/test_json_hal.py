import json
import os
import unittest
from pathlib import Path

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.files_readers.hal import JsonHALCollector


class TestXMLPLOSPlugin(unittest.TestCase):
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

        self.hal_collector = JsonHALCollector()

    def tearDown(self) -> None:
        os.environ.clear()

    def test_plugin_type(self):
        self.assertEqual(JsonHALCollector.collector_type_name, PluginType.FILES)

    def test_plugin_related_corpus(self):
        self.assertEqual(JsonHALCollector.related_corpus, "json_hal")

    def test_plugin_files_locations(self):
        self.assertEqual(
            self.hal_collector._files_locations,
            [self.mock_file_path.parent / "hal_test.json"],
        )

    def test_plugin_run(self):
        urls = [
            "https://example.org/halshs-01057493",
            "https://example.org/hal-01057494",
            "https://example.org/hal-01000000",
        ]
        res, errors = self.hal_collector.run(urls_or_external_ids=urls)

        awaited_docs = self.content_json["response"]["docs"]

        self.assertEqual(len(res), 2)

        # Check data in details
        details0 = res[0].document_details
        details1 = res[1].document_details

        self.assertListEqual(
            details0["authors"],
            [{"name": name, "misc": ""} for name in awaited_docs[0]["authFullName_s"]],
        )
        self.assertListEqual(
            details1["authors"],
            [{"name": name, "misc": ""} for name in awaited_docs[1]["authFullName_s"]],
        )
        self.assertEqual(res[0].document_url, awaited_docs[0]["uri_s"])
        self.assertEqual(res[1].document_url, awaited_docs[1]["uri_s"])
        all_urls_in_res = [doc.document_url for doc in res]
        self.assertNotIn(urls[2], all_urls_in_res)

    def test_plugin_run_no_urls(self):
        res, errors = self.hal_collector.run(urls_or_external_ids=[])
        self.assertEqual(len(res), 0)

    def test_filter_csv_line(self):
        with self.mock_file_path.open(mode="r") as file:
            json_content = json.load(file)
            filtered = self.hal_collector._filter_file_line(
                dr=json_content.get("response").get("docs"),
                urls=["https://example.org/halshs-01057493"],
                url_label="uri_s",
            )

            nb_iter = 0
            for line in filtered:
                nb_iter += 1
                self.assertEqual(line["uri_s"], "https://example.org/halshs-01057493")

            self.assertEqual(nb_iter, 1)

    def test_get_details_from_line(self):
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

    def test_convert_csv_line_to_welearndoc(self):
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
