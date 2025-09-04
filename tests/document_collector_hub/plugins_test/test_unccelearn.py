import datetime
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from bs4 import BeautifulSoup

from welearn_datastack.plugins.scrapers.unccelearn import (
    UNCCeLearnCollector,
    format_news_keywords,
)


class MockResponse:
    def __init__(self, content=None, json_data=None, status_code=200):
        self.content = content
        self._json = json_data
        self.status_code = status_code

    def json(self):
        if self._json is None:
            raise ValueError("No JSON data")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class TestUNCCeLearnCollector(TestCase):
    def setUp(self):
        self.collector = UNCCeLearnCollector()
        self.mock_base_path = Path(__file__).parent.parent / "resources"

        self.sample_html = """
            <html>
              <head></head>
              <body>
                <div class="details">
                  <p class="theme">Climate Change</p>
                  <p class="time">3-4 hours</p>
                  <p class="certification">With certification</p>
                  <p class="type">Self-paced</p>
                </div>
                <a id="overview_syllabus_download" href="https://example.org/syllabus.pdf">Download syllabus</a>
              </body>
            </html>
        """.encode(
            "utf-8"
        )

        # Métadonnées renvoyées par Tika pour la page HTML (PUT /meta)
        self.tika_html_meta = {
            "dc:title": "UN CC:Learn – Climate Course",
            "dc:description": "A comprehensive overview of climate change.",
            "og:image": "https://cdn.example.org/og-image.png",
            "keywords": "climate, environment, SDG 13",
        }

        self.pdf_text_pages = [
            ["Hello", "world"],
            ["foo", "bar"],
        ]
        self.pdf_meta = {"pdf:docinfo:created": "2021-01-02T03:04:05Z"}

    def _expected_timestamp_from_str(self, iso_str: str) -> int:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        ts = time.mktime(datetime.datetime.strptime(iso_str, fmt).timetuple())
        return int(ts)

    def test_format_news_keywords(self):
        self.assertEqual(format_news_keywords(None), [])
        self.assertEqual(format_news_keywords("climate"), ["climate"])
        self.assertEqual(
            format_news_keywords("climate, environment, SDG 13"),
            ["climate", "environment", "SDG 13"],
        )

    def test__convert_duration_to_seconds(self):
        # 3 hours -> 10800
        self.assertEqual(
            self.collector._convert_duration_to_seconds("3 hours"), 3 * 3600
        )
        # 3,5 hours (comma) -> 12600
        self.assertEqual(
            self.collector._convert_duration_to_seconds("3,5 hours"), int(3.5 * 3600)
        )
        # 3.5 hours (point) -> 12600
        self.assertEqual(
            self.collector._convert_duration_to_seconds("3.5 hours"), int(3.5 * 3600)
        )
        self.assertEqual(
            self.collector._convert_duration_to_seconds("3-4 hours"), int(3.5 * 3600)
        )

    def test__get_details_from_html(self):
        with open(self.mock_base_path / "unccelearn_course.html", "rb") as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, features="html.parser")
        details = self.collector._get_details(soup)
        self.assertEqual(details["theme"], "climate change")
        self.assertEqual(details["duration"], int(4 * 3600))
        self.assertTrue(details["certifying"])
        self.assertEqual(details["course-type"], "self-paced courses")

    @patch("welearn_datastack.plugins.scrapers.unccelearn.UNCCeLearnCollector._get_pdf")
    @patch(
        "welearn_datastack.plugins.scrapers.unccelearn.extract_txt_from_pdf_with_tika"
    )
    def test_get_content_and_file_metadata(self, mock_extract_txt, mock_get_pdf):
        mock_get_pdf.return_value = b"%PDF-1.4 fake pdf content"

        mock_extract_txt.return_value = (self.pdf_text_pages, self.pdf_meta)

        soup = BeautifulSoup(self.sample_html, features="html.parser")
        content, file_metadata = self.collector._get_content_and_file_metadata(soup)

        expected_content = "Hello world foo bar"
        expected_timestamp = self._expected_timestamp_from_str(
            self.pdf_meta["pdf:docinfo:created"]
        )

        self.assertEqual(content, expected_content)
        self.assertEqual(file_metadata["produced_date"], expected_timestamp)

        mock_get_pdf.assert_called_once_with("https://example.org/syllabus.pdf")
        mock_extract_txt.assert_called_once_with(
            b"%PDF-1.4 fake pdf content",
            tika_base_url=self.collector.tika_address,
            with_metadata=True,
        )

    @patch(
        "welearn_datastack.plugins.scrapers.unccelearn.UNCCeLearnCollector._get_content_and_file_metadata"
    )
    @patch(
        "welearn_datastack.plugins.scrapers.unccelearn.UNCCeLearnCollector._get_metadata_from_tika"
    )
    @patch("welearn_datastack.plugins.scrapers.unccelearn.get_new_https_session")
    def test__scrape_url_happy_path(
        self, mock_get_session, mock_get_meta, mock_get_content_md
    ):
        collector = UNCCeLearnCollector()

        sample_html = b"""
            <html><body>
                <div class="details">
                  <p class="thematic-areas">Climate Change</p>
                  <p class="time">3-4 hours</p>
                  <p class="certification">With certification</p>
                  <p class="type">Self-paced</p>
                </div>
            </body></html>
        """

        session = Mock()
        session.get.return_value = MockResponse(content=sample_html)
        mock_get_session.return_value = session

        mock_get_meta.return_value = {
            "dc:title": "UN CC:Learn – Climate Course",
            "dc:description": "A comprehensive overview",
            "og:image": "https://cdn.example.org/og.png",
            "keywords": "climate, environment",
        }

        mock_get_content_md.return_value = (
            "Lorem ipsum CLEAN CONTENT dolor sit amet consectetur",
            {"produced_date": 1234567890},
        )

        url = "https://example.org/course"
        doc = collector._scrape_url(url)

        self.assertEqual(doc.document_url, url)
        self.assertEqual(doc.document_title, "UN CC:Learn – Climate Course")
        self.assertEqual(doc.document_desc, "A comprehensive overview")
        self.assertEqual(
            doc.document_content, "Lorem ipsum CLEAN CONTENT dolor sit amet consectetur"
        )

        details = doc.document_details
        self.assertEqual(details["image"], "https://cdn.example.org/og.png")
        self.assertEqual(details["keywords"], ["climate", "environment"])
        self.assertEqual(details["type"], "MOOC")
        self.assertEqual(details["theme"], "climate change")  # get_details
        self.assertEqual(details["course-type"], "self-paced")
        self.assertTrue(details["certifying"])
        self.assertEqual(details["duration"], int(3.5 * 3600))  # "3-4 hours" => 3.5h
        self.assertEqual(details["produced_date"], 1234567890)

        session.get.assert_called_once()
        mock_get_meta.assert_called_once()
        mock_get_content_md.assert_called_once()

    @patch(
        "welearn_datastack.plugins.scrapers.unccelearn.UNCCeLearnCollector._scrape_url"
    )
    def test_run_mixed_success_and_error(self, mock_scrape):
        # Arrange: first URL raises, second URL returns a doc
        ok_doc = Mock()
        fail_url = "https://fail.example"
        ok_url = "https://ok.example"
        mock_scrape.side_effect = [Exception("boom"), ok_doc]

        collector = UNCCeLearnCollector()

        # Act
        collected, errors = collector.run([fail_url, ok_url])

        # Assert: one collected doc, one error containing the failing URL
        self.assertEqual(len(collected), 1, "Should collect exactly one document")
        self.assertIs(
            collected[0],
            ok_doc,
            "Collected document should be the one returned by _scrape_url",
        )
        self.assertEqual(len(errors), 1, "Should register exactly one error")
        self.assertIn(fail_url, errors[0], "Error list should include the failing URL")

    @patch(
        "welearn_datastack.plugins.scrapers.unccelearn.UNCCeLearnCollector._scrape_url"
    )
    def test_run_all_success(self, mock_scrape):
        # Arrange: both URLs succeed
        doc1, doc2 = Mock(), Mock()
        urls = ["https://a.example", "https://b.example"]
        mock_scrape.side_effect = [doc1, doc2]

        collector = UNCCeLearnCollector()

        # Act
        collected, errors = collector.run(urls)

        # Assert: both docs collected, no errors
        self.assertEqual(
            collected, [doc1, doc2], "Should collect all returned documents in order"
        )
        self.assertEqual(errors, [], "Should not report any errors when all succeed")
