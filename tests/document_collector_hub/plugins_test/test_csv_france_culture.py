import csv
import os
import shutil
import unittest
from copy import copy
from pathlib import Path
from unittest import TestCase

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.files_readers.france_culture import (
    CSVFranceCultureCollector,
)
from welearn_datastack.plugins.interface import IPluginFilesCollector

rows = [
    {
        "title": "Python Basics",
        "description": "A beginner's guide to Python programming",
        "url": "https://www.example.com/0",
        "content": "Learn the fundamentals of Python programming language.",
        "duration": "60",
        "date": "Dimanche 21 novembre 2021",
        "id": "1",
    },
    {
        "title": "Web Development Crash Course",
        "description": "A comprehensive course on web development",
        "url": "https://www.example.com/1",
        "content": "Master the skills required for building modern web applications.",
        "duration": "120",
        "date": "Lundi 22 novembre 2021",
        "id": "2",
    },
    {
        "title": "Data Science for Beginners",
        "description": "An introduction to data science concepts",
        "url": "https://www.example.com/2",
        "content": "Explore the world of data science and its applications.",
        "duration": "90",
        "date": "Mardi 23 novembre 2021",
        "id": "3",
    },
]

header = [
    "title",
    "description",
    "url",
    "content",
    "duration",
    "date",
    "id",
]


class TestCSVFranceCulturePlugin(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CSVFRANCECULTURECOLLECTOR_FILE_NAME"] = "test.csv"
        os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"] = "./resources/"

        self.rows = rows
        self.header = header

        mock_file_path = Path("./resources/CSVFranceCultureCollector/test.csv")
        mock_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.mock_file_path = mock_file_path

        with mock_file_path.open(mode="w") as file:
            writer = csv.DictWriter(file, fieldnames=self.header, delimiter=";")
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row)

        self.csv_france_culture_collector = CSVFranceCultureCollector()

    def tearDown(self) -> None:
        for f in self.csv_france_culture_collector._files_locations:
            if f.exists():
                os.remove(f.as_posix())
                f.parent.rmdir()
        del os.environ["CSVFRANCECULTURECOLLECTOR_FILE_NAME"]
        del os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"]

    def test_plugin_type(self):
        self.assertEqual(
            CSVFranceCultureCollector.collector_type_name, PluginType.FILES
        )

    def test_plugin_related_corpus(self):
        self.assertEqual(CSVFranceCultureCollector.related_corpus, "csv_france_culture")

    def test_plugin_files_locations(self):
        self.assertEqual(
            self.csv_france_culture_collector._files_locations,
            [
                Path("./resources/CSVFranceCultureCollector/test.csv"),
            ],
        )

    def _compare_res_docs_to_expected(self, res):
        for i, _res in enumerate(res):
            formated_date = self.csv_france_culture_collector._prepare_date(
                self.rows[i]["date"]
            )

            expected_row = self.rows[i]
            self.assertEqual(_res.document_corpus, "france_culture")
            self.assertEqual(_res.document_url, expected_row["url"])
            self.assertEqual(_res.document_title, expected_row["title"])
            self.assertEqual(_res.document_desc, expected_row["description"])
            self.assertEqual(_res.document_lang, "fr")
            self.assertEqual(_res.document_content, expected_row["content"])
            self.assertEqual(_res.document_details["date"], formated_date)
            self.assertEqual(
                _res.document_details["duration"], expected_row["duration"]
            )

    def test_plugin_run(self):
        urls = ["https://www.example.com/0", "https://www.example.com/1"]
        res, errors = self.csv_france_culture_collector.run(urls=urls)

        self.assertEqual(len(res), 2)
        self.assertTrue(isinstance(res[0], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(res[1], ScrapedWeLearnDocument))

        self._compare_res_docs_to_expected(res)

        # Check that the plugin the last url is not in the result
        self.assertNotIn("https://www.example.com/2", [r.document_url for r in res])

    def test_plugin_run_no_urls(self):
        res, errors = self.csv_france_culture_collector.run(urls=[])
        self.assertEqual(len(res), 0)

    def test_filter_csv_line(self):
        with self.mock_file_path.open(mode="r") as file:
            reader = csv.DictReader(file, delimiter=";")
            filtered = self.csv_france_culture_collector._filter_file_line(
                reader, ["https://www.example.com/0"]
            )

            nb_iter = 0
            for line in filtered:
                self.assertEqual(line["url"], rows[nb_iter]["url"])
                self.assertEqual(line["title"], rows[nb_iter]["title"])
                self.assertEqual(line["content"], rows[nb_iter]["content"])
                self.assertEqual(line["id"], rows[nb_iter]["id"])
                self.assertEqual(line["date"], rows[nb_iter]["date"])
                self.assertEqual(line["duration"], rows[nb_iter]["duration"])
                nb_iter += 1

            self.assertEqual(nb_iter, 1)

    def test_get_details_from_line(self):
        details = self.csv_france_culture_collector._get_details_from_line(self.rows[0])
        self.assertEqual(details["duration"], rows[0]["duration"])
        self.assertEqual(
            details["date"],
            self.csv_france_culture_collector._prepare_date(rows[0]["date"]),
        )

    def test_convert_csv_line_to_welearndoc(self):
        docs = [
            self.csv_france_culture_collector._convert_csv_line_to_welearndoc(row)
            for row in self.rows
        ]
        self.assertEqual(len(docs), 3)
        self.assertTrue(isinstance(docs[0], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(docs[1], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(docs[2], ScrapedWeLearnDocument))
        self._compare_res_docs_to_expected(docs)

    def test_convert_csv_line_to_welearndoc_no_details(self):
        current = copy(self.rows[0])
        del current["date"]
        del current["duration"]

        doc = self.csv_france_culture_collector._convert_csv_line_to_welearndoc(current)
        self.assertEqual(doc.document_url, "https://www.example.com/0")
        self.assertEqual(doc.document_details["date"], "")
        self.assertEqual(doc.document_details["duration"], "")
