import unittest
from unittest.mock import patch

import requests
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.exceptions import NoContent
from welearn_datastack.plugins.scrapers import NotreEnvironnementCollector


class TestNotreEnvironnementCollector(unittest.TestCase):
    def setUp(self):
        self.collector = NotreEnvironnementCollector()

    @patch(
        "welearn_datastack.plugins.scrapers.NotreEnvironnementCollector._get_dublin_core_metadata"
    )
    def test__compute_metadata(self, mock_get_dublin_core_metadata):
        wldoc = WeLearnDocument(
            url="https://www.notre-environnement.gouv.fr/actualites/breves/article/dans-les-pyrenees-le-nombre-d-ours-bruns-continue-de-progresser"
        )
        html_document = """<html>lorem ipsum</html>"""
        mock_get_dublin_core_metadata.return_value = {
            "description": "lorem ipsum",
            "dc.title": "Title ipsum",
            "dc.date": "2026-01-01",
            "dc.data.modified": "2026-01-15",
        }
        self.collector._compute_metadata(wldoc, html_document)
        mock_get_dublin_core_metadata.assert_called_once()

        self.assertEqual(wldoc.title, "Title ipsum")
        self.assertEqual(wldoc.description, "lorem ipsum")

    @patch.object(NotreEnvironnementCollector, "_compute_metadata")
    @patch.object(NotreEnvironnementCollector, "_get_full_content")
    @patch.object(NotreEnvironnementCollector, "_get_document")
    def test_run_success(
        self,
        mock_get_document,
        mock_get_full_content,
        mock_compute_metadata,
    ):
        html_document = "<html>ok</html>"
        wldoc = WeLearnDocument(url="https://example.org/doc")
        mock_get_document.return_value = html_document
        mock_get_full_content.return_value = "full content lorem ipsum ipsum"

        ret = self.collector.run([wldoc])

        self.assertEqual(len(ret), 1)
        self.assertFalse(ret[0].is_error)
        self.assertIs(ret[0].document, wldoc)
        self.assertEqual(wldoc.full_content, "full content lorem ipsum ipsum")
        mock_get_document.assert_called_once_with(wldoc.url)
        mock_get_full_content.assert_called_once_with(html_document)
        mock_compute_metadata.assert_called_once_with(
            html_document=html_document, document=wldoc
        )

    @patch.object(NotreEnvironnementCollector, "_compute_metadata")
    @patch.object(NotreEnvironnementCollector, "_get_full_content")
    @patch.object(NotreEnvironnementCollector, "_get_document")
    def test_run_no_content(
        self,
        mock_get_document,
        mock_get_full_content,
        mock_compute_metadata,
    ):
        wldoc = WeLearnDocument(url="https://example.org/no-content")
        mock_get_document.return_value = "<html>empty</html>"
        mock_get_full_content.side_effect = NoContent(
            "No content found in this document"
        )

        ret = self.collector.run([wldoc])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertEqual(ret[0].http_error_code, 204)
        self.assertIn("no content", ret[0].error_info.lower())
        mock_compute_metadata.assert_not_called()

    @patch(
        "welearn_datastack.plugins.scrapers.notre_environnement.get_http_code_from_exception"
    )
    @patch.object(NotreEnvironnementCollector, "_compute_metadata")
    @patch.object(NotreEnvironnementCollector, "_get_full_content")
    @patch.object(NotreEnvironnementCollector, "_get_document")
    def test_run_http_error(
        self,
        mock_get_document,
        mock_get_full_content,
        mock_compute_metadata,
        mock_get_http_code_from_exception,
    ):
        wldoc = WeLearnDocument(url="https://example.org/http-error")
        mock_get_document.side_effect = requests.HTTPError("bad gateway")
        mock_get_http_code_from_exception.return_value = 502

        ret = self.collector.run([wldoc])

        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].is_error)
        self.assertEqual(ret[0].http_error_code, 502)
        self.assertIn("HTTP error 502", ret[0].error_info)
        mock_get_http_code_from_exception.assert_called_once()
        mock_get_full_content.assert_not_called()
        mock_compute_metadata.assert_not_called()
