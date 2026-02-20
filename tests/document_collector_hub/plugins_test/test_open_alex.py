import json
import os
import unittest
from unittest.mock import MagicMock, patch

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.db_wrapper import WrapperRawData, WrapperRetrieveDocument
from welearn_datastack.data.source_models.open_alex import (
    Affiliation,
    Author,
    Authorship,
    BestOaLocation,
    Domain,
    Field,
    Ids,
    Institution,
    Keyword,
    Location,
    Meta,
    OpenAccess,
    OpenAlexModel,
    OpenAlexResult,
    Source,
    Source1,
    Subfield,
    Topic,
)
from welearn_datastack.plugins.rest_requesters.open_alex import OpenAlexCollector

# Helper to build a minimal valid OpenAlexResult


def build_openalex_result(
    url: str = "https://openalex.org/W123",
    doi: str = "10.1234/example",
    title: str = "Sample Title",
):
    ids = Ids(openalex=url, doi=doi, mag="", pmid="", pmcid="")
    author = Author(id="A1", display_name="John Doe", orcid=None)
    institution = Institution(
        id="I1", display_name="Inst", ror="", country_code=None, type="uni", lineage=[]
    )
    affiliation = Affiliation(raw_affiliation_string="Inst", institution_ids=["I1"])
    authorship = Authorship(
        author_position="first",
        author=author,
        institutions=[institution],
        countries=["FR"],
        is_corresponding=True,
        raw_author_name="John Doe",
        raw_affiliation_strings=["Inst"],
        affiliations=[affiliation],
    )
    open_access = OpenAccess(
        is_oa=True,
        oa_status="gold",
        oa_url="https://openalex.org/oa",
        any_repository_has_fulltext=True,
    )
    source = Source(
        id="S1",
        display_name="Source",
        issn_l="1234-5678",
        issn=["1234-5678"],
        is_oa=True,
        is_in_doaj=True,
        is_indexed_in_scopus=True,
        is_core=True,
        host_organization=None,
        host_organization_name=None,
        host_organization_lineage=[],
        host_organization_lineage_names=[],
        type="journal",
    )
    best_oa_location = BestOaLocation(
        is_oa=True,
        landing_page_url="https://openalex.org/landing",
        pdf_url="https://openalex.org/pdf",
        source=source,
        license="cc-by",
        license_id="cc-by",
        version="publishedVersion",
        is_accepted=True,
        is_published=True,
    )
    subfield = Subfield(id="sf1", display_name="Subfield")
    field = Field(id="f1", display_name="Field")
    domain = Domain(id="d1", display_name="Domain")
    topic = Topic(
        id="t1",
        display_name="Topic",
        score=1.0,
        subfield=subfield,
        field=field,
        domain=domain,
    )
    keyword = Keyword(id="k1", display_name="Keyword", score=1.0)
    source1 = Source1(
        id="S1",
        display_name="Source",
        issn_l="1234-5678",
        issn=["1234-5678"],
        is_oa=True,
        is_in_doaj=True,
        is_indexed_in_scopus=True,
        is_core=True,
        host_organization=None,
        host_organization_name=None,
        host_organization_lineage=["/org1"],
        host_organization_lineage_names=["Org1"],
        type="journal",
    )
    location = Location(
        is_oa=True,
        landing_page_url="https://openalex.org/landing",
        pdf_url="https://openalex.org/pdf",
        source=source1,
        license="cc-by",
        license_id="cc-by",
        version="publishedVersion",
        is_accepted=True,
        is_published=True,
    )
    return OpenAlexResult(
        title=title,
        ids=ids,
        language="en",
        publication_date="2022-01-01",
        authorships=[authorship],
        open_access=open_access,
        best_oa_location=best_oa_location,
        abstract_inverted_index={"Background": [0], "study": [1]},
        type="journal-article",
        topics=[topic],
        keywords=[keyword],
        referenced_works=["W2"],
        related_works=["W3"],
        locations=[location],
    )


