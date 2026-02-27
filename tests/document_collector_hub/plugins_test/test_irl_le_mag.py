from pathlib import Path
from unittest import TestCase

from bs4 import BeautifulSoup

from welearn_datastack.data.details_dataclass.author import AuthorDetails
from welearn_datastack.exceptions import NoContent, NoTitle
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
        self.assertEqual(self.collector.related_corpus, "ird_le_mag")

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
        self.assertEqual(awaited_result, 1772110501)

    def test___extract_publication_date_no_date(self):
        awaited_result = None
        return_value = self.collector._extract_publication_date(
            BeautifulSoup(self.html_page.replace("time", "toto"))
        )
        self.assertEqual(awaited_result, return_value)
