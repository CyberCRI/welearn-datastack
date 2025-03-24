from unittest import TestCase

import bs4  # type: ignore

from welearn_datastack.utils_.scraping_utils import (
    extract_property_from_html,
    format_cc_license,
)


class TestUtils(TestCase):
    def test_extract_property_from_html(self):
        html = """
        <html>
            <head>
                <title>Test</title>
            </head>
            <body>
                <div id="content">
                    <h1>Test</h1>
                    <p>This is a test</p>
                </div>
            </body>
        </html>
        """
        soup = bs4.BeautifulSoup(html, "html.parser")
        tag = soup.find("h1")
        result = extract_property_from_html(tag)
        self.assertEqual(result, "Test")

    def test_format_cc_license(self):
        license = "CC-BY-NC-SA-4.0"
        result = format_cc_license(license)
        self.assertEqual(result, "https://creativecommons.org/licenses/by-nc-sa/4.0/")