class TestOpenAlexCollector(unittest.TestCase):
    def setUp(self):
        os.environ["TEAM_EMAIL"] = "team@openalex.org"
        self.collector = OpenAlexCollector()
        self.welearn_doc = WeLearnDocument(
            url="https://openalex.org/W123",
            title="Doc",
            description="",
            full_content="",
            details={},
        )

    # Test _invert_abstract returns correct string
    def test_invert_abstract_returns_correct_string(self):
        inv = {"Background": [0], "study": [1]}
        result = self.collector._invert_abstract(inv)
        self.assertEqual(result, "Background study")

    # Test _generate_api_query_params returns expected dict
    def test_generate_api_query_params_returns_expected_dict(self):
        params = self.collector._generate_api_query_params(
            ["https://openalex.org/W123"], 10
        )
        self.assertIn("filter", params)
        self.assertIn("per_page", params)
        self.assertIn("mailto", params)
        self.assertIn("select", params)
        self.assertEqual(params["per_page"], 10)
        self.assertEqual(params["mailto"], "team@openalex.org")

    # Test _remove_useless_first_word removes word if present
    def test_remove_useless_first_word_removes_word(self):
        s = self.collector._remove_useless_first_word(
            "Background Study of X", ["Background"]
        )
        self.assertEqual(s, "Study of X")

    # Test _remove_useless_first_word returns original if not present
    def test_remove_useless_first_word_returns_original(self):
        s = self.collector._remove_useless_first_word("Study of X", ["Background"])
        self.assertEqual(s, "Study of X")

    # Test _transform_topics returns correct structure
    def test_transform_topics_returns_correct_structure(self):
        topics = [
            Topic(
                id="t1",
                display_name="Topic",
                domain=Domain(id="d1", display_name="Domain"),
                field=Field(id="f1", display_name="Field"),
                subfield=Subfield(id="sf1", display_name="Subfield"),
                score=1.0,
            )
        ]
        result = self.collector._transform_topics(topics)
        self.assertTrue(any(x.external_depth_name == "domain" for x in result))
        self.assertTrue(any(x.external_depth_name == "topic" for x in result))

    # Test _update_welearn_document returns a WeLearnDocument with expected values
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.get_pdf_content")
    def test_update_welearn_document_returns_expected_document(self, mock_pdf):
        openalex_result = build_openalex_result()
        wrapper = WrapperRawData(document=self.welearn_doc, raw_data=openalex_result)
        doc = self.collector._update_welearn_document(wrapper)
        self.assertEqual(doc.title, openalex_result.title)
        self.assertIn("publication_date", doc.details)
        self.assertEqual(doc.details["type"], openalex_result.type)
        self.assertTrue(doc.details["content_from_pdf"])
        self.assertIn("license_url", doc.details)
        self.assertEqual(
            doc.details["issn"], openalex_result.best_oa_location.source.issn_l
        )
        self.assertEqual(
            doc.details["authors"][0]["name"],
            openalex_result.authorships[0].author.display_name,
        )

    # Test _update_welearn_document raises on closed access
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.get_new_https_session")
    def test_update_welearn_document_raises_on_closed_access(self, mock_session):
        openalex_result = build_openalex_result()
        openalex_result.open_access.is_oa = False
        wrapper = WrapperRawData(document=self.welearn_doc, raw_data=openalex_result)
        # Mock any network call that could be triggered (e.g. PDF download)
        mock_session.return_value.get.return_value = MagicMock()
        with self.assertRaises(Exception):
            self.collector._update_welearn_document(wrapper)

    # Test run returns WrapperRetrieveDocument with correct document and error_info for missing url
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.get_new_https_session")
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.OpenAlexModel")
    def test_run_returns_error_for_missing_url(self, mock_model, mock_session):
        # Simulate OpenAlexModel returns no results
        mock_model.model_validate_json.return_value = OpenAlexModel(
            meta=Meta(
                count=0, db_response_time_ms=0, page=0, per_page=0, groups_count={}
            ),
            results=[],
            group_by=[],
        )
        mock_http = MagicMock()
        mock_http.get.return_value.json.return_value = {"results": []}
        mock_http.get.return_value.raise_for_status = lambda: None
        mock_session.return_value = mock_http
        result = self.collector.run([self.welearn_doc])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WrapperRetrieveDocument)
        self.assertIn("not returned", result[0].error_info)

    # Test run returns WrapperRetrieveDocument with document on success
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.get_new_https_session")
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.OpenAlexModel")
    @patch.object(OpenAlexCollector, "_update_welearn_document")
    def test_run_returns_document_on_success(
        self, mock_update, mock_model, mock_session
    ):
        openalex_result = build_openalex_result()
        mock_model.model_validate_json.return_value = OpenAlexModel(
            meta=Meta(
                count=0, db_response_time_ms=0, page=0, per_page=0, groups_count={}
            ),
            results=[openalex_result],
            group_by=[],
        )
        mock_http = MagicMock()
        mock_http.get.return_value.json.return_value = json.loads(
            OpenAlexModel(
                meta=Meta(
                    count=0, db_response_time_ms=0, page=0, per_page=0, groups_count={}
                ),
                results=[openalex_result],
                group_by=[],
            ).model_dump_json()
        )
        mock_http.get.return_value.raise_for_status = lambda: None
        mock_session.return_value = mock_http
        mock_update.return_value = self.welearn_doc
        result = self.collector.run([self.welearn_doc])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WrapperRetrieveDocument)
        self.assertEqual(result[0].document, self.welearn_doc)
        self.assertIsNone(result[0].error_info)

    # Test run returns error on API exception
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.get_new_https_session")
    @patch(
        "welearn_datastack.plugins.rest_requesters.open_alex.get_http_code_from_exception",
        return_value=500,
    )
    def test_run_returns_error_on_api_exception(self, mock_code, mock_session):
        mock_http = MagicMock()
        mock_http.get.side_effect = Exception("API error")
        mock_session.return_value = mock_http
        result = self.collector.run([self.welearn_doc])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], WrapperRetrieveDocument)
        self.assertEqual(result[0].http_error_code, 500)
        self.assertIn(
            "Error while trying to get contents from OpenAlex API", result[0].error_info
        )
