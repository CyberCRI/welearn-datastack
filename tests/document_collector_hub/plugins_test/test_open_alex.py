import json
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from welearn_datastack import constants
from welearn_datastack.exceptions import PDFFileSizeExceedLimit, UnauthorizedPublisher
from welearn_datastack.plugins.rest_requesters.open_alex import OpenAlexCollector


class MockResponse:
    def __init__(self, text="", status_code=200, content=None):
        self.text = text
        self.status_code = status_code
        self.content = content or text.encode("utf-8")

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(self.text)


class TestOpenAlexCollector(TestCase):
    def setUp(self):
        os.environ["TEAM_EMAIL"] = "welearn@learningplanetinstitute.org"
        self.openalexColector = OpenAlexCollector()
        self.json_response_path_one_work: Path = (
            Path(__file__).parent.parent / "resources/open_alex_response.json"
        )
        self.json_several_works: Path = (
            Path(__file__).parent.parent
            / "resources/open_alex_response_several_works_1.json"
        )
        self.pdf: Path = (
            Path(__file__).parent.parent
            / "resources/file_plugin_input/pages_with_headers_and_footers_pdf.pdf"
        )

    def test__invert_abstract(self):
        awaited_result = "This test is a test. This must be correct."
        test_values = {
            "This": [0, 5],
            "test": [1],
            "is": [2],
            "a": [3],
            "test.": [4],
            "must": [6],
            "be": [7],
            "correct.": [8],
        }
        result = self.openalexColector._invert_abstract(test_values)
        self.assertEqual(awaited_result, result)

    def test__generate_api_query_params(self):
        urls = [
            "https://example.org/1",
            "https://example.org/2",
            "https://example.org/3",
        ]
        joined_urls = "|".join(urls)
        page_ln = 200
        tested_query = self.openalexColector._generate_api_query_params(urls, page_ln)
        self.assertDictEqual(
            {
                "filter": f"ids.openalex:{joined_urls}",
                "mailto": "welearn@learningplanetinstitute.org",
                "per_page": page_ln,
                "select": "title,ids,language,abstract_inverted_index,publication_date,authorships,open_access,best_oa_location,publication_date,type,topics,keywords,referenced_works,related_works,locations",
            },
            tested_query,
        )

    @patch("welearn_datastack.modules.pdf_extractor._send_pdf_to_tika")
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.get_new_https_session")
    def test__get_pdf_content(self, http_session_mock, mock_send_pdf_to_tika):

        mock_session = Mock()
        http_session_mock.return_value = mock_session

        mock_session.get.return_value = MockResponse(
            status_code=200, content=self.pdf.read_bytes()
        )
        mock_send_pdf_to_tika.return_value = {
            "X-TIKA:content": "<div class='page'>2.2. Measurements of Fiber Parameters Small pieces were extracted from various positions on the strip. and mechanical properties to provide additional information regarding these areas of study and growth conditions.</div>"
        }
        tested_result = self.openalexColector._get_pdf_content("https://example.org/1")
        self.assertTrue(
            tested_result.startswith(
                "2.2. Measurements of Fiber Parameters Small pieces were extracted from various positions on the strip."
            )
        )
        self.assertTrue(
            tested_result.endswith(
                "and mechanical properties to provide additional information regarding these areas of study and growth conditions."
            )
        )

    @patch("welearn_datastack.plugins.rest_requesters.open_alex.get_new_https_session")
    def test_get_pdf_content_size_limit_error(self, http_session_mock):

        mock_session = Mock()
        http_session_mock.return_value = mock_session
        mock_resp = MockResponse(status_code=200, content=self.pdf.read_bytes())
        size_limit = 1000000
        mock_resp.headers = {"content-length": size_limit * 2}

        mock_session.head.return_value = mock_resp

        with self.assertRaises(PDFFileSizeExceedLimit):
            self.openalexColector._get_pdf_content(
                "https://example.org/1", file_size_limit=size_limit
            )

        with self.assertRaises(ValueError):
            self.openalexColector._get_pdf_content(
                "https://example.org/1", file_size_limit=-1
            )

    def test__transform_topics(self):
        original_json = [
            {
                "id": "https://openalex.org/T11213",
                "display_name": "Genomic variations and chromosomal abnormalities",
                "score": 0.9998,
                "subfield": {
                    "id": "https://openalex.org/subfields/1311",
                    "display_name": "Genetics",
                },
                "field": {
                    "id": "https://openalex.org/fields/13",
                    "display_name": "Biochemistry, Genetics and Molecular Biology",
                },
                "domain": {
                    "id": "https://openalex.org/domains/1",
                    "display_name": "Life Sciences",
                },
            },
            {
                "id": "https://openalex.org/T10434",
                "display_name": "Chromosomal and Genetic Variations",
                "score": 0.997,
                "subfield": {
                    "id": "https://openalex.org/subfields/1110",
                    "display_name": "Plant Science",
                },
                "field": {
                    "id": "https://openalex.org/fields/11",
                    "display_name": "Agricultural and Biological Sciences",
                },
                "domain": {
                    "id": "https://openalex.org/domains/1",
                    "display_name": "Life Sciences",
                },
            },
            {
                "id": "https://openalex.org/T11642",
                "display_name": "Genomics and Rare Diseases",
                "score": 0.9962,
                "subfield": {
                    "id": "https://openalex.org/subfields/1311",
                    "display_name": "Genetics",
                },
                "field": {
                    "id": "https://openalex.org/fields/13",
                    "display_name": "Biochemistry, Genetics and Molecular Biology",
                },
                "domain": {
                    "id": "https://openalex.org/domains/1",
                    "display_name": "Life Sciences",
                },
            },
        ]

        awaited_result = [
            {
                "external_id": "https://openalex.org/domains/1",
                "name": "Life Sciences",
                "depth": 0,
                "external_depth_name": "domain",
                "directly_contained_in": [],
            },
            {
                "external_id": "https://openalex.org/fields/13",
                "name": "Biochemistry, Genetics and Molecular Biology",
                "depth": 1,
                "external_depth_name": "field",
                "directly_contained_in": ["https://openalex.org/domains/1"],
            },
            {
                "external_id": "https://openalex.org/subfields/1311",
                "name": "Genetics",
                "depth": 2,
                "external_depth_name": "subfield",
                "directly_contained_in": ["https://openalex.org/fields/13"],
            },
            {
                "external_id": "https://openalex.org/T11213",
                "name": "Genomic variations and chromosomal abnormalities",
                "depth": 3,
                "external_depth_name": "topic",
                "directly_contained_in": ["https://openalex.org/subfields/1311"],
            },
            {
                "external_id": "https://openalex.org/fields/11",
                "name": "Agricultural and Biological Sciences",
                "depth": 1,
                "external_depth_name": "field",
                "directly_contained_in": ["https://openalex.org/domains/1"],
            },
            {
                "external_id": "https://openalex.org/subfields/1110",
                "name": "Plant Science",
                "depth": 2,
                "external_depth_name": "subfield",
                "directly_contained_in": ["https://openalex.org/fields/11"],
            },
            {
                "external_id": "https://openalex.org/T10434",
                "name": "Chromosomal and Genetic Variations",
                "depth": 3,
                "external_depth_name": "topic",
                "directly_contained_in": ["https://openalex.org/subfields/1110"],
            },
            {
                "external_id": "https://openalex.org/T11642",
                "name": "Genomics and Rare Diseases",
                "depth": 3,
                "external_depth_name": "topic",
                "directly_contained_in": ["https://openalex.org/subfields/1311"],
            },
        ]

        result = self.openalexColector._transform_topics(original_json)
        self.assertListEqual(result, awaited_result)

    @patch(
        "welearn_datastack.plugins.rest_requesters.open_alex.OpenAlexCollector._get_pdf_content"
    )
    def test__convert_json_in_welearn_document(self, mock_pdf):
        mock_pdf.return_value = "The findings highlight the intricate interplay between genomic architecture and the mechanisms driving CNV formation."
        with self.json_response_path_one_work.open(mode="r") as f:
            content_json = json.load(f)
            input_json = content_json["results"][0]
            best_oa = input_json["best_oa_location"]

            best_oa["pdf_url"] = "https://example.org/openalexdoc"
            document = self.openalexColector._convert_json_in_welearn_document(
                input_json
            )

            self.assertEqual(
                document.document_url,
                "https://openalex.org/W4407087308",
            )
            self.assertEqual(
                document.document_title,
                "Template switching during DNA replication is a prevalent source of adaptive gene amplification",
            )
            self.assertEqual(document.document_content, mock_pdf.return_value)
            self.assertEqual(document.document_lang, "en")
            self.assertEqual(document.document_corpus, "openalex")
            self.assertEqual(
                document.document_desc,
                """Copy number variants (CNVs) are an important source of genetic variation underlying rapid adaptation and genome evolution. Whereas point mutation rates vary with genomic location and local DNA features, the role of genome architecture in the formation and evolutionary dynamics of CNVs is poorly understood. Previously, we found the GAP1 gene in Saccharomyces cerevisiae undergoes frequent amplification and selection in glutamine-limitation. The gene is flanked by two long terminal repeats (LTRs) and proximate to an origin of DNA replication (autonomously replicating sequence, ARS), which likely promote rapid GAP1 CNV formation. To test the role of these genomic elements on CNV-mediated adaptive evolution, we evolved engineered strains lacking either the adjacent LTRs, ARS, or all elements in glutamine-limited chemostats. Using a CNV reporter system and neural network simulation-based inference (nnSBI) we quantified the formation rate and fitness effect of CNVs for each strain. Removal of local DNA elements significantly impacts the fitness effect of GAP1 CNVs and the rate of adaptation. In 177 CNV lineages, across all four strains, between 26% and 80% of all GAP1 CNVs are mediated by Origin Dependent Inverted Repeat Amplification (ODIRA) which results from template switching between the leading and lagging strand during DNA synthesis. In the absence of the local ARS, distal ones mediate CNV formation via ODIRA. In the absence of local LTRs, homologous recombination can mediate gene amplification following de novo retrotransposon events. Our study reveals that template switching during DNA replication is a prevalent source of adaptive CNVs.""",
            )
            self.assertEqual(
                document.document_title,
                "Template switching during DNA replication is a prevalent source of adaptive gene amplification",
            )

            details = document.document_details
            self.assertEqual(details["doi"], "https://doi.org/10.7554/elife.98934.3")
            self.assertEqual(details["publisher"], "eLife Sciences Publications Ltd")
            self.assertEqual(
                details["license_url"], "https://creativecommons.org/licenses/by/4.0/"
            )
            self.assertEqual(details["issn"], "2050-084X")
            self.assertTrue(details["content_from_pdf"])
            self.assertEqual(len(details["topics"]), 8)
            self.assertDictEqual(
                details["topics"][0],
                {
                    "depth": 0,
                    "directly_contained_in": [],
                    "external_depth_name": "domain",
                    "external_id": "https://openalex.org/domains/1",
                    "name": "Life Sciences",
                },
            )
            self.assertEqual(details["tags"][0], "Replication")
            self.assertEqual(len(details["referenced_works"]), 107)
            self.assertIn(
                "https://openalex.org/W1986559385", details["referenced_works"]
            )
            self.assertEqual(len(details["related_works"]), 10)
            self.assertIn("https://openalex.org/W4388014327", details["related_works"])

    @patch(
        "welearn_datastack.plugins.rest_requesters.open_alex.OpenAlexCollector._get_pdf_content"
    )
    def test__convert_json_in_welearn_document_from_unauthorized_publisher(
        self, mock_pdf
    ):
        mock_pdf.return_value = "The findings highlight the intricate interplay between genomic architecture and the mechanisms driving CNV formation."
        with self.json_response_path_one_work.open(mode="r") as f:
            content_json = json.load(f)
            input_json = content_json["results"][0]
            input_json["locations"][0]["source"]["host_organization_lineage"].append(
                "https://example.org/" + constants.PUBLISHERS_TO_AVOID[0]
            )
            best_oa = input_json["best_oa_location"]

            best_oa["pdf_url"] = "https://example.org/openalexdoc"
            with self.assertRaises(UnauthorizedPublisher):
                self.openalexColector._convert_json_in_welearn_document(input_json)

    @patch(
        "welearn_datastack.plugins.rest_requesters.open_alex.OpenAlexCollector._get_pdf_content"
    )
    @patch("welearn_datastack.plugins.rest_requesters.open_alex.get_new_https_session")
    def test_run(self, http_session_mock, mock_pdf):
        mock_pdf.return_value = "The findings highlight the intricate interplay between genomic architecture and the mechanisms driving CNV formation."
        mock_session = Mock()
        http_session_mock.return_value = mock_session
        several_works_content = json.loads(self.json_several_works.open("r").read())
        urls = [x["id"] for x in several_works_content["results"]]

        mock_session.get.return_value = MockResponse(
            self.json_several_works.open("r").read(), 200
        )

        collected_docs, error_docs = self.openalexColector.run(
            urls_or_external_ids=urls
        )

        self.assertEqual(len(collected_docs), 39)
        self.assertEqual(len(error_docs), 50 - 39)

    def test__remove_useless_first_word(self):
        string_to_test = "Abstract Background Preventing infections due to MDR pathogens is particularly important in the era of MDR pathogens."
        string2_to_test = "Abstract and introduction : Preventing infections due to MDR pathogens is particularly important in the era of MDR pathogens."
        string3_to_test = "Abstract Preventing infections due to MDR pathogens is particularly important in the era of MDR pathogens."

        tested_string = self.openalexColector._remove_useless_first_word(
            string_to_test, ["abstract", "background"]
        )
        tested_string2 = self.openalexColector._remove_useless_first_word(
            string2_to_test, ["abstract", "background"]
        )
        tested_string3 = self.openalexColector._remove_useless_first_word(
            string3_to_test, ["abstract", "background"]
        )

        self.assertEqual(
            tested_string,
            "Preventing infections due to MDR pathogens is particularly important in the era of MDR pathogens.",
        )
        self.assertEqual(
            tested_string2,
            "Abstract and introduction : Preventing infections due to MDR pathogens is particularly important in the era of MDR pathogens.",
        )
        self.assertEqual(
            tested_string3,
            "Preventing infections due to MDR pathogens is particularly important in the era of MDR pathogens.",
        )
