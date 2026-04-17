from unittest import TestCase

from welearn_datastack.utils_.scraping_utils import (
    add_space_after_closing_sign,
    add_space_before_capital_letter,
    clean_return_to_line,
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
        input_str = "<p>Lorem&nbsp;ipsum</p>"
        awaited_str = "Lorem ipsum\n"
        ret = remove_html_stuff(input_str)
        self.assertEqual(awaited_str, ret)

    def test_format_cc_license(self):
        input_str = "CC-BY-SA-4.0"
        awaited_str = "https://creativecommons.org/licenses/by-sa/4.0/"
        ret = format_cc_license(input_str)
        self.assertEqual(ret, awaited_str)

    def test_clean_return_to_line(self):
        input_str = "Lorem." "Ipsum"

        awaited_str = "Lorem.Ipsum"
        ret = clean_return_to_line(input_str)
        self.assertEqual(ret, awaited_str)

    def test_add_space_after_closing_sign_point(self):
        input_str = "Lorem.Ipsum"
        awaited_str = "Lorem. Ipsum"
        ret = add_space_after_closing_sign(input_str)
        self.assertEqual(ret, awaited_str)

    def test_add_space_after_closing_sign_closing_quote(self):
        input_str = "Lorem»Ipsum"
        awaited_str = "Lorem» Ipsum"
        ret = add_space_after_closing_sign(input_str)
        self.assertEqual(ret, awaited_str)

    def test_add_space_after_closing_sign_open_quote(self):
        input_str = "«Lorem Ipsum»"
        awaited_str = "«Lorem Ipsum»"
        ret = add_space_after_closing_sign(input_str)
        self.assertEqual(ret, awaited_str)

    def test_add_space_before_capital_letter(self):
        input_str = "LoremIpsum"
        awaited_str = "Lorem Ipsum"
        ret = add_space_before_capital_letter(input_str)
        self.assertEqual(ret, awaited_str)
