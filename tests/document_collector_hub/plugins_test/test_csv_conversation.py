import csv
import os
import shutil
import unittest
from copy import copy
from pathlib import Path
from unittest import TestCase

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.data.scraped_welearn_document import ScrapedWeLearnDocument
from welearn_datastack.plugins.files_readers.conversation import (
    CSVConversationCollector,
)
from welearn_datastack.plugins.interface import IPluginFilesCollector

rows = [
    {
        "url": "https://www.example.com/0",
        "title": "The Irish Times",
        "description": "Irish news, sport & opinion",
        "lang": "en",
        "content": "The latest Irish and international news...",
        "author": "John Smith",
        "source": "Dublin, Ireland",
        "id": 123,
        "readability": "easy",
        "duration": 5,
    },
    {
        "url": "https://www.example.com/1",
        "title": "El Mundo",
        "description": "Noticias de España y el mundo",
        "lang": "es",
        "content": "Noticias de última hora...",
        "author": "Juan Pérez",
        "source": "Madrid, Spain",
        "id": 456,
        "readability": "difficult",
        "duration": 10,
    },
    {
        "url": "https://www.example.com/2",
        "title": "The New York Times",
        "description": "Breaking News, World News & Multimedia",
        "lang": "en",
        "content": "The New York Times: Find breaking news...",
        "author": "Jane Doe",
        "source": "New York City, United States",
        "id": 789,
        "readability": "moderate",
        "duration": 7,
    },
    {
        "url": "https://www.example.com/3",
        "title": "The New York Times",
        "description": "Breaking News, World News & Multimedia",
        "lang": "en",
        "content": None,
        "author": "Jane Doe",
        "source": "New York City, United States",
        "id": 789,
        "readability": "moderate",
        "duration": 7,
    },
]

header = [
    "url",
    "title",
    "description",
    "lang",
    "content",
    "author",
    "source",
    "id",
    "readability",
    "duration",
]


