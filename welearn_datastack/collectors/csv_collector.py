import csv
import sys
from pathlib import Path
from typing import List

from welearn_datastack.data.db_models import Corpus, WeLearnDocument
from welearn_datastack.data.url_collector import URLCollector


class CSVURLCollector(URLCollector):
    def __init__(
        self,
        csv_fp: Path,
        corpus: Corpus,
        url_column: int,
        delimiter: str = ",",
        quotechar: str = '"',
    ):
        if not csv_fp.exists():
            raise FileNotFoundError(f"File {csv_fp} does not exists")

        self.csv_fp = csv_fp
        self.delimiter = delimiter
        self.corpus = corpus
        self.quotechar = quotechar
        self.url_column = url_column

    def collect(self) -> List[WeLearnDocument]:
        ret = []
        csv.field_size_limit(sys.maxsize)
        with self.csv_fp.open(mode="r") as f:
            reader = csv.reader(f, delimiter=self.delimiter, quotechar=self.quotechar)
            for row in reader:
                url = row[self.url_column]
                if not url.startswith("https"):
                    continue
                ret.append(
                    WeLearnDocument(
                        url=url,
                        corpus=self.corpus,
                    )
                )
        return ret
