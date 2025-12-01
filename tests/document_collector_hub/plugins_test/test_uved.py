import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.details_dataclass.scholar_institution_type import (
    InstitutionTypeName,
)
from welearn_datastack.data.source_models.uved import Category, UVEDMemberItem
from welearn_datastack.plugins.rest_requesters.uved import UVEDCollector


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception("HTTP Error")


class TestUVEDCollector(unittest.TestCase):
    def setUp(self):
        self.collector = UVEDCollector()
        self.resource_path = Path(__file__).parent / "../resources/resource_uved.json"
        with self.resource_path.open() as f:
            self.resource_json = json.load(f)
        self.uved_item = UVEDMemberItem.model_validate(self.resource_json)
        self.base_doc = WeLearnDocument(
            id=1,
            url="https://www.uved.fr/ressource/agroforesterie-bien-etre-et-sante-mentale-1",
            external_id=self.uved_item.uid,
        )

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_transcript_used_as_full_content(self, mock_session):
        # Transcript is not empty, should be used as full_content
        item = self.uved_item.model_copy()
        item.transcription = "Transcript content here."
        mock_session.return_value.get.return_value = MockResponse(item.model_dump())
        # Check that the API is called with the correct external_id
        result = self.collector.run([self.base_doc])
        self.assertEqual(len(result), 1)
        doc = result[0].document
        self.assertEqual(doc.full_content, "Transcript content here.")
        self.assertEqual(doc.title, item.title)
        self.assertTrue(doc.details)
        self.assertEqual(doc.external_id, self.uved_item.uid)

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_transcription_file_used_as_full_content(self, mock_session):
        # Transcript is empty, transcriptionFile is present and used
        item = self.uved_item.model_copy()
        item.transcription = ""
        item.transcriptionFile["url"] = (
            "https://www.uved.fr/fileadmin/user_upload/Documents/pdf/Transcriptions/Arbres/MOOC_UVED_Arbres_Transcription_LeCadre_2.pdf"
        )
        mock_session.return_value.get.return_value = MockResponse(item.model_dump())
        with patch(
            "welearn_datastack.modules.pdf_extractor.extract_txt_from_pdf_with_tika",
            return_value="PDF extracted content.",
        ):
            result = self.collector.run([self.base_doc])
        self.assertEqual(len(result), 1)
        doc = result[0].document
        self.assertEqual(doc.full_content, "PDF extracted content.")
        self.assertTrue(doc.title)
        self.assertTrue(doc.details)
        self.assertEqual(doc.external_id, self.uved_item.uid)

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_description_used_as_full_content(self, mock_session):
        # Neither transcript nor transcriptionFile, fallback to description
        item = self.uved_item.model_copy()
        item.transcription = ""
        item.transcriptionFile = None
        mock_session.return_value.get.return_value = MockResponse(item.model_dump())
        result = self.collector.run([self.base_doc])
        self.assertEqual(len(result), 1)
        doc = result[0].document
        self.assertEqual(doc.full_content, item.description)
        self.assertTrue(doc.title)
        self.assertTrue(doc.details)
        self.assertEqual(doc.external_id, self.uved_item.uid)

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_http_error(self, mock_session):
        # Simulate HTTP error
        mock_session.return_value.get.return_value = MockResponse({}, status_code=500)
        with self.assertRaises(Exception):
            self.collector.run([self.base_doc])

    def test__extract_scholar_institution_types(self):
        # Should extract correct institution types
        institution_types = self.collector._extract_scholar_institution_types(
            self.uved_item.categories
        )
        self.assertTrue(isinstance(institution_types, list))
        institution_type = institution_types[0]
        self.assertEqual(institution_type.original_institution_type_name, "université")
        self.assertListEqual(institution_type.isced_level_awarded, [6, 7, 8])
        self.assertEqual(institution_type.taxonomy_name, InstitutionTypeName.UNI)
        self.assertEqual(institution_type.original_country, "france")

    def test_extract_licence(self):
        # Should extract correct license from categories
        licence = self.collector._extract_licence(self.uved_item)
        self.assertTrue(isinstance(licence, str))
        self.assertEqual("https://creativecommons.org/licenses/by-nc-nd/4.0/", licence)

    def test_clean_txt_content(self):
        # Should clean text content
        raw_content = """
        <p>Édith Le Cadre, professeure à l'Institut Agro Rennes-Angers, discute dans cette vidéo de <strong>la relation entre santé mentale des agriculteurs et agricultrices et agroforesterie</strong>. Elle met en évidence les constats faits par les premiers travaux de recherche ayant exploré ce sujet, et en appelle à une évaluation des effets des arbres sur la santé mentale dans le milieu agricole.</p>
        <p><strong>Objectifs d'apprentissage :</strong></p>
        <p>- Définir les notions de bien-être et de santé mentale<br /> - Identifier les problématiques de santé mentale auxquelles sont aujourd'hui soumis les agriculteurs et agricultrices<br /> - Mettre en relation les enjeux de santé mentale et l'adoption de pratiques d'agroforesterie</p>
        """
        cleaned_content = self.collector._clean_txt_content(raw_content)
        self.assertEqual(
            cleaned_content,
            "Édith Le Cadre, professeure à l'Institut Agro Rennes-Angers, discute dans cette vidéo de la relation entre santé mentale des agriculteurs et agricultrices et agroforesterie. Elle met en évidence les constats faits par les premiers travaux de recherche ayant exploré ce sujet, et en appelle à une évaluation des effets des arbres sur la santé mentale dans le milieu agricole. Objectifs d'apprentissage : - Définir les notions de bien-être et de santé mentale - Identifier les problématiques de santé mentale auxquelles sont aujourd'hui soumis les agriculteurs et agricultrices - Mettre en relation les enjeux de santé mentale et l'adoption de pratiques d'agroforesterie",
        )

    def test__extract_topics(self):
        # Should extract topics from categories
        topics = self.collector._extract_topics(self.uved_item.categories)
        self.assertTrue(isinstance(topics, list))
        self.assertTrue(len(topics) > 0)
        for topic in topics:
            if topic.external_depth_name == "Domaines":
                self.assertEqual(topic.name, "agronomie & agriculture")
                self.assertEqual(topic.external_id, "42")
                self.assertEqual(topic.depth, 0)
            if topic.external_depth_name == "Thèmes":
                self.assertEqual(topic.name, "environnement - santé")
                self.assertEqual(topic.external_id, "86")
                self.assertEqual(topic.depth, 0)

    def test_extract_metadata(self):
        # Should extract metadata dict
        metadata = self.collector._extract_metadata(self.uved_item)
        self.assertTrue(isinstance(metadata, dict))
        self.assertIn("authors", metadata)
        self.assertIn("publisher", metadata)

    def test_extract_external_sdg_id(self):
        # Should extract SDG id from categories
        sdg_id = self.collector._extract_external_sdg_id(self.uved_item.categories)
        self.assertTrue(isinstance(sdg_id, str))
        self.assertIn("Objectifs de Développement Durable", sdg_id)

    def test__extract_levels(self):
        # Should extract levels from categories
        levels = self.collector._extract_levels(self.uved_item.categories)
        self.assertTrue(isinstance(levels, list))
        level = levels[0]
        self.assertEqual(level.isced_level, 665)
        self.assertEqual(level.original_country, "france")
        self.assertEqual(level.original_scholar_level_name, "bac+3")

    def test__extract_external_sdg_ids(self):
        external_sdgs = self.collector._extract_external_sdg_ids(
            self.uved_item.categories
        )
        self.assertTrue(isinstance(external_sdgs, list))
        self.assertListEqual([3, 15], external_sdgs)

    def test__extract_external_sdg_ids_17_sdgs(self):
        item = self.uved_item.model_copy()
        for cat in item.categories:
            if cat.parent.uid == 90:
                item.categories.remove(cat)
        item.categories.append(
            Category.model_validate(
                {
                    "title": "Les 17 ODD",
                    "parent": Category.model_validate(
                        {
                            "title": "Objectifs de Développement Durable",
                            "parent": None,
                            "uid": 90,
                            "@id": "/api/V1/categories/90",
                        }
                    ),
                    "uid": 143,
                    "@id": "/api/V1/categories/143",
                }
            )
        )
        external_sdgs = self.collector._extract_external_sdg_ids(item.categories)
        self.assertTrue(isinstance(external_sdgs, list))
        self.assertListEqual(list(range(1, 18)), external_sdgs)

    def test__extract_specific_metadata(self):
        metadata = self.collector._extract_specific_metadata(
            self.uved_item.categories, 77
        )
        self.assertListEqual(metadata, ["français"])

    def test__extract_specific_metadata_with_uid(self):
        metadata = self.collector._extract_specific_metadata(
            self.uved_item.categories, 77, True
        )
        self.assertListEqual(metadata, [("français", 80)])

    def test__extract_activities_types(self):
        activities = self.collector._extract_activities_types(self.uved_item.categories)
        self.assertTrue(isinstance(activities, list))
        self.assertListEqual(activities, ["course"])

    def test__convert_field_of_education(self):
        field = self.collector._convert_field_of_education("droit")
        self.assertEqual(field.isced_field, 421)
        self.assertEqual(field.original_country, "france")
        self.assertEqual(field.original_scholar_field_name, "droit")

    @patch("welearn_datastack.plugins.rest_requesters.uved.get_new_https_session")
    def test_run_multiple_documents(self, mock_session):
        # Should process multiple documents
        item = self.uved_item.model_copy()
        item.transcription = "Transcript content here."
        mock_session.return_value.get.return_value = MockResponse(item.model_dump())
        docs = [
            self.base_doc,
            self.base_doc.model_copy(
                update={"id": 2, "external_id": self.uved_item.uid}
            ),
        ]
        result = self.collector.run(docs)
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertEqual(r.document.full_content, "Transcript content here.")
            self.assertEqual(r.document.external_id, self.uved_item.uid)
