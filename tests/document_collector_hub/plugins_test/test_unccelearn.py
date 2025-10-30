import datetime
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from bs4 import BeautifulSoup
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRetrieveDocument
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
        doc_in = WeLearnDocument(
            id=1,
            url=url,
            lang="en",
            full_content="",
            description="",
            title="",
            details={},
        )
        doc = collector._scrape_document(doc_in)
        # Utilisation du vrai modèle Pydantic/ORM pour valider le résultat
        self.assertIsInstance(doc, WeLearnDocument)
        self.assertIsInstance(doc, WeLearnDocument)
        self.assertEqual(doc.url, url)
        self.assertEqual(doc.title, "UN CC:Learn – Climate Course")
        self.assertEqual(doc.description, "A comprehensive overview")
        self.assertEqual(
            doc.full_content,
            "Lorem ipsum CLEAN CONTENT dolor sit amet consectetur",
        )
        details = doc.details
        self.assertEqual(details["image"], "https://cdn.example.org/og.png")
        self.assertEqual(details["keywords"], ["climate", "environment"])
        self.assertEqual(details["type"], "MOOC")
        self.assertEqual(details["theme"], "climate change")
        self.assertEqual(details["course-type"], "self-paced")
        self.assertTrue(details["certifying"])
        self.assertEqual(details["duration"], int(3.5 * 3600))
        self.assertEqual(details["produced_date"], 1234567890)
        session.get.assert_called_once()
        mock_get_meta.assert_called_once()
        mock_get_content_md.assert_called_once()

    @patch(
        "welearn_datastack.plugins.scrapers.unccelearn.UNCCeLearnCollector._scrape_document"
    )
    def test_run_mixed_success_and_error(self, mock_scrape):
        fail_url = "https://fail.example"
        ok_url = "https://ok.example"
        fail_doc = WeLearnDocument(
            id=3,
            url=fail_url,
            lang="en",
            full_content="",
            description="",
            title="",
            details={},
        )
        ok_doc_in = WeLearnDocument(
            id=4,
            url=ok_url,
            lang="en",
            full_content="",
            description="",
            title="",
            details={},
        )
        mock_scrape.side_effect = [Exception("boom"), ok_doc_in]
        collector = UNCCeLearnCollector()
        result = collector.run([fail_doc, ok_doc_in])

        # Support both (collected, errors) and collected only
        collected = [d for d in result if not d.is_error]
        errors = [d for d in result if d.is_error]
        self.assertEqual(len(collected), 1)
        self.assertIsInstance(collected[0], WrapperRetrieveDocument)
        self.assertEqual(collected[0].document.url, ok_url)
        self.assertEqual(len(errors), 1)
        self.assertIn(fail_url, errors[0].document.url)

    @patch(
        "welearn_datastack.plugins.scrapers.unccelearn.UNCCeLearnCollector._scrape_document"
    )
    def test_run_all_success(self, mock_scrape):
        # Use real Pydantic/ORM objects and check all values
        doc1_data = dict(
            id=1,
            url="https://a.example",
            title="A Title",
            lang="en",
            full_content="A Content, lorem ipsum dolor sit amet consectetur",
            description="A Desc",
            details={"theme": "climate change", "duration": 3600},
        )
        doc2_data = dict(
            id=2,
            url="https://b.example",
            title="B Title",
            lang="en",
            full_content="B Content, lorem ipsum dolor sit amet consectetur",
            description="B Desc",
            details={"theme": "biodiversity", "duration": 7200},
        )
        doc1_in = WeLearnDocument(**doc1_data)
        doc2_in = WeLearnDocument(**doc2_data)
        mock_scrape.side_effect = [doc1_in, doc2_in]
        collector = UNCCeLearnCollector()

        collected = collector.run([doc1_in, doc2_in])

        self.assertEqual(len(collected), 2)
        self.assertTrue(all(isinstance(d, WrapperRetrieveDocument) for d in collected))
        # Check all values for each document
        self.assertEqual(collected[0].document.id, doc1_data["id"])
        self.assertEqual(collected[0].document.url, doc1_data["url"])
        self.assertEqual(collected[0].document.title, doc1_data["title"])
        self.assertEqual(collected[0].document.lang, doc1_data["lang"])
        self.assertEqual(
            getattr(collected[0].document, "full_content", None),
            doc1_data["full_content"],
        )
        self.assertEqual(
            getattr(collected[0].document, "description", None),
            doc1_data["description"],
        )
        self.assertEqual(collected[0].document.details, doc1_data["details"])
        self.assertEqual(collected[1].document.id, doc2_data["id"])
        self.assertEqual(collected[1].document.url, doc2_data["url"])
        self.assertEqual(collected[1].document.title, doc2_data["title"])
        self.assertEqual(collected[1].document.lang, doc2_data["lang"])
        self.assertEqual(
            getattr(collected[1].document, "full_content", None),
            doc2_data["full_content"],
        )
        self.assertEqual(
            getattr(collected[1].document, "description", None),
            doc2_data["description"],
        )
