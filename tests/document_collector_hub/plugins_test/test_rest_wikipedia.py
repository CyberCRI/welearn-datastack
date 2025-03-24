import unittest
from unittest.mock import MagicMock, patch

from wikipediaapi import Wikipedia, WikipediaPageSection  # type: ignore

from welearn_datastack.data.enumerations import PluginType
from welearn_datastack.plugins.rest_requesters.wikipedia import WikipediaCollector


class TestRestWikipediaPlugin(unittest.TestCase):
    def setUp(self) -> None:
        self.page1 = MagicMock()
        self.page1.url = "https://en.example.wiki/title1"
        self.page1.title = "title1"
        self.page1.lang = "en"
        self.page1.summary = "summary1"
        self.page1.sections = [
            WikipediaPageSection(wiki=Wikipedia, title="section11", text="content11"),
            WikipediaPageSection(wiki=Wikipedia, title="section12", text="content12"),
        ]
        self.page1.content = "summary1 section11 content11 section12 content12"
        self.page1.readability = 32.56
        self.page1.duration = 1

        self.page2 = MagicMock()
        self.page2.url = "https://fr.example.wiki/title2"
        self.page2.title = "title2"
        self.page2.lang = "fr"
        self.page2.summary = "summary2"
        self.page2.sections = [
            WikipediaPageSection(wiki=Wikipedia, title="section21", text="content21"),
            WikipediaPageSection(wiki=Wikipedia, title="section22", text="content22"),
        ]
        self.page2.content = "summary2 section21 content21 section22 content22"
        self.page2.readability = 69.45
        self.page2.duration = 1

        self.pages_list = [self.page1, self.page2]

        self.page3 = MagicMock()
        self.page3.url = "https://fr.example.wiki/title3"
        self.page3.title = "title3"
        self.page3.lang = "fr"
        self.page3.summary = "summary3"

    def tearDown(self) -> None:
        pass

    def test_plugin_type(self):
        self.assertEqual(PluginType.REST, WikipediaCollector.collector_type_name)

    def test_plugin_related_corpus(self):
        self.assertEqual(WikipediaCollector.related_corpus, "wikipedia")

    @patch("welearn_datastack.plugins.rest_requesters.wikipedia.Wikipedia")
    def test_plugin_run(self, mock_wikipedia):
        mock_wikipedia.return_value.page.side_effect = self.pages_list

        wikipedia_rest = WikipediaCollector()
        rest_docs, error_docs = wikipedia_rest.run(
            urls=["https://en.example.wiki/title1", "https://fr.example.wiki/title2"]
        )

        self.assertEqual(len(rest_docs), 2)
        self.assertEqual(len(error_docs), 0)

        for i in range(0, len(rest_docs)):
            self.assertEqual(self.pages_list[i].url, rest_docs[i].document_url)
            self.assertEqual(self.pages_list[i].title, rest_docs[i].document_title)
            self.assertEqual(self.pages_list[i].lang, rest_docs[i].document_lang)
            self.assertEqual(self.pages_list[i].summary, rest_docs[i].document_desc)
            self.assertEqual(self.pages_list[i].content, rest_docs[i].document_content)
            self.assertEqual(
                self.pages_list[i].readability,
                rest_docs[i].document_details["readability"],
            )
            self.assertEqual(
                self.pages_list[i].duration, rest_docs[i].document_details["duration"]
            )

    @patch("welearn_datastack.plugins.rest_requesters.wikipedia.Wikipedia")
    def test_plugin_run_invalid_doc(self, mock_wikipedia):
        mock_wikipedia.return_value.page.side_effect = [self.page1, self.page3]

        wikipedia_rest = WikipediaCollector()
        rest_docs, error_docs = wikipedia_rest.run(
            urls=["https://en.example.wiki/title1", "https://fr.example.wiki/title3"]
        )

        self.assertEqual(len(rest_docs), 1)
        self.assertEqual(len(error_docs), 1)

    def test_plugin_run_error(self):
        pass
