from unittest import TestCase

from welearn_datastack.data.source_models.unesdoc import UNESDOCItem
from welearn_datastack.plugins.rest_requesters.unesdoc import UNESDOCCollector


class TestUNESDOCCollector(TestCase):

    def setUp(self):
        self.collector = UNESDOCCollector()

    def test__get_pdf_content(self):
        assert False

    def test__clean_txt_content(self):
        assert False

    def test__extract_licence(self):
        right_to_test = '<a href="https://creativecommons.org/licenses/by-sa/3.0/igo/" target="_blank" title="This license allows readers to share, copy, distribute, adapt and make commercial use of the work as long as it is attributed back to the author and distributed under this or a similar license.">CC BY-SA 3.0 IGO</a>'
        unesdoc_item = UNESDOCItem(
            rights=right_to_test,
            url="example.com",
            year=["2020"],
            language=["eng"],
            title="Test",
            type=["type"],
            description="desc",
            subject=["subj"],
            creator="creator",
        )
        licence = self.collector._extract_licence(unesdoc_item)
        self.assertEqual(licence, "https://creativecommons.org/licenses/by-sa/3.0/igo/")

    def test__extract_topics(self):
        assert False

    def test__extract_authors(self):
        assert False

    def test__check_licence_authorization(self):
        assert False

    def test__extract_metadata(self):
        assert False

    def test__get_metadata_json(self):
        assert False

    def test__convert_ark_id_to_iid(self):
        assert False

    def test__get_pdf_document_name(self):
        assert False

    def test_run(self):
        assert False
