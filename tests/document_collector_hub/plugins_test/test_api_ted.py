import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.rest_requesters.ted import TEDCollector


class TestAPITedPlugin(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        req_json_content_path1 = (
            Path(__file__).parent.parent / "resources/file_plugin_input/ted_page.json"
        )

        with req_json_content_path1.open(mode="r") as file1:
            self.json_content_1 = json.load(file1)

        self.jsons_list = [
            self.json_content_1,
        ]

        self.ted_scraper = TEDCollector()

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        self.assertEqual(PluginType.REST, TEDCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(TEDCollector.related_corpus, "ted")

    @patch("requests.sessions.Session.post")
    def test_plugin_run(self, mock_get):
        class MockResponse:
            def __init__(self, text, status_code):
                self.text = text
                self.status_code = status_code

            def raise_for_status(self):
                pass

            def json(self):
                return self.text

        mock_get.side_effect = [MockResponse(text, 200) for text in self.jsons_list]

        scraped_docs, error_docs = self.ted_scraper.run(
            urls_or_external_ids=["https://example.org/4"]
        )

        self.assertEqual(len(scraped_docs), 1)
        self.assertEqual(len(error_docs), 0)

        self.assertEqual(
            scraped_docs[0].document_url,
            self.json_content_1["data"]["video"]["canonicalUrl"],
        )
        self.assertEqual(
            scraped_docs[0].document_title,
            self.json_content_1["data"]["video"]["title"],
        )
        self.assertEqual(
            scraped_docs[0].document_desc,
            self.json_content_1["data"]["video"]["description"],
        )
        self.assertEqual(
            scraped_docs[0].document_lang,
            self.json_content_1["data"]["video"]["internalLanguageCode"],
        )
        self.assertEqual(
            scraped_docs[0].document_details["duration"],
            str(self.json_content_1["data"]["video"]["duration"]),
        )

        self.assertEqual(
            scraped_docs[0].document_details["authors"][0]["name"],
            self.json_content_1["data"]["video"]["presenterDisplayName"],
        )

        ted_date_format = "%Y-%m-%dT%H:%M:%SZ"
        pubdate = datetime.strptime(
            self.json_content_1["data"]["video"]["publishedAt"], ted_date_format
        )
        pubdate.replace(tzinfo=timezone.utc)
        pubdate_ts = pubdate.timestamp()

        self.assertEqual(
            scraped_docs[0].document_details["publication_date"], pubdate_ts
        )
        self.assertEqual(
            scraped_docs[0].document_details["type"],
            self.json_content_1["data"]["video"]["type"]["name"],
        )

    def test_concat_content_from_json(self):
        tested_paragraphs = [
            {
                "cues": [
                    {
                        "text": "lorep ipsum dolor sit amet",
                    },
                    {
                        "text": "(Applause)",
                    },
                    {
                        "text": "consectetur adipiscing elit",
                    },
                ]
            },
            {
                "cues": [
                    {
                        "text": "sed do eiusmod tempor incididunt",
                    },
                    {
                        "text": "ut labore et dolore magna aliqua",
                    },
                ]
            },
        ]

        expected_content = (
            "lorep ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt "
            "ut labore et dolore magna aliqua"
        )

        self.assertEqual(
            expected_content,
            self.ted_scraper._concat_content_from_json(tested_paragraphs),
        )

    def test_plugin_run_error(self):
        pass
