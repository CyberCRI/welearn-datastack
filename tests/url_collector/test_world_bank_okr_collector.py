import unittest
from unittest.mock import MagicMock, patch

from welearn_database.data.enumeration import ExternalIdType

from welearn_datastack.exceptions import NotEnoughData, NoUrl

MODULE = "welearn_datastack.collectors.world_bank_okr"
from welearn_datastack.collectors.world_bank_okr import (  # noqa: E402
    WorldBankOpenKnowledgeRepositoryCollector,
)
from welearn_datastack.data.xml_data import XMLData

RECORD_NORMAL = """
<record>
    <header>
        <identifier>oai:openknowledge.worldbank.org:10986/12345</identifier>
        <datestamp>2024-01-15T10:00:00Z</datestamp>
    </header>
    <metadata>
        <mods:mods>
            <mods:identifier type="uri">https://hdl.handle.net/10986/12345</mods:identifier>
            <mods:identifier type="doi">https://doi.org/10.1596/12345</mods:identifier>
        </mods:mods>
    </metadata>
</record>
"""

RECORD_DELETED = """
<record>
    <header status="deleted">
        <identifier>oai:openknowledge.worldbank.org:10986/99999</identifier>
        <datestamp>2024-01-16T10:00:00Z</datestamp>
    </header>
</record>
"""

RECORD_NO_DOI = """
<record>
    <header>
        <identifier>oai:openknowledge.worldbank.org:10986/55555</identifier>
        <datestamp>2024-01-17T10:00:00Z</datestamp>
    </header>
    <metadata>
        <mods:mods>
            <mods:identifier type="uri">https://hdl.handle.net/10986/55555</mods:identifier>
        </mods:mods>
    </metadata>
</record>
"""

RECORD_NO_URI = """
<record>
    <header>
        <identifier>oai:openknowledge.worldbank.org:10986/66666</identifier>
        <datestamp>2024-01-18T10:00:00Z</datestamp>
    </header>
    <metadata>
        <mods:mods>
            <mods:identifier type="doi">https://doi.org/10.1596/66666</mods:identifier>
        </mods:mods>
    </metadata>
</record>
"""

RECORD_NO_HEADER_IDENTIFIER = """
<record>
    <header>
        <datestamp>2024-01-19T10:00:00Z</datestamp>
    </header>
    <metadata>
        <mods:mods>
            <mods:identifier type="uri">https://hdl.handle.net/10986/77777</mods:identifier>
        </mods:mods>
    </metadata>
</record>
"""

LIST_RECORDS_RESPONSE = f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH>
    <ListRecords>
        {RECORD_NORMAL}
        {RECORD_DELETED}
        {RECORD_NO_DOI}
    </ListRecords>
