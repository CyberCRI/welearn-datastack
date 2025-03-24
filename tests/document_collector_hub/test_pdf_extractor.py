import unittest
from pathlib import Path

from pypdf import PdfReader

from welearn_datastack.data.enumerations import DeletePart
from welearn_datastack.modules import pdf_extractor


class TestPDFExtractor(unittest.TestCase):
    def setUp(self):
        resources_fp = (
            Path(__file__).parent / "resources" / "file_plugin_input" / "hal_pdf.pdf"
        )

        self.reader = PdfReader(resources_fp)

    def test_extract_txt_from_pdf(self):
        pdf_content, ref_content = pdf_extractor.extract_txt_from_pdf(self.reader)
        self.assertEqual(len(pdf_content), len(self.reader.pages))
        self.assertEqual(len(ref_content), len(self.reader.pages))

    def test_delete_pages_before_key(self):
        pdf_content = [["content"], ["content", "key", "lorem"], ["content"]]
        ref_content = [["content"], ["content", "key", "lorem"], ["content"]]
        pdf_extractor.delete_pages(pdf_content, DeletePart.before, "key", ref_content)
        self.assertEqual(pdf_content, [["lorem"], ["content"]])
        self.assertEqual(ref_content, [["lorem"], ["content"]])

    def test_delete_pages_before_key_with_key_deleted_by_previous_filter(self):
        pdf_content = [["content"], ["ipsum"], ["content", "lorem"], ["content end"]]
        ref_content = [
            ["content"],
            ["key"],
            ["content", "lorem"],
            ["content end"],
        ]
        pdf_extractor.delete_pages(pdf_content, DeletePart.before, "key", ref_content)
        self.assertListEqual([[], ["content", "lorem"], ["content end"]], pdf_content)
        self.assertListEqual([[], ["content", "lorem"], ["content end"]], ref_content)

    def test_delete_pages_after_key(self):
        pdf_content = [["content", "key"], ["content"], ["content"]]
        ref_content = [["content", "key"], ["content"], ["content"]]
        pdf_extractor.delete_pages(pdf_content, DeletePart.after, "key", ref_content)
        self.assertEqual(pdf_content, [["content"]])
        self.assertEqual(ref_content, [["content"]])

    def test_delete_redundant_content(self):
        pdf_content = [["line1", "line2"], ["line1", "line3"], ["line1", "line4"]]
        filtered_content = pdf_extractor.delete_redundant_content(pdf_content)
        self.assertEqual(filtered_content, [["line1", "line2"], ["line3"], ["line4"]])

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
