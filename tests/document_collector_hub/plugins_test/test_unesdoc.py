from unittest import TestCase

from welearn_datastack.data.source_models.unesdoc import UNESDOCItem
from welearn_datastack.exceptions import UnauthorizedLicense
from welearn_datastack.plugins.rest_requesters.unesdoc import UNESDOCCollector


class TestUNESDOCCollector(TestCase):

    def setUp(self):
        self.collector = UNESDOCCollector()

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
        subjects = [
            "Happiness",
            "Well-being",
            "Educational philosophy",
            "Student welfare",
            "Educational environment",
            "Educational policy",
            "Case studies",
            "Happy Schools Project",
        ]
        unesdoc_item = UNESDOCItem(
            rights="",
            url="example.com",
            year=["2020"],
            language=["eng"],
            title="Test",
            type=["type"],
            description="desc",
            subject=subjects,
            creator="creator",
        )
        res_subjects = self.collector._extract_topics(unesdoc_item)
        result_list = [s.name for s in res_subjects]
        awaited_list = [s.lower() for s in subjects]
        self.assertListEqual(result_list, awaited_list)

    def test__extract_authors(self):
        unesdoc_item = UNESDOCItem(
            rights="",
            url="example.com",
            year=["2020"],
            language=["eng"],
            title="Test",
            type=["type"],
            description="desc",
            subject=[],
            creator="UNESCO",
        )
        res_authors = self.collector._extract_authors(unesdoc_item)
        self.assertListEqual([a.name for a in res_authors], ["UNESCO"])

    def test__check_licence_authorization_good(self):
        tested_licence = "https://creativecommons.org/licenses/by-sa/3.0/igo/"
        self.collector._check_licence_authorization(tested_licence)
        self.assertTrue(True)

    def test__check_licence_authorization_bad(self):
        tested_licence = (
            "https://creativecommons.org/licenses/highly_bored_copyrights//"
        )
        with self.assertRaises(UnauthorizedLicense):
            self.collector._check_licence_authorization(tested_licence)

    def test__extract_metadata(self):
        metadata = UNESDOCItem(
            rights='<a href="https://creativecommons.org/licenses/by-sa/3.0/igo/" target="_blank" title="This license allows readers to share, copy, distribute, adapt and make commercial use of the work as long as it is attributed back to the author and distributed under this or a similar license.">CC BY-SA 3.0 IGO</a>',
            subject=["Happiness"],
            year=["2020"],
            language=["eng"],
            title="Test",
            type=["type"],
            description="desc",
            creator="UNESCO",
            url="example.com",
        )
        result_metadata = self.collector._extract_metadata(metadata)
        self.assertEqual(result_metadata["type"], "type")
        self.assertEqual(result_metadata["topics"][0].name, "happiness")
        self.assertEqual(result_metadata["topics"][0].depth, 0)
        self.assertEqual(
            result_metadata["licence_url"],
            "https://creativecommons.org/licenses/by-sa/3.0/igo/",
        )
        self.assertEqual(result_metadata["authors"][0].name, "UNESCO")

    def test__get_metadata_json(self):
        assert False

    def test__convert_ark_id_to_iid(self):
        assert False

    def test__get_pdf_document_name(self):
        assert False

    def test_run(self):
        assert False