</OAI-PMH>
"""


def make_collector(date_last_insert: int = 1700000000):
    corpus = MagicMock()
    corpus.id = "corpus-uuid-1234"
    return WorldBankOpenKnowledgeRepositoryCollector(
        corpus=corpus, date_last_insert=date_last_insert
    )


class TestExtractUrl(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector()

    def test_extract_url_success(self):

        url = self.collector._extract_url(XMLData(content=RECORD_NORMAL, attributes={}))
        self.assertEqual(
            url,
            "https://openknowledge.worldbank.org/handle/10986/12345",
        )

    def test_extract_url_raises_no_url_when_missing(self):
        from welearn_datastack.data.xml_data import XMLData

        with self.assertRaises(NoUrl):
            self.collector._extract_url(XMLData(content=RECORD_NO_URI, attributes={}))

    def test_extract_url_raises_no_url_when_duplicated(self):
        from welearn_datastack.data.xml_data import XMLData

        duplicated = """
        <record>
            <mods:identifier type="uri">https://hdl.handle.net/10986/111</mods:identifier>
            <mods:identifier type="uri">https://hdl.handle.net/10986/222</mods:identifier>
        </record>
        """
        with self.assertRaises(NoUrl):
            self.collector._extract_url(XMLData(content=duplicated, attributes={}))


class TestExtractDoi(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector()

    def test_extract_doi_success(self):
        from welearn_datastack.data.xml_data import XMLData

        doi = self.collector._extract_doi(XMLData(content=RECORD_NORMAL, attributes={}))
        self.assertEqual(doi, "10.1596/12345")

    def test_extract_doi_returns_none_when_missing(self):
        from welearn_datastack.data.xml_data import XMLData

        doi = self.collector._extract_doi(XMLData(content=RECORD_NO_DOI, attributes={}))
        self.assertIsNone(doi)


class TestExtractExternalId(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector()

    def test_extract_external_id_success(self):
        from welearn_datastack.data.xml_data import XMLData

        external_id = self.collector._extract_external_id(
            XMLData(content=RECORD_NORMAL, attributes={})
        )
        self.assertEqual(external_id, "oai:openknowledge.worldbank.org:10986/12345")

    def test_extract_external_id_raises_not_enough_data(self):
        from welearn_datastack.data.xml_data import XMLData

        with self.assertRaises(NotEnoughData):
            self.collector._extract_external_id(
                XMLData(content=RECORD_NO_HEADER_IDENTIFIER, attributes={})
            )


class TestIsDeleted(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector()

    def test_is_deleted_true(self):
        from welearn_datastack.data.xml_data import XMLData

        self.assertTrue(
            self.collector._is_deleted(XMLData(content=RECORD_DELETED, attributes={}))
        )

    def test_is_deleted_false(self):
        from welearn_datastack.data.xml_data import XMLData

        self.assertFalse(
            self.collector._is_deleted(XMLData(content=RECORD_NORMAL, attributes={}))
        )


class TestFormatDate(unittest.TestCase):
    def test_format_date(self):
        # 1700000000 -> 2023-11-14T22:13:20Z (GMT)
        collector = make_collector(date_last_insert=1700000000)
        formatted = collector._format_date()
        self.assertEqual(formatted, "2023-11-14T22:13:20Z")


class TestExtractWorldBankOkrDocument(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector()

    def test_filters_out_deleted_and_builds_documents(self):
        from welearn_datastack.modules.xml_extractor import XMLExtractor

        extractor = XMLExtractor(LIST_RECORDS_RESPONSE)
        documents = self.collector._extract_world_bank_okr_document(extractor)

        # 3 records dans la fixture, 1 deleted -> 2 documents attendus
        self.assertEqual(len(documents), 2)

        external_ids = {d.external_id for d in documents}
        self.assertIn("oai:openknowledge.worldbank.org:10986/12345", external_ids)
        self.assertIn("oai:openknowledge.worldbank.org:10986/55555", external_ids)
        self.assertNotIn("oai:openknowledge.worldbank.org:10986/99999", external_ids)

        doc_with_doi = next(
            d
            for d in documents
            if d.external_id == "oai:openknowledge.worldbank.org:10986/12345"
        )
        self.assertEqual(
            doc_with_doi.url,
            "https://openknowledge.worldbank.org/handle/10986/12345",
        )
        self.assertEqual(doc_with_doi.doi, "10.1596/12345")
        self.assertEqual(doc_with_doi.external_id_type, ExternalIdType.API_ID)
        self.assertEqual(doc_with_doi.corpus_id, self.collector.corpus.id)

        doc_without_doi = next(
            d
            for d in documents
            if d.external_id == "oai:openknowledge.worldbank.org:10986/55555"
        )
        self.assertIsNone(doc_without_doi.doi)


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.collector = make_collector(date_last_insert=1700000000)

    @patch(f"{MODULE}.get_new_https_session")
    def test_collect_calls_api_with_expected_params_and_parses_response(
        self, mock_get_session
    ):
        mock_response = MagicMock()
        mock_response.text = LIST_RECORDS_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        documents = self.collector.collect()

        # Verifie que get_new_https_session a bien ete utilise
        mock_get_session.assert_called_once()

        # Verifie les parametres de l'appel HTTP
        mock_session.get.assert_called_once_with(
            url=self.collector.api_base_url,
            headers=self.collector.headers,
            params={
                "verb": "ListRecords",
                "metadataPrefix": "mods",
                "from": "2023-11-14T22:13:20Z",
            },
        )

        mock_response.raise_for_status.assert_called_once()

        # Verifie que le resultat est correctement parse (2 records valides)
        self.assertEqual(len(documents), 2)

    @patch(f"{MODULE}.get_new_https_session")
    def test_collect_propagates_http_error(self, mock_get_session):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        with self.assertRaises(Exception):
            self.collector.collect()

    @patch(f"{MODULE}.get_new_https_session")
    def test_collect_returns_empty_list_when_no_records(self, mock_get_session):
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
        <OAI-PMH><ListRecords></ListRecords></OAI-PMH>"""
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        documents = self.collector.collect()
        self.assertEqual(documents, [])
