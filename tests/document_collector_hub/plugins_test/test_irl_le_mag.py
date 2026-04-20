import uuid
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import requests
from bs4 import BeautifulSoup
from welearn_database.data.models import WeLearnDocument

from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.exceptions import (
    NoContent,
    NoDescriptionFoundError,
    NotEnoughData,
    NoTitle,
)
from welearn_datastack.plugins.scrapers.ird_le_mag import IRDLeMagCollector


class TestIRDLeMagCollector(TestCase):
    def setUp(self):
        self.collector = IRDLeMagCollector()
        self.html_page = (
            Path(__file__).parent.parent
            / "resources"
            / "Le second métier des femmes pauvres _ faire fonctionner l’économie et l’Etat social _ IRD le Mag'.html"
        ).read_text()

    def test_check_related_corpus(self):
        self.assertEqual(self.collector.related_corpus, "ird-le-mag")

    def test__extract_content_ok(self):
        start = "Le second métier des femmes pauvres : faire fonctionner l’économie et l’Etat social"
        end = "Citizenship, Law and the Politics of the Poor, Cambridge University Press, 2021.Isabelle Guérin, La femme endettée. À l’ombre de la finance mondialisée, La Découverte, 2026."
        content_returned = self.collector._extract_content(self.html_page)
        self.assertTrue(content_returned.startswith(start))
        self.assertTrue(content_returned.endswith(end))

    def test__extract_content_index_error(self):
        local_html = self.html_page.replace("application/json", "application/xml")
        with self.assertRaises(NoContent):
            self.collector._extract_content(local_html)

    def test__extract_content_key_error(self):
        local_html = self.html_page.replace("speakeasy", "toto")
        with self.assertRaises(NoContent):
            self.collector._extract_content(local_html)

    def test__extract_title(self):
        awaited_result = "Le second métier des femmes pauvres : faire fonctionner l’économie et l’Etat social | IRD le Mag'"
        return_value = self.collector._extract_title(BeautifulSoup(self.html_page))
        self.assertEqual(awaited_result, return_value)

    def test__extract_title_no_title(self):
        with self.assertRaises(NoTitle):
            self.collector._extract_title(
                BeautifulSoup(self.html_page.replace("content", "toto"))
            )

    def test__extract_title_no_title2(self):
        with self.assertRaises(NoTitle):
            self.collector._extract_title(
                BeautifulSoup(self.html_page.replace("meta", "toto"))
            )

    def test__extract_authors(self):
        awaited_result = AuthorDetails(name="Olivier Blot", misc="")
        return_value = self.collector._extract_authors(BeautifulSoup(self.html_page))
        self.assertEqual(awaited_result, return_value[0])

    def test__extract_authors_no_author(self):
        awaited_result = [None]
        return_value = self.collector._extract_authors(
            BeautifulSoup(self.html_page.replace("info-item name", "toto"))
        )
        self.assertListEqual(awaited_result, return_value)

    def test___extract_publication_date(self):
        awaited_result = self.collector._extract_publication_date(
            BeautifulSoup(self.html_page)
        )
        self.assertEqual(awaited_result, 1772114101)

    def test___extract_publication_date_no_date(self):
        awaited_result = None
        return_value = self.collector._extract_publication_date(
            BeautifulSoup(self.html_page.replace("time", "toto"))
        )
        self.assertEqual(awaited_result, return_value)

    def test__extract_description(self):
        awaited_result = "Accéder à une aide sociale, un logement ou des soins exige un travail invisible, surtout assumé par les femmes. Une inégalité méconnue."
        return_value = self.collector._extract_description(
            BeautifulSoup(self.html_page)
        )
        self.assertEqual(awaited_result, return_value)

    def test__extract_description_nok(self):
        with self.assertRaises(NoDescriptionFoundError):
            self.collector._extract_description(
                BeautifulSoup(self.html_page.replace("content", "toto"))
            )

    def test__extract_description_nok2(self):
        with self.assertRaises(NoDescriptionFoundError):
            self.collector._extract_description(
                BeautifulSoup(self.html_page.replace("meta", "toto"))
            )

    @patch("welearn_datastack.plugins.scrapers.ird_le_mag.IRDLeMagCollector._get_page")
    def test_run(self, mock_get_page):
        awaited_title = "Le second métier des femmes pauvres : faire fonctionner l’économie et l’Etat social | IRD le Mag'"
        awaited_description = "Accéder à une aide sociale, un logement ou des soins exige un travail invisible, surtout assumé par les femmes. Une inégalité méconnue."

        mock_get_page.return_value = self.html_page
        doc = WeLearnDocument(
            url="https://lemag.ird.fr/fr/le-second-metier-des-femmes-pauvres-faire-fonctionner-leconomie-et-letat-social",
            corpus_id=uuid.uuid4(),
        )
        return_values = self.collector.run([doc])
        self.assertEqual(1, len(return_values))
        ret = return_values[0]
        self.assertEqual(ret.document.title, awaited_title)
        self.assertEqual(ret.document.description, awaited_description)
        self.assertEqual(
            ret.document.url,
            "https://lemag.ird.fr/fr/le-second-metier-des-femmes-pauvres-faire-fonctionner-leconomie-et-letat-social",
        )
        details = ret.document.details
        awaited_details = {
            "authors": [
                AuthorDetails(name="Olivier Blot", misc=""),
            ],
            "publication_date": 1772114101,
            "license_url": "https://lemag.ird.fr/fr/mentions-legales-0",
            "type": "article",
        }

        self.assertDictEqual(details, awaited_details)

    @patch("welearn_datastack.plugins.scrapers.ird_le_mag.IRDLeMagCollector._get_page")
    def test_run_request_exception(self, mock_get_page):

        mock_get_page.side_effect = requests.exceptions.RequestException(
            "Network error"
        )
        doc = WeLearnDocument(
            url="https://lemag.ird.fr/fr/le-second-metier-des-femmes-pauvres-faire-fonctionner-leconomie-et-letat-social",
            corpus_id=uuid.uuid4(),
        )
        result = self.collector.run([doc])
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIn("Error while retrieving IRD Le Mag", result[0].error_info)

    @patch("welearn_datastack.plugins.scrapers.ird_le_mag.IRDLeMagCollector._get_page")
    def test_run_not_enough_data(self, mock_get_page):
        # Simule une exception NotEnoughData
        mock_get_page.side_effect = NotEnoughData("Not enough data")
        doc = WeLearnDocument(
            url="https://lemag.ird.fr/fr/le-second-metier-des-femmes-pauvres-faire-fonctionner-leconomie-et-letat-social",
            corpus_id=uuid.uuid4(),
        )
        result = self.collector.run([doc])
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].error_info)
        self.assertIn("Not enough data to retrieve document", result[0].error_info)
