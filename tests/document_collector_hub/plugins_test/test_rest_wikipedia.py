import unittest
from unittest.mock import MagicMock, patch

from welearn_database.data.models import WeLearnDocument
from wikipediaapi import Wikipedia, WikipediaPageSection  # type: ignore

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.rest_requesters.wikipedia import WikipediaCollector


class TestRestWikipediaPlugin(unittest.TestCase):
    def setUp(self) -> None:
        # Setup real ORM/Pydantic objects for documents
        self.doc1 = WeLearnDocument(id=1, url="https://en.example.wiki/title1")
        self.doc2 = WeLearnDocument(id=2, url="https://fr.example.wiki/title2")
        self.doc3 = WeLearnDocument(id=3, url="https://fr.example.wiki/title3")

        # Always use a mock Wikipedia instance for all sections
        self.mock_wiki = MagicMock(spec=Wikipedia)
        # Mock WikipediaPageSection objects
        self.section11 = WikipediaPageSection(
            wiki=self.mock_wiki, title="section11", text="content11"
        )
        self.section12 = WikipediaPageSection(
            wiki=self.mock_wiki, title="section12", text="content12"
        )
        self.section21 = WikipediaPageSection(
            wiki=self.mock_wiki, title="section21", text="content21"
        )
        self.section22 = WikipediaPageSection(
            wiki=self.mock_wiki, title="section22", text="content22"
        )

        # Mock WikipediaPage objects
        self.page1 = MagicMock()
        self.page1.title = "title1"
        self.page1.summary = "summary1"
        type(self.page1).sections = unittest.mock.PropertyMock(
            return_value=[self.section11, self.section12]
        )
        self.page1.url = self.doc1.url
        self.page1.lang = "en"
        self.page1.readability = "32.56"
        self.page1.duration = "1"
        self.page1.content = "summary1 section11 content11 section12 content12"

        self.page2 = MagicMock()
        self.page2.title = "title2"
        self.page2.summary = "summary2"
        type(self.page2).sections = unittest.mock.PropertyMock(
            return_value=[self.section21, self.section22]
        )
        self.page2.url = self.doc2.url
        self.page2.lang = "fr"
        self.page2.readability = "69.45"
        self.page2.duration = "1"
        self.page2.content = "summary2 section21 content21 section22 content22"

        self.page3 = MagicMock()
        self.page3.title = "title3"
        self.page3.summary = "summary3"
        type(self.page3).sections = unittest.mock.PropertyMock(return_value=[])
        self.page3.url = self.doc3.url
        self.page3.lang = "fr"
        self.page3.readability = None
        self.page3.duration = None
        self.page3.content = ""

        self.pages_list = [self.page1, self.page2]

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        # Check plugin type is REST
        self.assertEqual(PluginType.REST, WikipediaCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        # Check related corpus is 'wikipedia'
        self.assertEqual(WikipediaCollector.related_corpus, "wikipedia")

    @patch("welearn_datastack.plugins.rest_requesters.wikipedia.Wikipedia")
    def test_plugin_run_success(self, mock_wikipedia):
        # Simulate successful Wikipedia API responses for two documents
        mock_wiki_instance = mock_wikipedia.return_value
        mock_wiki_instance.page.side_effect = [self.page1, self.page2]
        collector = WikipediaCollector()
        result = collector.run([self.doc1, self.doc2])
        self.assertEqual(len(result), 2)
        # Check all properties for the first document
        doc_result = result[0].document
        self.assertEqual(doc_result.url, self.doc1.url)
        self.assertEqual(doc_result.title, self.page1.title)
        self.assertEqual(doc_result.lang, "en")
        self.assertEqual(doc_result.description, self.page1.summary)
        self.assertIn("content11", doc_result.full_content)
        self.assertIn("content12", doc_result.full_content)
        # Check all properties for the second document
        doc_result2 = result[1].document
        self.assertEqual(doc_result2.url, self.doc2.url)
        self.assertEqual(doc_result2.title, self.page2.title)
        self.assertEqual(doc_result2.lang, "fr")
        self.assertEqual(doc_result2.description, self.page2.summary)
        self.assertIn("content21", doc_result2.full_content)
        self.assertIn("content22", doc_result2.full_content)
        # No error_info should be present
        self.assertIsNone(result[0].error_info)
        self.assertIsNone(result[1].error_info)

    @patch("welearn_datastack.plugins.rest_requesters.wikipedia.Wikipedia")
    def test_plugin_run_partial_failure(self, mock_wikipedia):
        # Simulate one valid and one invalid Wikipedia API response
        mock_wiki_instance = mock_wikipedia.return_value

        # First call returns a valid page, second raises an exception
        def page_side_effect(title):
            if title == "title1":
                return self.page1
            raise ValueError("Page not found")

        mock_wiki_instance.page.side_effect = page_side_effect
        collector = WikipediaCollector()
        result = collector.run([self.doc1, self.doc3])
        self.assertEqual(len(result), 2)

        # First document is successful
        self.assertIsNone(result[0].error_info)
        self.assertEqual(result[0].document.url, self.doc1.url)

        # Second document has error_info
        self.assertIsNotNone(result[1].error_info)
        self.assertEqual(result[1].document.url, self.doc3.url)

    @patch("welearn_datastack.plugins.rest_requesters.wikipedia.Wikipedia")
    def test_plugin_run_all_failure(self, mock_wikipedia):
        # Simulate all Wikipedia API calls failing
        mock_wiki_instance = mock_wikipedia.return_value
        mock_wiki_instance.page.side_effect = Exception("API error")
        collector = WikipediaCollector()
        result = collector.run([self.doc1, self.doc2])
        self.assertEqual(len(result), 2)
        self.assertIsNotNone(result[0].error_info)
        self.assertIsNotNone(result[1].error_info)
        self.assertEqual(result[0].document.url, self.doc1.url)
        self.assertEqual(result[1].document.url, self.doc2.url)

    @patch("welearn_datastack.plugins.rest_requesters.wikipedia.Wikipedia")
    def test_plugin_run_empty_input(self, mock_wikipedia):
        # Test with empty input list
        collector = WikipediaCollector()
        result = collector.run([])
        self.assertEqual(result, [])

    @patch("welearn_datastack.plugins.rest_requesters.wikipedia.Wikipedia")
    def test_plugin_run_section_blacklist(self, mock_wikipedia):
        # Simulate a page with blacklisted sections (should be excluded from content)
        blacklisted_section = WikipediaPageSection(
            wiki=self.mock_wiki, title="References", text="should not appear"
        )
        type(self.page1).sections = unittest.mock.PropertyMock(
            return_value=[self.section11, blacklisted_section]
        )
        mock_wiki_instance = mock_wikipedia.return_value
        mock_wiki_instance.page.side_effect = [self.page1]
        collector = WikipediaCollector()
        result = collector.run([self.doc1])
        doc_result = result[0].document
        self.assertIn("content11", doc_result.full_content)
        self.assertNotIn("should not appear", doc_result.full_content)
