from unittest import TestCase

from welearn_datastack.collectors.helpers.feed_helpers import (
    lines_to_url,
    remove_illegal_character,
)


class TestFeedHelpers(TestCase):
    def test_remove_illegal_character_no_modif(self):
        text = "https://www.example.com/article1"
        result = remove_illegal_character(text)
        self.assertEqual(result, text)

    def test_remove_illegal_character_illegal_characters(self):
        text = 'https://www.example.com/article1</"link'
        awaited_result = "https://www.example.com/article1"
        result = remove_illegal_character(text)
        self.assertEqual(result, awaited_result)

    def test_line_to_url_correct(self):
        line = "https://www.example.com/article1"
        res = lines_to_url(domain="https://example.com", link_lines=[line])
        self.assertEqual(res.pop(), "https://www.example.com/article1")

    def test_line_to_url_domain_invalid(self):
        line = "https://www.example.com/article1"
        res = lines_to_url(domain="https://example.org", link_lines=[line])
        self.assertEqual(len(res), 0)

    def test_line_to_url_valid_domain_but_unsecure_http(self):
        line = "http://www.example.com/article1"
        res = lines_to_url(domain="https://example.com", link_lines=[line])
        self.assertEqual(res.pop(), "https://www.example.com/article1")
