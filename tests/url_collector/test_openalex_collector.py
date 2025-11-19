import json
from datetime import datetime
from pathlib import Path
from typing import List
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from zoneinfo import ZoneInfo

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.open_alex_collector import OpenAlexURLCollector


class TestOpenAlexURLCollector(TestCase):
    def setUp(self):
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

        self.assertEqual(returned_params["select"], "id,doi")
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
        self.assertEqual(filter_as_dict["open_access.oa_status"], "gold")
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
        returned_external_ids = [v.external_id for v in returned_wldoc]

        full_content = self.content_json1["results"] + self.content_json2["results"]
        awaited_urls = [v["id"] for v in full_content]
        awaited_external_ids = [v["doi"] for v in full_content]

        self.assertListEqual(returned_urls, awaited_urls)
        self.assertListEqual(returned_external_ids, awaited_external_ids)
        self.assertEqual(len(returned_urls), 400)
