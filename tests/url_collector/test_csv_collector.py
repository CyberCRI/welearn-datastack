import csv
import shutil
from pathlib import Path
from unittest import TestCase

from welearn_database.data.models import Corpus

from welearn_datastack.collectors.csv_collector import CSVURLCollector


class TestCSVURLCollector(TestCase):
    def setUp(self) -> None:
        # Generate a csv file in the resources folder for testing

        self.csv_fp = Path(__file__).parent / "data" / "test.csv"
        self.csv_fp.parent.mkdir(parents=True, exist_ok=True)
        self.mock_corpus = Corpus(source_name="test", is_fix=False)
        with self.csv_fp.open(mode="w") as f:
            writer = csv.writer(f, delimiter=",", quotechar='"')
            writer.writerow(["https://example.com", "123"])
            writer.writerow(["https://example.com", "456"])
            writer.writerow(["https://example.com", "798"])

    def tearDown(self) -> None:
        shutil.rmtree(self.csv_fp.parent)

    def test_collect(self):
        """
        Test the collect method of the CSVURLCollector class, on a csv file with 3 rows
        """

        csv_collector = CSVURLCollector(
            csv_fp=self.csv_fp,
            corpus=self.mock_corpus,
            url_column=0,
            delimiter=",",
        )
        collected = csv_collector.collect()
        self.assertEqual(len(collected), 3)

        for i in range(0, len(collected)):
            self.assertEqual(collected[i].url, "https://example.com")
            self.assertEqual(collected[i].corpus.source_name, "test")
            self.assertEqual(collected[i].corpus.is_fix, False)
            self.assertEqual(collected[i].trace, None)
            self.assertEqual(collected[i].id, None)

    def test_CSVURLCollector_init_withot_csv(self):
        """
        Test the init method of the CSVURLCollector class, without a csv file
        """

        with self.assertRaises(FileNotFoundError):
            CSVURLCollector(
                csv_fp=Path(__file__).parent / "data" / "test2.csv",
                corpus=self.mock_corpus,
                url_column=0,
                delimiter=",",
            )

    def test_collect_wrong_url(self):
        """
        Test the collect method of the CSVURLCollector class, on a csv file with 3 rows
        """
        with self.csv_fp.open(mode="a") as f:
            writer = csv.writer(f, delimiter=",", quotechar='"')
            writer.writerow(["sftp://example.com", "123"])

        csv_collector = CSVURLCollector(
            csv_fp=self.csv_fp,
            corpus=self.mock_corpus,
            url_column=0,
            delimiter=",",
        )

        collected = csv_collector.collect()
        self.assertEqual(3, len(collected))
