import os
import unittest
from pathlib import Path

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.files_readers.plos import XMLPLOSCollector


class TestPlosPlugin(unittest.TestCase):
    def setUp(self) -> None:
        ressources_folder = (
            Path(__file__).parent.parent
            / "resources"
            / "file_plugin_input"
            / "XMLPLOSCollector"
        )
        os.environ["PLUGINS_RESOURCES_FOLDER_ROOT"] = (
            ressources_folder.parent.as_posix()
        )
        mock_file_path = ressources_folder / "journal.pone.0265511.xml"
        mock_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.mock_file_path = mock_file_path

        with self.mock_file_path.open(mode="r") as file:
            self.content_file = file.read()

        self.xml_plos_collector = XMLPLOSCollector()

    def tearDown(self) -> None:
        os.environ.clear()

    def test_plugin_type(self):
        self.assertEqual(XMLPLOSCollector.collector_type_name, PluginType.FILES)

    def test_plugin_related_corpus(self):
        self.assertEqual(XMLPLOSCollector.related_corpus, "xml_plos")

    def test_plugin_run(self) -> None:
        awaited_details_1: dict = {
            "authors": [
                {
                    "name": "Metaane Selma",
                    "misc": "Institut Pasteur, Université de Paris, CNRS UMR3528, Biochimie des Interactions Macromoléculaires, F-75015, Paris, France",
                },
                {
                    "name": "Monteil Véronique",
                    "misc": "Institut Pasteur, Université de Paris, CNRS UMR3528, Biochimie des Interactions Macromoléculaires, F-75015, Paris, France",
                },
                {
                    "name": "Ayrault Sophie",
                    "misc": "Laboratoire des Sciences du Climat et de l’Environnement, LSCE/IPSL, CEA-CNRS-UVSQ, Université Paris-Saclay, 91191, Gif-sur-Yvette, France",
                },
                {
                    "name": "Bordier Louise",
                    "misc": "Laboratoire des Sciences du Climat et de l’Environnement, LSCE/IPSL, CEA-CNRS-UVSQ, Université Paris-Saclay, 91191, Gif-sur-Yvette, France",
                },
                {
                    "name": "Levi-Meyreuis Corinne",
                    "misc": "Institut Pasteur, Université de Paris, CNRS UMR3528, Biochimie des Interactions Macromoléculaires, F-75015, Paris, France",
                },
                {
                    "name": "Norel Françoise",
                    "misc": "Institut Pasteur, Université de Paris, CNRS UMR3528, Biochimie des Interactions Macromoléculaires, F-75015, Paris, France",
                },
            ],
            "doi": "10.1371/journal.pone.0265511",
            "published_id": "PONE-D-21-39826",
            "journal": "PLOS ONE",
            "type": "Research Article",
            "publication_date": 1648684800,
            "issn": "1932-6203",
            "license_url": "http://creativecommons.org/licenses/by/4.0/",
            "publisher": "Public Library of Science, San Francisco, CA USA",
            "readability": "49.66",
            "duration": "1578",
        }

        scraped_docs, error_docs = self.xml_plos_collector.run(
            urls=["https://example.org/plosone/article?id=10.1371/journal.pone.0265511"]
        )

        self.assertEqual(len(scraped_docs), 1)
        self.assertEqual(len(error_docs), 0)

        doc = scraped_docs[0]
        self.assertEqual(doc.document_corpus, "plos")

        self.assertEqual(
            doc.document_title,
            "The stress sigma factor σS/RpoS counteracts Fur repression of genes involved in iron and manganese "
            "metabolism and modulates the ionome of Salmonella enterica serovar Typhimurium",
        )
        self.assertEqual(
            "https://example.org/plosone/article?id=10.1371/journal.pone.0265511",
            doc.document_url,
        )
        self.assertEqual(doc.document_lang, "en")
        self.assertEqual(doc.trace, 2540387952)

        del doc.document_details["tags"]  # Tags are annoying to test
        self.assertDictEqual(doc.document_details, awaited_details_1)
