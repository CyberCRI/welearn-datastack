import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.source_models.unesdoc import UNESDOCItem
from welearn_datastack.exceptions import UnauthorizedLicense
from welearn_datastack.plugins.rest_requesters.unesdoc import UNESDOCCollector


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


class TestUNESDOCCollector(TestCase):

    def setUp(self):
        self.collector = UNESDOCCollector()
        path_root = (
            Path(__file__).parent.parent
            / "resources"
            / "file_plugin_input"
            / "root_unesdoc.json"
        )

        path_sources = (
            Path(__file__).parent.parent
            / "resources"
            / "file_plugin_input"
            / "sources_unesdoc.json"
        )
        self.root_json_content = json.load(path_root.open("r"))
        self.sources_json_content = json.load(path_sources.open("r"))

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

    @patch("welearn_datastack.plugins.rest_requesters.unesdoc.get_new_https_session")
    def test__get_metadata_json(self, mock_get_new_https_session):
        session = Mock()
        session.get.return_value = MockResponse(json_data=self.root_json_content)
        mock_get_new_https_session.return_value = session

        test_doc = WeLearnDocument(
            url="https://www.example.com/doc001", external_id="doc001"
        )

        ret_doc = self.collector._get_metadata_json(test_doc)

        self.assertEqual(
            ret_doc.title,
            "Mapeo de los sistemas de créditos académicos en América Latina y el Caribe: hacia la armonización regional y la transformación de la educación superior",
        )
        self.assertEqual(
            ret_doc.url, "https://unesdoc.unesco.org/ark:/48223/pf0000397002"
        )

        session.method_calls[0].kwargs["params"] = {
            "params": {
                "limit": 1,
                "select": "url, year, language, title, type,description, subject,creator,rights",
                "where": 'search(url, "doc001")',
            }
        }

    def test__convert_ark_id_to_iid(self):
        res_iid = self.collector._convert_ark_id_to_iid("48223/pf0000389119")
        self.assertEqual(res_iid, "p::usmarcdef_0000389119")

    def test__convert_ark_id_to_iid_w_lang(self):
        res_iid = self.collector._convert_ark_id_to_iid("48223/pf0000389119/fre")
        self.assertEqual(res_iid, "p::usmarcdef_0000389119_fre")

    @patch("welearn_datastack.plugins.rest_requesters.unesdoc.get_new_https_session")
    def test__get_pdf_document_name(self, mock_get_new_https_session):
        session = Mock()
        session.get.return_value = MockResponse(json_data=self.sources_json_content)
        mock_get_new_https_session.return_value = session

        ret = self.collector._get_pdf_document_name(iid="48223/pf0000389119")
        self.assertListEqual(
            ret, ["attach_import_155a21be-2a3e-4424-8e8c-2412f8e5d26c"]
        )

    def test_run(self):
        assert False
