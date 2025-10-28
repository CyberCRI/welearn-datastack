import unittest
from unittest.mock import MagicMock, patch

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRawData
from welearn_datastack.data.source_models.oapen import Bitstream, Metadatum, OapenModel
from welearn_datastack.exceptions import (
    NoDescriptionFoundError,
    TooMuchLanguages,
    UnauthorizedLicense,
    WrongLangFormat,
)
from welearn_datastack.plugins.rest_requesters.oapen import OAPenCollector


class TestOAPenCollector(unittest.TestCase):
    def setUp(self):
        self.collector = OAPenCollector()
        self.doc = WeLearnDocument(url="https://library.oapen.org/handle/1234")

    @patch("welearn_datastack.plugins.rest_requesters.oapen.get_new_https_session")
    @patch(
        "welearn_datastack.plugins.rest_requesters.oapen.extract_txt_from_pdf_with_tika"
    )
    def test_get_pdf_content_success(self, mock_tika, mock_session):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"PDFDATA"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response
        mock_session.return_value = mock_client
        mock_tika.return_value = [["page1", "page2"]]
        result = self.collector._get_pdf_content("https://library.oapen.org/fake.pdf")
        self.assertEqual("page1 page2", result)

    def test_clean_backline_removes_newlines_and_hyphens(self):
        text = "Lin-\nguistique\nLinguistique"
        cleaned = self.collector.clean_backline(text)
        self.assertNotIn("\n", cleaned)
        self.assertNotIn("-\n", cleaned)

    @patch("welearn_datastack.plugins.rest_requesters.oapen.get_new_https_session")
    def test_get_txt_content_success(self, mock_session):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Texte brut\nLigne2"
        mock_response.encoding = "utf-8"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response
        mock_session.return_value = mock_client
        result = self.collector._get_txt_content("https://library.oapen.org/fake.txt")
        self.assertIn("Texte brut", result)
        self.assertIn("Ligne2", result)

    def test_format_metadata_merges_keys(self):
        meta = [
            Metadatum(
                key="a",
                value="1",
                language=None,
                schema="s",
                element="e",
                qualifier=None,
            ),
            Metadatum(
                key="a",
                value="2",
                language=None,
                schema="s",
                element="e",
                qualifier=None,
            ),
        ]
        result = self.collector._format_metadata(meta)
        self.assertEqual(result["a"], ["1", "2"])

    @patch("welearn_datastack.plugins.rest_requesters.oapen.get_new_https_session")
    @patch(
        "welearn_datastack.plugins.rest_requesters.oapen.OapenModel.model_validate_json"
    )
    def test_get_jsons_returns_wrappers(self, mock_validate, mock_session):
        doc = WeLearnDocument(url="https://library.oapen.org/handle/1234")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "handle": "1234",
                "name": "Titre",
                "bitstreams": [],
                "metadata": [],
                "uuid": "u",
                "type": "t",
                "expand": [],
                "lastModified": "",
                "parentCollection": None,
                "parentCollectionList": None,
                "parentCommunityList": None,
                "archived": "",
                "withdrawn": "",
                "link": "",
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response
        mock_session.return_value = mock_client
        fake_model = MagicMock()
        fake_model.handle = "1234"
        mock_validate.return_value = fake_model
        result = self.collector._get_jsons([doc])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].document, doc)
        self.assertEqual(result[0].raw_data, fake_model)

    def test_update_welearn_document_unauthorized_license(self):
        bitstream = Bitstream(
            uuid="u",
            name="n",
            handle=None,
            type="t",
            expand=[],
            bundleName="original",
            description=None,
            format="f",
            mimeType="m",
            sizeBytes=1,
            parentObject=None,
            retrieveLink="/pdf",
            checkSum=None,
            sequenceId=1,
            code="by-nc",
            policies=None,
            link="",
            metadata=[],
        )
        model = MagicMock()
        model.name = "Titre"
        model.handle = "1234"
        model.bitstreams = [bitstream]
        model.metadata = []
        with self.assertRaises(UnauthorizedLicense):
            self.collector._update_welearn_document(
                WrapperRawData(raw_data=model, document=self.doc)
            )

    def test_update_welearn_document_no_description(self):
        bitstream = Bitstream(
            uuid="u",
            name="n",
            handle=None,
            type="t",
            expand=[],
            bundleName="original",
            description=None,
            format="f",
            mimeType="m",
            sizeBytes=1,
            parentObject=None,
            retrieveLink="/pdf",
            checkSum=None,
            sequenceId=1,
            code="by",
            policies=None,
            link="",
            metadata=[],
        )
        model = MagicMock()
        model.name = "Titre"
        model.handle = "1234"
        model.bitstreams = [bitstream]
        model.metadata = []
        with self.assertRaises(NoDescriptionFoundError):
            self.collector._update_welearn_document(
                WrapperRawData(raw_data=model, document=self.doc)
            )

    def test_update_welearn_document_too_many_languages(self):
        bitstream = Bitstream(
            uuid="u",
            name="n",
            handle=None,
            type="t",
            expand=[],
            bundleName="original",
            description=None,
            format="f",
            mimeType="m",
            sizeBytes=1,
            parentObject=None,
            retrieveLink="/pdf",
            checkSum=None,
            sequenceId=1,
            code="by",
            policies=None,
            link="",
            metadata=[],
        )
        meta = [
            Metadatum(
                key="dc.description.abstract",
                value="Résumé.",
                language=None,
                schema="s",
                element="e",
                qualifier=None,
            ),
            Metadatum(
                key="dc.language",
                value="fr",
                language=None,
                schema="s",
                element="e",
                qualifier=None,
            ),
        ]
        model = MagicMock()
        model.name = "Titre"
        model.handle = "1234"
        model.bitstreams = [bitstream]
        model.metadata = meta
        # Simule un mauvais format de langue (liste)
        with patch.object(
            self.collector,
            "_format_metadata",
            return_value={
                "dc.description.abstract": "Résumé.",
                "dc.language": ["fr", "en"],
            },
        ):
            with self.assertRaises(TooMuchLanguages):
                self.collector._update_welearn_document(
                    WrapperRawData(raw_data=model, document=self.doc)
                )

    def test_update_welearn_document_wrong_lang_format(self):
        bitstream = Bitstream(
            uuid="u",
            name="n",
            handle=None,
            type="t",
            expand=[],
            bundleName="original",
            description=None,
            format="f",
            mimeType="m",
            sizeBytes=1,
            parentObject=None,
            retrieveLink="/pdf",
            checkSum=None,
            sequenceId=1,
            code="by",
            policies=None,
            link="",
            metadata=[],
        )
        meta = [
            Metadatum(
                key="dc.description.abstract",
                value="Résumé.",
                language=None,
                schema="s",
                element="e",
                qualifier=None,
            ),
            Metadatum(
                key="dc.language",
                value="notalanguage",
                language=None,
                schema="s",
                element="e",
                qualifier=None,
            ),
        ]
        model = MagicMock()
        model.name = "Titre"
        model.handle = "1234"
        model.bitstreams = [bitstream]
        model.metadata = meta
        with patch.object(
            self.collector,
            "_format_metadata",
            return_value={
                "dc.description.abstract": "Résumé.",
                "dc.language": "notalanguage",
            },
        ):
            with self.assertRaises(WrongLangFormat):
                self.collector._update_welearn_document(
                    WrapperRawData(raw_data=model, document=self.doc)
                )


if __name__ == "__main__":
    unittest.main()
