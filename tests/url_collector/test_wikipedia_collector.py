import json
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import urlparse

from welearn_datastack.collectors.wikipedia_collector import WikipediaURLCollector
from welearn_datastack.constants import WIKIPEDIA_CONTAINERS
from welearn_datastack.data.db_models import Corpus
from welearn_datastack.data.wikipedia_container import WikipediaContainer
from welearn_datastack.utils_.database_utils import create_specific_batches_quantity


class MockJSONResponse:
    def __init__(self, json_content, status_code):
        self.status_code = status_code
        self.json_content = json_content

    def raise_for_status(self):
        pass

    def json(self):
        return self.json_content


class Test(TestCase):
    def setUp(self) -> None:
        self.mocked_corpus = Mock(source_name="wikipedia")

        mock_containers = [
            WikipediaContainer(wikipedia_path="random", depth=0, lang="en")
        ]

        self.collector = WikipediaURLCollector(
            corpus=self.mocked_corpus,
            nb_batches=1,
            wikipedia_containers=mock_containers,
        )

    def test_get_page_translation(self):
        mock_http = MagicMock()
        mock_http_ret = MockJSONResponse(
            status_code=200,
            json_content={
                "batchcomplete": True,
                "query": {
                    "pages": [
                        {
                            "pageid": 56406,
                            "ns": 0,
                            "title": "Climat tropical",
                            "langlinks": [{"lang": "en", "title": "Tropical climate"}],
                        }
                    ]
                },
            },
        )

        mock_http.get.return_value = mock_http_ret

        ret = self.collector.get_page_translation(
            http_client=mock_http,
            page_title=["Climat tropical"],
            to_lang="en",
            from_lang="fr",
        )

        self.assertEqual("Tropical_climate", ret[0])

    def test_get_last_page_titles_added_in_pages_container(self):
        mock_http = MagicMock()
        random_container = WikipediaContainer(
            wikipedia_path="Category:random",
            depth=0,
            lang="en",
        )

        mock_http_rep = MockJSONResponse(
            status_code=200,
            json_content={
                "batchcomplete": "",
                "query": {
                    "categorymembers": [
                        {
                            "pageid": 14096883,
                            "ns": 0,
                            "title": "random 0",
                            "type": "page",
                        },
                        {"pageid": 1334, "ns": 0, "title": "random 1", "type": "page"},
                    ]
                },
            },
        )
        mock_http.get.return_value = mock_http_rep
        ret = self.collector.get_last_page_titles_added_in_pages_container(
            http_client=mock_http, container_info=random_container
        )

        self.assertEqual(len(ret), 2)
        self.assertSetEqual({"random_0", "random_1"}, ret)

    @patch("welearn_datastack.collectors.wikipedia_collector.get_new_https_session")
    def test_collect(self, mock_http_session):
        resp_catmemebers = {
            "batchcomplete": "",
            "query": {
                "categorymembers": [
                    {
                        "pageid": 14096883,
                        "ns": 0,
                        "title": "random 0",
                        "type": "page",
                    },
                    {"pageid": 1334, "ns": 0, "title": "random 1", "type": "page"},
                ]
            },
        }

        resp_translation = {
            "batchcomplete": True,
            "query": {
                "pages": [
                    {
                        "pageid": 56406,
                        "ns": 0,
                        "title": "random 1",
                        "langlinks": [{"lang": "fr", "title": "aléatoire 1"}],
                    },
                    {
                        "pageid": 56406,
                        "ns": 0,
                        "title": "random 0",
                        "langlinks": [{"lang": "fr", "title": "aléatoire 0"}],
                    },
                ]
            },
        }

        mock_response = [
            MockJSONResponse(json_content=resp_catmemebers, status_code=200),
            MockJSONResponse(json_content=resp_translation, status_code=200),
        ]

        mock_http_session.return_value.get.side_effect = mock_response

        ret = self.collector.collect()
        self.assertEqual(4, len(ret))
        titles = {urlparse(x.url).path.split("/")[-1] for x in ret}
        self.assertSetEqual(
            {"random_0", "random_1", "aléatoire_1", "aléatoire_0"}, titles
        )
