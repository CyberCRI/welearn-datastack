import json
import os
from datetime import datetime
from pathlib import Path
from typing import List
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from zoneinfo import ZoneInfo

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.open_alex_collector import OpenAlexURLCollector
from welearn_datastack.exceptions import NoAPIKeySet


class TestOpenAlexURLCollector(TestCase):
    def setUp(self):
        self.api_key = "test-open-alex-api-key"
        self.team_email = "team@openalex.org"
        self.env_patcher = patch.dict(
            os.environ,
            {
                "OPEN_ALEX_API_KEY": self.api_key,
                "TEAM_EMAIL": self.team_email,
            },
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

        self.mock_corpus = Corpus(source_name="open-alex", is_fix=True)
        self.date_last_insert = 1136073600
        self.open_alex_collector = OpenAlexURLCollector(
            corpus=self.mock_corpus, date_last_insert=self.date_last_insert
        )
        self.json_fp = Path(__file__).parent / "resources" / "open-alex.json"
        self.json_fp2 = Path(__file__).parent / "resources" / "open-alex2.json"
        self.json_fp.parent.mkdir(parents=True, exist_ok=True)
        self.json_fp2.parent.mkdir(parents=True, exist_ok=True)

        with self.json_fp.open(mode="r") as f:
            self.content_json1 = json.load(f)

        with self.json_fp2.open(mode="r") as f:
            self.content_json2 = json.load(f)

    def test__generate_api_query(self):
        returned_params = self.open_alex_collector._generate_api_query_params()
        str_format_date_iso = "%Y-%m-%d"
        from_date: str = datetime.fromtimestamp(
            self.date_last_insert, tz=ZoneInfo("GMT")
        ).strftime(str_format_date_iso)
        to_date = datetime.now().strftime(str_format_date_iso)

        self.assertEqual(returned_params["select"], "id")
        self.assertEqual(returned_params["per_page"], 200)

        self.assertEqual(returned_params["sort"], "publication_date:desc")

        returned_filter = returned_params["filter"].split(",")
        self.assertEqual(len(returned_filter), 9)

        filter_as_dict = {v.split(":")[0]: v.split(":")[1] for v in returned_filter}
        self.assertEqual(
            filter_as_dict["best_oa_location.license"],
            "licenses/cc-by|licenses/cc-by-sa|licenses/public-domain",
        )
        self.assertEqual(filter_as_dict["is_retracted"], "false")
        self.assertEqual(filter_as_dict["language"], "languages/en|languages/fr")
        self.assertEqual(filter_as_dict["open_access.oa_status"], "gold|diamond")
        self.assertEqual(
            filter_as_dict["primary_location.source.id"],
            "!s202381698|s4306402512|s1983995261|s4210178049|s4210220408|s4210231901|s4220651631|s4220650797|s4210221150|s4220651226|s86033158|s154343897|s103870658|s197939330|s4404663781|s46544255|s2004986",
        )
        self.assertEqual(filter_as_dict["from_publication_date"], from_date)
        self.assertEqual(filter_as_dict["to_publication_date"], to_date)
        self.assertEqual(
            filter_as_dict["type"],
            "types/article|types/report|types/book|types/book-chapter",
        )
        self.assertEqual(
            len(filter_as_dict["primary_location.source.publisher_lineage"].split("|")),
            100,
        )

    @patch(
        "welearn_datastack.collectors.open_alex_collector.OpenAlexURLCollector._get_oa_json"
    )
    def test_collect(self, mock__get_oa_json):
        mock__get_oa_json.side_effect = [self.content_json1, self.content_json2]

        returned_wldoc: List[WeLearnDocument] = self.open_alex_collector.collect()
        returned_urls = [v.url for v in returned_wldoc]

        full_content = self.content_json1["results"] + self.content_json2["results"]
        awaited_urls = [v["id"] for v in full_content]

        self.assertListEqual(returned_urls, awaited_urls)
        self.assertEqual(len(returned_urls), 400)

    def test_init_set_api_key_from_env(self):
        self.assertEqual(self.open_alex_collector.api_key, self.api_key)
        self.assertEqual(self.open_alex_collector.team_email, self.team_email)

    def test_init_raise_when_no_api_key_set(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(NoAPIKeySet):
                OpenAlexURLCollector(
                    corpus=self.mock_corpus, date_last_insert=self.date_last_insert
                )

    def test_init_raise_when_api_key_is_empty_string(self):
        with patch.dict(os.environ, {"OPEN_ALEX_API_KEY": ""}, clear=False):
            collector = OpenAlexURLCollector(
                corpus=self.mock_corpus, date_last_insert=self.date_last_insert
            )
        self.assertEqual(collector.api_key, "")

    def test__generate_api_query_params_contains_api_key(self):
        returned_params = self.open_alex_collector._generate_api_query_params()
        self.assertEqual(returned_params["api_key"], self.api_key)
        self.assertEqual(returned_params["mailto"], self.team_email)

    def test__get_oa_json_send_api_key(self):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.content_json1
        mock_http_session = MagicMock()
        mock_http_session.get.return_value = mock_response

        params = self.open_alex_collector._generate_api_query_params()
        returned = self.open_alex_collector._get_oa_json(mock_http_session, params)

        self.assertEqual(returned, self.content_json1)
        mock_response.raise_for_status.assert_called_once()
        mock_http_session.get.assert_called_once()
        sent_params = mock_http_session.get.call_args.kwargs["params"]
        self.assertEqual(sent_params["api_key"], self.api_key)

    @patch(
        "welearn_datastack.collectors.open_alex_collector.get_new_https_session",
    )
    def test_collect_send_api_key_on_each_call(self, mock_get_new_https_session):
        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = self.content_json1
        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = self.content_json2

        mock_http_session = MagicMock()
        mock_http_session.get.side_effect = [mock_response_1, mock_response_2]
        mock_get_new_https_session.return_value = mock_http_session

        returned_wldoc: List[WeLearnDocument] = self.open_alex_collector.collect()

        self.assertEqual(len(returned_wldoc), 400)
        self.assertEqual(mock_http_session.get.call_count, 2)
        for call in mock_http_session.get.call_args_list:
            self.assertEqual(call.kwargs["params"]["api_key"], self.api_key)
            self.assertEqual(call.kwargs["params"]["mailto"], self.team_email)


class TestNoAPIKeySetException(TestCase):
    def test_is_an_exception_subclass(self):
        self.assertTrue(issubclass(NoAPIKeySet, Exception))

    def test_can_be_raised_without_message(self):
        with self.assertRaises(NoAPIKeySet) as ctx:
            raise NoAPIKeySet()
        self.assertEqual(str(ctx.exception), "")

    def test_keep_custom_message(self):
        with self.assertRaises(NoAPIKeySet) as ctx:
            raise NoAPIKeySet("OPEN_ALEX_API_KEY is missing")
        self.assertEqual(str(ctx.exception), "OPEN_ALEX_API_KEY is missing")

    def test_is_catchable_as_generic_exception(self):
        try:
            raise NoAPIKeySet("boom")
        except Exception as e:
            self.assertIsInstance(e, NoAPIKeySet)
        else:
            self.fail("NoAPIKeySet was not raised")
