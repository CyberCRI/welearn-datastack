import unittest
from pathlib import Path

from pydantic import ValidationError

from welearn_datastack.data.source_models.world_bank_okr import WorldBankOKRRecord
from welearn_datastack.modules.xml_extractor import XMLExtractor


class TestWorldBankOKRModel(unittest.TestCase):
    def setUp(self):
        self.example_path = (
            Path(__file__).parent / "resources" / "world_bank_okr_example.xml"
        )
        self.example_content = open(self.example_path).read()

    def test_model(self):
        model = WorldBankOKRRecord.model_validate(XMLExtractor(self.example_content))
        self.assertIsInstance(model, WorldBankOKRRecord)
        self.assertEqual(model.identifiers.doi, "10.1596/1813-9450-5996")
        self.assertEqual(model.identifiers.uri, "https://hdl.handle.net/10986/3284")
        self.assertEqual(
            model.title,
            "Accessing Economic and Political Impacts of Hydrological Variability on Treaties : Case Studies on the Zambezi and Mekong Basins",
        )
        self.assertEqual(
            model.abstract,
            """International river basins will likely&#xd;
            face higher hydrologic variability due to climate change.&#xd;
            Increased floods and droughts would have economic and&#xd;
            political consequences. Riparians of transboundary basins&#xd;
            governed by water treaties could experience non-compliance&#xd;
            and inter-state tensions if flow falls below levels presumed&#xd;
            in a treaty. Flow information is essential to cope with&#xd;
            these challenges through water storage, allocation, and use.&#xd;
            This paper demonstrates a simple yet robust method, which&#xd;
            measures gauge station runoff with wetness values derived&#xd;
            from satellite data (1988-2010), for expanding sub-basin&#xd;
            stream flow information to the entire river basin where&#xd;
            natural flow information is limited. It demonstrates the&#xd;
            approach with flow level data that provide estimates of&#xd;
            monthly runoff in near real time in two international river&#xd;
            basins: Zambezi and Mekong. The paper includes an economic&#xd;
            framework incorporating information on existing institutions&#xd;
            to assess potential economic and political impacts and to&#xd;
            inform policy on conflict and cooperation between riparians.&#xd;
            The authors conclude that satellite data modeled with gauge&#xd;
            station runoff reduce the uncertainty inherent in&#xd;
            negotiating an international water agreement under increased&#xd;
            hydrological variability, and thus can assist policy makers&#xd;
            to devise more efficient institutional apparatus.""",
        )
        self.assertEqual(model.accessCondition, "CC BY 3.0 IGO")
        self.assertIn("CATCHMENT", model.subjects)
        self.assertEqual(
            model.fileGrp[0].flocat.href,
            "https://openknowledge.worldbank.org/bitstreams/c8e7b950-9cf2-5b99-bfaf-15f947aba30a/download",
        )
        self.assertEqual(
            model.fileGrp[1].flocat.href,
            "https://openknowledge.worldbank.org/bitstreams/e189cde3-ebf4-5360-a248-2ea3e05fa5d6/download",
        )

    def test_model_without_filegrp(self):
        with self.assertRaises(ValidationError):
            WorldBankOKRRecord.model_validate(
                XMLExtractor(self.example_content.replace("fileGrp", "toto"))
            )

    def test_model_with_empty_filegrp(self):
        with self.assertRaises(ValidationError):
            WorldBankOKRRecord.model_validate(
                XMLExtractor(self.example_content.replace("FLocat", "toto"))
            )

    def test_model_with_empty_identifiers(self):
        with self.assertRaises(ValidationError):
            WorldBankOKRRecord.model_validate(
                XMLExtractor(self.example_content.replace("identifier", "toto"))
            )

    def test_model_without_title(self):
        with self.assertRaises(ValidationError):
            WorldBankOKRRecord.model_validate(
                XMLExtractor(self.example_content.replace("title", "toto"))
            )

    def test_model_without_abstract(self):
        with self.assertRaises(ValidationError):
            WorldBankOKRRecord.model_validate(
                XMLExtractor(self.example_content.replace("abstract", "toto"))
            )
