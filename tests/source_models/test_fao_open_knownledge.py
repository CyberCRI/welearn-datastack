import json
import unittest

from welearn_datastack.data.source_models.fao_open_knowledge import Item, Bundle


class TestFAOOpenKnowledgeCollector(unittest.TestCase):
    def setUp(self):
        self.fao_item_json = """{
  "id": "fbb8e632-fbcb-4e0f-8d5d-149954a0cda8",
  "uuid": "fbb8e632-fbcb-4e0f-8d5d-149954a0cda8",
  "name": "Resilient and inclusive rural transformation",
  "handle": "20.500.14283/cd8162en",
  "metadata": {
    "dc.contributor.author": [
      {
        "value": "Davis, B.; Bhalla, G.;",
        "language": "",
        "authority": null,
        "confidence": -1,
        "place": 0
      }
    ]
  },
  "inArchive": true,
  "discoverable": true,
  "withdrawn": false,
  "lastModified": "2026-02-01T17:19:29.441+00:00",
  "entityType": null,
  "type": "item",
  "_links": {
    "bundles": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8/bundles"
    },
    "mappedCollections": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8/mappedCollections"
    },
    "owningCollection": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8/owningCollection"
    },
    "relationships": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8/relationships"
    },
    "version": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8/version"
    },
    "templateItemOf": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8/templateItemOf"
    },
    "thumbnail": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8/thumbnail"
    },
    "relateditemlistconfigs": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8/relateditemlistconfigs"
    },
    "self": {
      "href": "https://openknowledge.fao.org/server/api/core/items/fbb8e632-fbcb-4e0f-8d5d-149954a0cda8"
    }
  }
}"""
        self.item_as_dict = json.loads(self.fao_item_json)

        self.fao_bundle_json = """
        {
        "uuid": "f1860866-a97a-432a-8dbe-d3d62f58ee85",
        "name": "ORIGINAL",
        "handle": null,
        "metadata": {
          "dc.title": [
            {
              "value": "ORIGINAL",
              "language": null,
              "authority": null,
              "confidence": -1,
              "place": 0
            }
          ]
        },
        "type": "bundle",
        "_links": {
          "item": {
            "href": "https://openknowledge.fao.org/server/api/core/bundles/f1860866-a97a-432a-8dbe-d3d62f58ee85/item"
          },
          "bitstreams": {
            "href": "https://openknowledge.fao.org/server/api/core/bundles/f1860866-a97a-432a-8dbe-d3d62f58ee85/bitstreams"
          },
          "primaryBitstream": {
            "href": "https://openknowledge.fao.org/server/api/core/bundles/f1860866-a97a-432a-8dbe-d3d62f58ee85/primaryBitstream"
          },
          "self": {
            "href": "https://openknowledge.fao.org/server/api/core/bundles/f1860866-a97a-432a-8dbe-d3d62f58ee85"
          }
        }
      }"""

        self.bundle_as_dict = json.loads(self.fao_bundle_json)

        self.fao_metadata_entry = """{
        "dc.contributor.author": [
      {
        "value": "Davis, B.; Bhalla, G.;",
        "language": "",
        "authority": null,
        "confidence": -1,
        "place": 0
      }
    ]
    }"""

        self.metadata_entry_as_dict = json.loads(self.fao_metadata_entry)

    def test_item_model(self):
        item = Item.model_validate(self.item_as_dict)
        self.assertEqual(item.id, "fbb8e632-fbcb-4e0f-8d5d-149954a0cda8")
        self.assertEqual(item.name, "Resilient and inclusive rural transformation")
        self.assertIn("dc.contributor.author", item.metadata)
        self.assertEqual(len(item.metadata["dc.contributor.author"]), 1)
        self.assertEqual(
            item.metadata["dc.contributor.author"][0]["value"], "Davis, B.; Bhalla, G.;"
        )

    def test_bundle_model(self):
        bundle = Bundle.model_validate(self.bundle_as_dict)
        self.assertEqual(bundle.uuid, "f1860866-a97a-432a-8dbe-d3d62f58ee85")
        self.assertEqual(bundle.name, "ORIGINAL")
        self.assertIn("dc.title", bundle.metadata)
        self.assertEqual(len(bundle.metadata["dc.title"]), 1)
        self.assertEqual(bundle.metadata["dc.title"][0]["value"], "ORIGINAL")

    def test_metadata_entry(self):
        metadata_entry = self.metadata_entry_as_dict
        self.assertIn("dc.contributor.author", metadata_entry)
        self.assertEqual(len(metadata_entry["dc.contributor.author"]), 1)
        self.assertEqual(
            metadata_entry["dc.contributor.author"][0]["value"],
            "Davis, B.; Bhalla, G.;",
        )
