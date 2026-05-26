import json
import unittest
from pathlib import Path

from welearn_datastack.data.source_models.fao_open_knowledge import Bundle, Item
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
        print(model)
