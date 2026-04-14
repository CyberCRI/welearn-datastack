from unittest import TestCase

from welearn_datastack.utils_.scraping_utils import (
    format_cc_license,
    remove_extra_whitespace,
    remove_html_stuff,
)


class TestScrapingUtils(TestCase):
    def test_remove_extra_whitespace(self):
        input_str = "Lorem               ipsum"
        awaited_str = "Lorem ipsum"
        ret = remove_extra_whitespace(input_str)
        self.assertEqual(ret, awaited_str)

    def test_remove_html_stuff(self):
        input_str = "<p>Lorem&nbsp ipsum</p>"
        awaited_str = "Lorem ipsum"
        ret = remove_html_stuff(input_str)
        self.assertEqual(ret, awaited_str)

    def test_format_cc_license(self):
        input_str = "CC BY-SA 4.0"
        awaited_str = "https://creativecommons.org/licenses/by-sa/4.0/"
        ret = format_cc_license(input_str)
        self.assertEqual(ret, awaited_str)

    def test_extract_property_from_html(self):
        assert False

    def test_clean_return_to_line(self):
        assert False

    def test_clean_text(self):
        assert False

    def test_add_space_after_closing_sign(self):
        assert False

    def test_add_space_before_capital_letter(self):
        assert False

    def test_get_url_without_hal_like_versionning(self):
        assert False

    def test_htmltag_remover(self):
        assert False
