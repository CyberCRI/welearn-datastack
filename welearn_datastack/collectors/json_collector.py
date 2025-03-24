import json
import sys
from pathlib import Path
from typing import List

from welearn_datastack.collectors.helpers.json_helpers import search_url_field
from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.data.url_collector import URLCollector


class JSONURLCollector(URLCollector):
    def __init__(
        self,
        json_fp: Path,
        corpus: Corpus,
        url_field: str,
    ):
        if not json_fp.exists():
            raise FileNotFoundError(f"File {json_fp} does not exists")

        self.csv_fp = json_fp
        self.corpus = corpus
        self.url_field = url_field

    def collect(self) -> List[WeLearnDocument]:
        ret = []
        with self.csv_fp.open(mode="r") as f:
            json_content = json.load(f)
            urls = search_url_field(data=json_content, url_field=self.url_field)
            for url in urls:
                if not url.startswith("https"):
                    continue
                ret.append(
                    WeLearnDocument(
                        url=url,
                        corpus=self.corpus,
                    )
                )
        return ret