class TestCSVConversationPlugin(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CSVCONVERSATIONCOLLECTOR_FILE_NAME"] = "test.csv"
        os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"] = "./resources/"

        self.rows = rows
        self.header = header

        mock_file_path = Path("./resources/CSVConversationCollector/test.csv")
        mock_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.mock_file_path = mock_file_path

        with mock_file_path.open(mode="w") as file:
            writer = csv.DictWriter(file, fieldnames=self.header, delimiter=";")
            writer.writeheader()
            for row in self.rows:
                writer.writerow(row)  # type: ignore

        self.csv_conversation_collector = CSVConversationCollector()

    def tearDown(self) -> None:
        for f in self.csv_conversation_collector._files_locations:
            if f.exists():
                os.remove(f.as_posix())
                f.parent.rmdir()
        del os.environ["CSVCONVERSATIONCOLLECTOR_FILE_NAME"]
        del os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"]

    def test_plugin_type(self):
        self.assertEqual(CSVConversationCollector.collector_type_name, PluginType.FILES)

    def test_plugin_related_corpus(self):
        self.assertEqual(CSVConversationCollector.related_corpus, "csv_conversation")

    def test_plugin_files_locations(self):
        self.assertEqual(
            self.csv_conversation_collector._files_locations,
            [
                Path("./resources/CSVConversationCollector/test.csv"),
            ],
        )

    def test_plugin_run(self):
        urls = ["https://www.example.com/0", "https://www.example.com/1"]
        res, errors = self.csv_conversation_collector.run(urls_or_external_ids=urls)

        self.assertEqual(len(res), 2)
        self.assertTrue(isinstance(res[0], ScrapedWeLearnDocument))
        self.assertTrue(isinstance(res[1], ScrapedWeLearnDocument))
        self.assertEqual(res[0].document_url, "https://www.example.com/0")
        self.assertEqual(res[1].document_url, "https://www.example.com/1")
        self.assertEqual(res[0].document_title, "The Irish Times")
        self.assertEqual(res[1].document_title, "El Mundo")
        self.assertEqual(res[0].document_desc, "Irish news, sport & opinion")
        self.assertEqual(res[1].document_desc, "Noticias de España y el mundo")
        self.assertEqual(res[0].document_lang, "en")
        self.assertEqual(res[1].document_lang, "es")
        self.assertEqual(
            res[0].document_content, "The latest Irish and international news..."
        )
        self.assertEqual(res[1].document_content, "Noticias de última hora...")

        # Check data in details
        details0 = res[0].document_details
        details1 = res[1].document_details
        self.assertEqual(details0["authors"], [{"name": "John Smith", "misc": ""}])
        self.assertEqual(details1["authors"], [{"misc": "", "name": "Juan Pérez"}])
        self.assertEqual(details0["source"], "Dublin, Ireland")
        self.assertEqual(details1["source"], "Madrid, Spain")

        self.assertEqual(details0["readability"], "easy")
        self.assertEqual(details1["readability"], "difficult")
        self.assertEqual(details0["duration"], "5")
        self.assertEqual(details1["duration"], "10")

        # Check that the plugin the last url is not in the result
        self.assertNotIn("https://www.example.com/2", [r.document_url for r in res])

    def test_plugin_run_no_urls(self):
        res, errors = self.csv_conversation_collector.run(urls_or_external_ids=[])
        self.assertEqual(len(res), 0)

    def test_plugin_run_error(self):
        urls = ["https://www.example.com/0", "https://www.example.com/3"]
        res, errors = self.csv_conversation_collector.run(urls_or_external_ids=urls)

        self.assertEqual(len(errors), 1)

    def test_filter_csv_line(self):
        with self.mock_file_path.open(mode="r") as file:
            reader = csv.DictReader(file, delimiter=";")
            filtered = self.csv_conversation_collector._filter_file_line(
                reader, ["https://www.example.com/0"]
            )

            nb_iter = 0
            for line in filtered:
                nb_iter += 1
                self.assertEqual(line["url"], "https://www.example.com/0")
                self.assertEqual(line["title"], "The Irish Times")
                self.assertEqual(line["description"], "Irish news, sport & opinion")
                self.assertEqual(line["lang"], "en")
                self.assertEqual(
                    line["content"], "The latest Irish and international news..."
                )
                self.assertEqual(line["author"], "John Smith")
                self.assertEqual(line["source"], "Dublin, Ireland")
                self.assertEqual(line["id"], "123")

            self.assertEqual(nb_iter, 1)

    def test_get_details_from_line(self):
        details = self.csv_conversation_collector._get_details_from_line(self.rows[0])
        self.assertEqual(details["authors"], [{"name": "John Smith", "misc": ""}])
        self.assertEqual(details["source"], "Dublin, Ireland")
        self.assertEqual(details["readability"], "easy")
        self.assertEqual(details["duration"], 5)

    def test_convert_csv_line_to_welearndoc(self):
        doc = self.csv_conversation_collector._convert_csv_line_to_welearndoc(
            self.rows[0]
        )
        self.assertEqual(doc.document_url, "https://www.example.com/0")
        self.assertEqual(doc.document_title, "The Irish Times")
        self.assertEqual(doc.document_desc, "Irish news, sport & opinion")
        self.assertEqual(doc.document_lang, "en")
        self.assertEqual(
            doc.document_content, "The latest Irish and international news..."
        )
        self.assertEqual(
            doc.document_details["authors"], [{"name": "John Smith", "misc": ""}]
        )
        self.assertEqual(doc.document_details["source"], "Dublin, Ireland")
        self.assertEqual(doc.document_details["readability"], "easy")
        self.assertEqual(doc.document_details["duration"], 5)
        self.assertEqual(doc.document_corpus, "conversation")

    def test_convert_csv_line_to_welearndoc_no_details(self):
        current = copy(self.rows[0])
        del current["author"]
        del current["source"]
        del current["readability"]
        del current["duration"]

        doc = self.csv_conversation_collector._convert_csv_line_to_welearndoc(current)
        self.assertEqual(doc.document_url, "https://www.example.com/0")
        self.assertEqual(doc.document_title, "The Irish Times")
        self.assertEqual(doc.document_desc, "Irish news, sport & opinion")
        self.assertEqual(doc.document_lang, "en")
        self.assertEqual(
            doc.document_content, "The latest Irish and international news..."
        )
        self.assertEqual(doc.document_details["authors"], [{"name": "", "misc": ""}])
        self.assertEqual(doc.document_details["source"], "")
        self.assertEqual(doc.document_details["readability"], "")
        self.assertEqual(doc.document_details["duration"], "")
        self.assertEqual(doc.document_corpus, "conversation")
