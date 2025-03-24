import csv
import os
import shutil
import unittest
from copy import copy
from pathlib import Path
from unittest import TestCase

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.files_readers.ted import CSVTedCollector
from welearn_datastack.plugins.interface import IPluginFilesCollector

rows = [
    {
        "url": "https://www.example.com/0",
        "title": "The Irish Times",
        "description": "The Irish Times online. Latest news...",
        "lang": "en",
        "content": "The latest Irish and international news, business and sport. "
        "Today at 12:00, 15:00 and 17:00 and exclusive podcasts with our award-winning journalists.",
        "id": "123",
        "speaker": "John Doe",
        "duration": "5",
    },
    {
        "url": "https://www.example.com/1",
        "title": "El Mundo",
        "description": "Noticias de última hora...",
        "lang": "es",
        "content": "Noticias de última hora, actualidad, deportes y economía de España y el mundo.",
        "id": "456",
        "speaker": "Jane Doe",
        "duration": "10",
    },
    {
        "url": "https://www.example.com/2",
        "title": "Le Monde",
        "description": "Dernières nouvelles...",
        "lang": "fr",
        "content": "Dernières nouvelles, actualités, sport, business, tech, culture...",
        "id": "789",
        "speaker": "John Doe",
        "duration": "15",
    },
]


header = [
    "url",
    "title",
    "description",
    "lang",
    "content",
    "speaker",
    "duration",
    "id",
]


class TestCSVTedPlugin(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CSVTEDCOLLECTOR_FILE_NAME"] = "test.csv"
        os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"] = "./resources/"

        self.rows = rows
        self.header = header

        mock_file_path = Path("./resources/CSVTedCollector/test.csv")
        mock_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.mock_file_path = mock_file_path

        with mock_file_path.open(mode="w") as file:
            writer = csv.DictWriter(file, fieldnames=self.header, delimiter=";")
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row)

        self.csv_ted_collector = CSVTedCollector()

    def tearDown(self) -> None:
        for f in self.csv_ted_collector._files_locations:
            if f.exists():
                os.remove(f.as_posix())
                f.parent.rmdir()
        del os.environ["CSVTEDCOLLECTOR_FILE_NAME"]
        del os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"]

    def test_plugin_type(self):
        self.assertEqual(CSVTedCollector.collector_type_name, PluginType.FILES)

    def test_plugin_related_corpus(self):
        self.assertEqual(CSVTedCollector.related_corpus, "csv_ted")

    def test_plugin_files_locations(self):
        self.assertEqual(
            self.csv_ted_collector._files_locations,
            [
                Path("./resources/CSVTedCollector/test.csv"),
            ],
        )

    def _compare_res_docs_to_expected(self, res):
        for i, _res in enumerate(res):
            expected_row = self.rows[i]
            self.assertEqual(_res.document_corpus, "ted")
            self.assertEqual(_res.document_url, expected_row["url"])
            self.assertEqual(_res.document_title, expected_row["title"])
            self.assertEqual(_res.document_desc, expected_row["description"])
            self.assertEqual(_res.document_lang, expected_row["lang"])
            self.assertEqual(_res.document_content, expected_row["content"])
            self.assertEqual(
                _res.document_details["duration"], expected_row["duration"]
            )
            self.assertEqual(
                _res.document_details["authors"],
                [{"name": expected_row["speaker"], "misc": ""}],
            )

    def test_plugin_run(self):
        urls = ["https://www.example.com/0", "https://www.example.com/1"]
        res, errors = self.csv_ted_collector.run(urls=urls)

        self.assertEqual(len(res), 2)
        self.assertTrue(isinstance(res[0], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(res[1], ScrapedWeLearnDocument))

        self._compare_res_docs_to_expected(res)

        # Check that the plugin the last url is not in the result
        self.assertNotIn("https://www.example.com/2", [r.document_url for r in res])

    def test_plugin_run_no_urls(self):
        res, errors = self.csv_ted_collector.run(urls=[])
        self.assertEqual(len(res), 0)

    def test_filter_csv_line(self):
        with self.mock_file_path.open(mode="r") as file:
            reader = csv.DictReader(file, delimiter=";")
            filtered = self.csv_ted_collector._filter_file_line(
                reader, ["https://www.example.com/0"]
            )

            nb_iter = 0
            for line in filtered:
                self.assertEqual(line["url"], rows[nb_iter]["url"])
                self.assertEqual(line["title"], rows[nb_iter]["title"])
                self.assertEqual(line["lang"], rows[nb_iter]["lang"])
                self.assertEqual(line["content"], rows[nb_iter]["content"])
                self.assertEqual(line["speaker"], rows[nb_iter]["speaker"])
                self.assertEqual(line["duration"], rows[nb_iter]["duration"])
                self.assertEqual(line["description"], rows[nb_iter]["description"])
                nb_iter += 1

            self.assertEqual(nb_iter, 1)

    def test_get_details_from_line(self):
        details = self.csv_ted_collector._get_details_from_line(self.rows[0])
        self.assertEqual(details["duration"], self.rows[0]["duration"])
        self.assertEqual(
            details["authors"], [{"name": self.rows[0]["speaker"], "misc": ""}]
        )

    def test_convert_csv_line_to_welearndoc(self):
        docs = [
            self.csv_ted_collector._convert_csv_line_to_welearndoc(row)
            for row in self.rows
        ]
        self.assertEqual(len(docs), 3)
        self.assertTrue(isinstance(docs[0], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(docs[1], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(docs[2], ScrapedWeLearnDocument))
        self._compare_res_docs_to_expected(docs)

    def test_convert_csv_line_to_welearndoc_no_details(self):
        current = copy(self.rows[0])
        del current["speaker"]
        del current["duration"]

        doc = self.csv_ted_collector._convert_csv_line_to_welearndoc(current)
        self.assertEqual(doc.document_url, "https://www.example.com/0")
        self.assertEqual(doc.document_details["authors"], [{"name": "", "misc": ""}])
        self.assertEqual(doc.document_details["duration"], "")
