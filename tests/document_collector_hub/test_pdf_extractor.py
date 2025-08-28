import io
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pypdf import PdfReader

from welearn_datastack.data.enumerations import DeletePart
from welearn_datastack.modules import pdf_extractor
from welearn_datastack.modules.pdf_extractor import (
    _parse_tika_content,
    _send_pdf_to_tika,
    extract_txt_from_pdf_with_tika,
)


class TestPDFExtractor(unittest.TestCase):
    def setUp(self):
        resources_fp = (
            Path(__file__).parent / "resources" / "file_plugin_input" / "hal_pdf.pdf"
        )

        self.reader = PdfReader(resources_fp)

    def test_extract_txt_from_pdf(self):
        pdf_content = pdf_extractor.extract_txt_from_pdf(self.reader)
        self.assertEqual(len(pdf_content), len(self.reader.pages))

    def test_replace_ligatures(self):
        text = "ﬁrst ﬂight"
        cleaned_text = pdf_extractor.replace_ligatures(text)
        self.assertEqual(cleaned_text, "first flight")

    def test_delete_accents(self):
        text = "re ´sume´"
        cleaned_text = pdf_extractor.delete_accents(text)
        self.assertEqual(cleaned_text, "resume")

    def test_remove_hyphens(self):
        text = "well-\nknown"
        cleaned_text = pdf_extractor.remove_hyphens(text)
        self.assertEqual(cleaned_text, "wellknown\n")

    def test_check_page_size_positive(self):
        ret = pdf_extractor.large_pages_size_flag(self.reader, 10000)
        self.assertEqual(len(ret[0]), len(self.reader.pages))
        self.assertTrue(ret[1])

    def test_check_page_size_negative(self):
        ret = pdf_extractor.large_pages_size_flag(self.reader, 100000)
        self.assertEqual(len(ret[0]), len(self.reader.pages))
        self.assertFalse(ret[1])

    @patch("welearn_datastack.modules.pdf_extractor.get_new_https_session")
    def test_send_pdf_to_tika(self, mock_get_session):
        # Mock de la session HTTP
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "X-TIKA:content": "<html>Mock Content</html>"
        }
        mock_response.raise_for_status.return_value = None
        mock_session.put.return_value = mock_response
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Appel de la méthode
        pdf_content = io.BytesIO(b"Mock PDF content")
        tika_base_url = "http://mock-tika-url"
        result = _send_pdf_to_tika(pdf_content, tika_base_url)

        # Assertions
        mock_session.put.assert_called_once_with(
            url=f"{tika_base_url}/tika",
            files={"file": pdf_content},
            headers={
                "Accept": "application/json",
                "Content-type": "application/octet-stream",
                "X-Tika-PDFOcrStrategy": "no_ocr",
            },
        )
        self.assertEqual(result, {"X-TIKA:content": "<html>Mock Content</html>"})

    def test_parse_tika_content(self):
        # Contenu simulé de Tika
        tika_content = {
            "X-TIKA:content": """
            <html>
                <div class="page">Page 1 content</div>
                <div class="page">Page 2 content</div>
            </html>
            """
        }

        # Appel de la méthode
        result = _parse_tika_content(tika_content)

        # Assertions
        expected_result = [["Page 1 content"], ["Page 2 content"]]
        self.assertEqual(result, expected_result)

    @patch("welearn_datastack.modules.pdf_extractor._send_pdf_to_tika")
    @patch("welearn_datastack.modules.pdf_extractor._parse_tika_content")
    def test_extract_txt_from_pdf_with_tika(
        self, mock_parse_tika_content, mock_send_pdf_to_tika
    ):
        # Simuler le contenu PDF
        pdf_content = io.BytesIO(b"%PDF-1.4 simulated content")
        tika_base_url = "http://localhost:9998"

        # Simuler la réponse de Tika
        mock_send_pdf_to_tika.return_value = {
            "X-TIKA:content": "<div class='page'>Page 1 content</div>"
        }
        mock_parse_tika_content.return_value = [["Page 1 content"]]

        # Appeler la méthode
        result = extract_txt_from_pdf_with_tika(pdf_content, tika_base_url)

        # Vérifier les résultats
        self.assertEqual(result, [["Page 1 content"]])
        mock_send_pdf_to_tika.assert_called_once_with(pdf_content, tika_base_url)
        mock_parse_tika_content.assert_called_once_with(
            mock_send_pdf_to_tika.return_value
        )
