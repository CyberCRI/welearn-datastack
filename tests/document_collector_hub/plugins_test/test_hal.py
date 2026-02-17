import unittest
from unittest.mock import MagicMock, patch

from welearn_datastack.data.db_wrapper import WrapperRawData
from welearn_datastack.plugins.rest_requesters.hal import HALCollector


class DummyWeLearnDocument:
    def __init__(self, url="https://example.com/hal-00006805"):
        self.url = url
        self.title = None
        self.description = None
        self.full_content = None
        self.details = None


class DummyWrapperRawData:
    def __init__(self, raw_data=None, document=None):
        self.raw_data = raw_data or {}
        self.document = document or DummyWeLearnDocument()


class TestHALCollector(unittest.TestCase):
    def setUp(self):
        self.collector = HALCollector()
        self.dummy_doc = DummyWeLearnDocument()
        self.dummy_wrapper = DummyWrapperRawData(document=self.dummy_doc)

    def test_convert_hal_date_to_ts_valid(self):
        ts = self.collector._convert_hal_date_to_ts("2022-01-01T00:00:00Z")
        self.assertIsInstance(ts, float)
        self.assertAlmostEqual(ts, 1640995200.0, delta=10)  # 2022-01-01 UTC

    def test_convert_hal_date_to_ts_empty(self):
        ts = self.collector._convert_hal_date_to_ts("")
        self.assertIsNone(ts)

    def test_create_halids_query_single(self):
        query = self.collector._create_halids_query(["hal-00006805"])
        self.assertEqual(query, "halId_s:hal-00006805")

    def test_create_halids_query_multiple(self):
        query = self.collector._create_halids_query(["hal-00006805", "hal-00333300"])
        self.assertEqual(query, "halId_s:(hal-00006805 OR hal-00333300)")

    def test_get_hal_url(self):
        url = self.collector._get_hal_url({"halId_s": "hal-00006805"})
        self.assertIn("hal-00006805", url)
        self.assertTrue(url.startswith("https://hal.science/hal-00006805"))

    def test_get_details_from_dict_minimal(self):
        details = self.collector._get_details_from_dict(
            {"docid": "1", "authFullName_s": ["A. Author"], "docType_s": "ART"}
        )
        self.assertEqual(details["docid"], "1")
        self.assertEqual(details["type"], "article")
        self.assertEqual(details["authors"], [{"name": "A. Author", "misc": ""}])
        self.assertIsNone(details["publication_date"])
        self.assertIsNone(details["produced_date"])

    def test_get_details_from_dict_with_dates(self):
        d = {
            "docid": "1",
            "authFullName_s": ["A. Author"],
            "docType_s": "ART",
            "publicationDate_tdate": "2022-01-01T00:00:00Z",
            "producedDate_tdate": "2021-01-01T00:00:00Z",
        }
        details = self.collector._get_details_from_dict(d)
        self.assertAlmostEqual(details["publication_date"], 1640995200.0, delta=10)
        self.assertAlmostEqual(details["produced_date"], 1609459200.0, delta=10)

    def test_get_details_from_dict_empty_authors(self):
        d = {"docid": "1", "authFullName_s": [], "docType_s": "ART"}
        details = self.collector._get_details_from_dict(d)
        self.assertEqual(details["authors"], [])

    def test_update_welearn_document_no_titles(self):
        raw_data = {
            "halId_s": "hal-00006805",
            "abstract_s": ["Résumé."],
            "docType_s": "ART",
            "authFullName_s": ["A. Author"],
        }
        wrapper = DummyWrapperRawData(
            raw_data=raw_data, document=DummyWeLearnDocument()
        )
        with self.assertRaises(KeyError):
            self.collector._update_welearn_document(wrapper)

    def test_update_welearn_document_no_abstract(self):
        raw_data = {
            "halId_s": "hal-00006805",
            "title_s": ["Titre"],
            "docType_s": "ART",
            "authFullName_s": ["A. Author"],
        }
        wrapper = DummyWrapperRawData(
            raw_data=raw_data, document=DummyWeLearnDocument()
        )
        with self.assertRaises(KeyError):
            self.collector._update_welearn_document(wrapper)

    def test_update_welearn_document_abstract_absent(self):
        raw_data = {
            "halId_s": "hal-00006805",
            "title_s": ["Titre"],
            "abstract_s": ["absent"],
            "docType_s": "ART",
            "authFullName_s": ["A. Author"],
        }
        wrapper = DummyWrapperRawData(
            raw_data=raw_data, document=DummyWeLearnDocument()
        )
        from welearn_datastack.exceptions import NoContent

        with self.assertRaises(NoContent):
            self.collector._update_welearn_document(wrapper)

    @patch(
        "welearn_datastack.plugins.rest_requesters.hal.get_pdf_content",
        return_value="PDF content",
    )
    def test_update_welearn_document_pdf_mode(self, mock_pdf):
        raw_data = {
            "halId_s": "hal-00006805",
            "title_s": ["Titre"],
            "abstract_s": ["Résumé."],
            "docType_s": "ART",
            "authFullName_s": ["A. Author"],
            "licence_s": "http://hal.archives-ouvertes.fr/licences/publicDomain/",
            "fileMain_s": "https://example.com/fake.pdf",
        }
        wrapper = DummyWrapperRawData(
            raw_data=raw_data, document=DummyWeLearnDocument()
        )
        doc = self.collector._update_welearn_document(wrapper)
        self.assertEqual(doc.title, "Titre")
        self.assertEqual(doc.description, "Résumé.")
        self.assertEqual(doc.full_content, "PDF content")
        self.assertTrue(doc.details["content_from_pdf"])
        self.assertEqual(doc.details["type"], "article")
        self.assertEqual(doc.details["authors"], [{"name": "A. Author", "misc": ""}])

    def test_update_welearn_document_normal_mode(self):
        raw_data = {
            "halId_s": "hal-00006805",
            "title_s": ["Titre"],
            "abstract_s": ["Résumé. Plus."],
            "docType_s": "ART",
            "authFullName_s": ["A. Author"],
        }
        wrapper = DummyWrapperRawData(
            raw_data=raw_data, document=DummyWeLearnDocument()
        )
        doc = self.collector._update_welearn_document(wrapper)
        self.assertEqual(doc.title, "Titre")
        self.assertEqual(doc.description, "Résumé")
        self.assertEqual(doc.full_content, "Résumé. Plus.")
        self.assertFalse(doc.details["content_from_pdf"])
        self.assertEqual(doc.details["type"], "article")
        self.assertEqual(doc.details["authors"], [{"name": "A. Author", "misc": ""}])

    @patch("welearn_datastack.plugins.rest_requesters.hal.get_new_https_session")
    @patch("welearn_datastack.plugins.rest_requesters.hal.HALModel")
    def test_get_jsons_returns_wrappers(self, mock_halmodel, mock_session):
        # Préparation des mocks
        doc1 = DummyWeLearnDocument(url="https://example.com/hal-00006805")
        doc2 = DummyWeLearnDocument(url="https://example.com/hal-00333300")
        hal_documents = [doc1, doc2]
        # Mock de la session HTTP
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": {
                "docs": [
                    {
                        "halId_s": "hal-00006805",
                        "docid": "1",
                        "authFullName_s": ["A. Author"],
                        "docType_s": "ART",
                        "title_s": ["Titre"],
                        "abstract_s": ["Résumé."],
                    },
                    {
                        "halId_s": "hal-00333300",
                        "docid": "2",
                        "authFullName_s": ["B. Author"],
                        "docType_s": "ART",
                        "title_s": ["Titre2"],
                        "abstract_s": ["Résumé2."],
                    },
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_http.get.return_value = mock_response
        mock_session.return_value = mock_http

        # Mock du modèle HALModel
        class DummyDoc:
            def __init__(
                self, halId_s, docid, authFullName_s, docType_s, title_s, abstract_s
            ):
                self.halId_s = halId_s
                self.docid = docid
                self.authFullName_s = authFullName_s
                self.docType_s = docType_s
                self.title_s = title_s
                self.abstract_s = abstract_s

            def model_dump(self):
                return {
                    "halId_s": self.halId_s,
                    "docid": self.docid,
                    "authFullName_s": self.authFullName_s,
                    "docType_s": self.docType_s,
                    "title_s": self.title_s,
                    "abstract_s": self.abstract_s,
                }

        class DummyHALModels:
            def __init__(self):
                self.response = MagicMock()
                self.response.docs = [
                    DummyDoc(
                        "hal-00006805",
                        "1",
                        ["A. Author"],
                        "ART",
                        ["Titre"],
                        ["Résumé."],
                    ),
                    DummyDoc(
                        "hal-00333300",
                        "2",
                        ["B. Author"],
                        "ART",
                        ["Titre2"],
                        ["Résumé2."],
                    ),
                ]

        mock_halmodel.model_validate_json.return_value = DummyHALModels()
        # Appel de la méthode
        wrappers = self.collector._get_jsons(hal_documents)
        self.assertEqual(len(wrappers), 2)
        self.assertEqual(wrappers[0].raw_data["halId_s"], "hal-00006805")
        self.assertEqual(wrappers[1].raw_data["halId_s"], "hal-00333300")
        self.assertIs(wrappers[0].document, doc1)
        self.assertIs(wrappers[1].document, doc2)

    @patch.object(HALCollector, "_get_jsons")
    def test_run_returns_wrapped_documents(self, mock_get_jsons):
        doc1 = DummyWeLearnDocument(url="https://example.com/hal-00006805")
        doc2 = DummyWeLearnDocument(url="https://example.com/hal-00333300")
        # raw_data doit être un dict, pas un HALModel
        raw_data1 = {
            "halId_s": "hal-00006805",
            "docid": "1",
            "authFullName_s": ["A. Author"],
            "docType_s": "ART",
            "title_s": ["Titre"],
            "abstract_s": ["Résumé."],
        }
        raw_data2 = {
            "halId_s": "hal-00333300",
            "docid": "2",
            "authFullName_s": ["B. Author"],
            "docType_s": "ART",
            "title_s": ["Titre2"],
            "abstract_s": ["Résumé2."],
        }
        wrapper1 = WrapperRawData(raw_data=raw_data1, document=doc1)
        wrapper2 = WrapperRawData(raw_data=raw_data2, document=doc2)
        mock_get_jsons.return_value = [wrapper1, wrapper2]

        # # Simuler le comportement attendu de _update_welearn_document
        # # On suppose que run appelle _update_welearn_document et met à jour les champs du document
        # # Pour ce test, on simule le résultat final attendu
        # doc1.title = "Titre"
        # doc1.description = "Résumé."
        # doc1.full_content = "Résumé."
        # doc1.details = {"content_from_pdf": False}
        # doc2.title = "Titre2"
        # doc2.description = "Résumé2."
        # doc2.full_content = "Résumé2."
        # doc2.details = {"content_from_pdf": False}

        result = self.collector.run([doc1, doc2])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].document.title, "Titre")
        self.assertEqual(result[1].document.title, "Titre2")
        self.assertEqual(result[0].document.description, "Résumé")
        self.assertEqual(result[1].document.description, "Résumé2")
        self.assertEqual(result[0].document.full_content, "Résumé.")
        self.assertEqual(result[1].document.full_content, "Résumé2.")
        self.assertFalse(result[0].document.details.get("content_from_pdf", True))
        self.assertFalse(result[1].document.details.get("content_from_pdf", True))
        self.assertTrue(
            all(isinstance(d.document, DummyWeLearnDocument) for d in result)
        )
