import csv
import os
import shutil
import unittest
from copy import copy
from pathlib import Path
from unittest import TestCase

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.files_readers.wikipedia import CSVWikipediaCollector
from welearn_datastack.plugins.interface import IPluginFilesCollector

rows = [
    {
        "url": "https://www.example.com/0",
        "title": "The Irish Times",
        "lang": "en",
        "content": "The latest Irish and international news and sport from The Irish Times.",
        "summary": "The latest Irish and international news...",
        "id": "123",
        "qid": "Q404000",
        "readability": "60.21",
        "duration": "5",
    },
    {
        "url": "https://www.example.com/1",
        "title": "El Mundo",
        "lang": "es",
        "content": "Noticias de última hora, últimas noticias de actualidad, deportes, cultura, sociedad, curiosidades y economía en nuestros Informativos",
        "summary": "Noticias de última hora, últimas noticias de actualidad...",
        "id": "456",
        "qid": "Q404001",
        "readability": "30.21",
        "duration": "10",
    },
    {
        "url": "https://www.example.com/2",
        "title": "Le Monde",
        "lang": "fr",
        "content": "Dernières nouvelles, actualités internationales, sport, culture et divertissement sur Le Monde.",
        "summary": "Dernières nouvelles, actualités internationales...",
        "id": "789",
        "qid": "Q404002",
        "readability": "40.21",
        "duration": "15",
    },
]

header = [
    "title",
    "content",
    "summary",
    "qid",
    "url",
    "lang",
    "readability",
    "duration",
    "id",
]


class TestCSVWikipediaPlugin(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CSVWIKIPEDIACOLLECTOR_FILE_NAME"] = "test.csv"
        os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"] = "./resources/"

        self.rows = rows
        self.header = header

        mock_file_path = Path("./resources/CSVWikipediaCollector/test.csv")
        mock_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.mock_file_path = mock_file_path

        with mock_file_path.open(mode="w") as file:
            writer = csv.DictWriter(file, fieldnames=self.header, delimiter=";")
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row)

        self.csv_wikipedia_collector = CSVWikipediaCollector()

    def tearDown(self) -> None:
        for f in self.csv_wikipedia_collector._files_locations:
            if f.exists():
                os.remove(f.as_posix())
                f.parent.rmdir()
        del os.environ["CSVWIKIPEDIACOLLECTOR_FILE_NAME"]
        del os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"]

    def test_plugin_type(self):
        self.assertEqual(CSVWikipediaCollector.collector_type_name, PluginType.FILES)

    def test_plugin_related_corpus(self):
        self.assertEqual(CSVWikipediaCollector.related_corpus, "csv_wikipedia")

    def test_plugin_files_locations(self):
        self.assertEqual(
            self.csv_wikipedia_collector._files_locations,
            [
                Path("./resources/CSVWikipediaCollector/test.csv"),
            ],
        )

    def _compare_res_docs_to_expected(self, res):
        for i, _res in enumerate(res):
            expected_row = self.rows[i]
            self.assertEqual(_res.document_corpus, "wikipedia")
            self.assertEqual(_res.document_url, expected_row["url"])
            self.assertEqual(_res.document_title, expected_row["title"])
            self.assertEqual(_res.document_desc, expected_row["summary"])
            self.assertEqual(_res.document_lang, expected_row["lang"])
            self.assertEqual(_res.document_content, expected_row["content"])
            self.assertEqual(
                _res.document_details["readability"], expected_row["readability"]
            )
            self.assertEqual(
                _res.document_details["duration"], expected_row["duration"]
            )
            self.assertEqual(_res.document_details["qid"], expected_row["qid"])

    def test_plugin_run(self):
        urls = ["https://www.example.com/0", "https://www.example.com/1"]
        res, errors = self.csv_wikipedia_collector.run(urls_or_external_ids=urls)

        self.assertEqual(len(res), 2)
        self.assertTrue(isinstance(res[0], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(res[1], ScrapedWeLearnDocument))

        self._compare_res_docs_to_expected(res)

        # Check that the plugin the last url is not in the result
        self.assertNotIn("https://www.example.com/2", [r.document_url for r in res])

    def test_plugin_run_no_urls(self):
        res, errors = self.csv_wikipedia_collector.run(urls_or_external_ids=[])
        self.assertEqual(len(res), 0)

    def test_filter_csv_line(self):
        with self.mock_file_path.open(mode="r") as file:
            reader = csv.DictReader(file, delimiter=";")
            filtered = self.csv_wikipedia_collector._filter_file_line(
                reader, ["https://www.example.com/0"]
            )

            nb_iter = 0
            for line in filtered:
                nb_iter += 1
                self.assertEqual(line["url"], "https://www.example.com/0")
                self.assertEqual(line["title"], "The Irish Times")
                self.assertEqual(line["lang"], "en")
                self.assertEqual(
                    line["content"],
                    "The latest Irish and international news and sport from The Irish Times.",
                )
                self.assertEqual(line["id"], "123")
                self.assertEqual(line["qid"], "Q404000")
                self.assertEqual(line["readability"], "60.21")
                self.assertEqual(line["duration"], "5")

            self.assertEqual(nb_iter, 1)

    def test_get_details_from_line(self):
        details = self.csv_wikipedia_collector._get_details_from_line(self.rows[0])
        self.assertEqual(details["duration"], "5")
        self.assertEqual(details["readability"], "60.21")
        self.assertEqual(details["qid"], "Q404000")

    def test_convert_csv_line_to_welearndoc(self):
        docs = [
            self.csv_wikipedia_collector._convert_csv_line_to_welearndoc(row)
            for row in self.rows
        ]
        self.assertEqual(len(docs), 3)
        self.assertTrue(isinstance(docs[0], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(docs[1], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(docs[2], ScrapedWeLearnDocument))
        self._compare_res_docs_to_expected(docs)

    def test_convert_csv_line_to_welearndoc_no_details(self):
        current = copy(self.rows[0])
        del current["qid"]
        del current["readability"]
        del current["duration"]

        doc = self.csv_wikipedia_collector._convert_csv_line_to_welearndoc(current)
        self.assertEqual(doc.document_url, "https://www.example.com/0")
        self.assertEqual(doc.document_details["qid"], "")
        self.assertEqual(doc.document_details["readability"], "")
        self.assertEqual(doc.document_details["duration"], "")
