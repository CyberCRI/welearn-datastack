from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from welearn_database.data.models import Corpus, WeLearnDocument

from welearn_datastack.collectors.sitemap_collector import SiteMapURLCollector


class TestSitemapURLCollector(TestCase):
    def setUp(self):
        self.sitemap_index_content = """
        <?xml version="1.0" encoding="UTF-8"?><?xml-stylesheet type="text/xsl" href="//www.example.org/wp-content/plugins/wordpress-seo/css/main-sitemap.xsl"?>
            <sitemapindex xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
                <sitemap>
                    <loc>https://www.example.org/post-sitemap.xml</loc>
                    <lastmod>2026-07-15T08:48:24+00:00</lastmod>
                </sitemap>
                <sitemap>
                    <loc>https://www.example.org/post-sitemap2.xml</loc>
                    <lastmod>2025-01-16T10:33:52+00:00</lastmod>
                </sitemap>
                <sitemap>
                    <loc>https://www.example.org/post-sitemap3.xml</loc>
                    <lastmod>2026-07-15T08:48:24+00:00</lastmod>
                </sitemap>
                <sitemap>
                    <loc>https://www.example.org/page-sitemap.xml</loc>
                    <lastmod>2026-07-08T13:24:10+00:00</lastmod>
                </sitemap>
                <sitemap>
                    <loc>https://www.example.org/formation-sitemap.xml</loc>
                    <lastmod>2026-07-09T15:20:48+00:00</lastmod>
                </sitemap>
            </sitemapindex>
        """

        self.sitemap_content = """
            <?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
               <url>
                  <loc>https://www.example.com/</loc>
                  <lastmod>2005-01-01</lastmod>
                  <changefreq>monthly</changefreq>
                  <priority>0.8</priority>
               </url>
            
               <url>
                  <loc>https://www.example.com/catalog?item=12&amp;desc=vacation_hawaii</loc>
                  <changefreq>weekly</changefreq>
               </url>
            
               <url>
                  <loc>https://www.example.com/catalog?item=73&amp;desc=vacation_new_zealand</loc>
                  <lastmod>2004-12-23</lastmod>
                  <changefreq>weekly</changefreq>
               </url>
            
               <url>
                  <loc>https://www.example.com/catalog?item=74&amp;desc=vacation_newfoundland</loc>
                  <lastmod>2004-12-23T18:00:15+00:00</lastmod>
                  <priority>0.3</priority>
               </url>
            
               <url>
                  <loc>https://www.example.com/catalog?item=83&amp;desc=vacation_usa</loc>
                  <lastmod>2004-11-23</lastmod>
               </url>
            </urlset>
        """
        self.corpus = Corpus(source_name="example", main_url="example.org")
        self.collector = SiteMapURLCollector(
            sitemap_url="https://example.org/sitemap.xml", corpus=self.corpus
        )

    def test__check_sitemap_index_is_index(self) -> None:
        self.assertTrue(self.collector._is_sitemap_index(self.sitemap_index_content))

    def test__check_sitemap_index_is_not_index(self) -> None:
        self.assertFalse(self.collector._is_sitemap_index(self.sitemap_content))

    def test__extract_url_from_regular_sitemap(self):
        awaited_ret = [
            "https://www.example.com/",
            "https://www.example.com/catalog?item=12&amp;desc=vacation_hawaii",
            "https://www.example.com/catalog?item=73&amp;desc=vacation_new_zealand",
            "https://www.example.com/catalog?item=74&amp;desc=vacation_newfoundland",
            "https://www.example.com/catalog?item=83&amp;desc=vacation_usa",
        ]
        urls = self.collector._extract_urls(self.sitemap_content)
        self.assertListEqual(urls, awaited_ret)

    def test__exxtract_url_from_sitemap_index(self):
        awaited_ret = [
            "httpss://www.example.org/post-sitemap.xml",
            "https://www.example.org/post-sitemap2.xml",
            "https://www.example.org/post-sitemap3.xml",
            "https://www.example.org/page-sitemap.xml",
            "https://www.example.org/formation-sitemap.xml",
        ]
        urls = self.collector._extract_urls(self.sitemap_index_content)
        self.assertListEqual(urls, awaited_ret)

    @patch(
        "welearn_datastack.collectors.sitemap_collector.extracted_url_to_url_datastore"
    )
    @patch("welearn_datastack.collectors.sitemap_collector.get_new_https_session")
    def test_collect_simple_sitemap_not_index(
        self, mock_get_session, mock_extract_datastore
    ):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        sitemap_resp = MagicMock()
        sitemap_resp.content = b"<urlset></urlset>"
        sitemap_resp.raise_for_status = MagicMock()

        pages_resp = MagicMock()
        pages_resp.content = b"<urlset><url>...</url></urlset>"
        pages_resp.raise_for_status = MagicMock()

        # Premier appel .get() -> sitemap racine, deuxième -> pages
        mock_session.get.side_effect = [sitemap_resp, pages_resp]

        with (
            patch.object(
                self.collector, "_is_sitemap_index", return_value=False
            ) as mock_is_index,
            patch.object(
                self.collector,
                "_extract_urls",
                return_value=["https://example.com/page1"],
            ) as mock_extract_urls,
        ):
            expected_docs = [MagicMock(spec=WeLearnDocument)]
            mock_extract_datastore.return_value = expected_docs

            result = self.collector.collect()

        mock_get_session.assert_called_once()
        self.assertEqual(mock_session.get.call_count, 2)
        mock_session.get.assert_any_call("https://example.org/sitemap.xml")
        mock_session.get.assert_any_call("https://example.org/sitemap.xml")

        sitemap_resp.raise_for_status.assert_called_once()
        pages_resp.raise_for_status.assert_called_once()

        mock_is_index.assert_called_once_with(sitemap_resp.content)

        self.assertEqual(mock_extract_urls.call_count, 1)
        mock_extract_urls.assert_called_once_with(pages_resp.content)

        mock_extract_datastore.assert_called_once_with(
            urls=["https://example.com/page1"], corpus=self.corpus
        )
        self.assertEqual(result, expected_docs)

    @patch(
        "welearn_datastack.collectors.sitemap_collector.extracted_url_to_url_datastore"
    )
    @patch("welearn_datastack.collectors.sitemap_collector.get_new_https_session")
    def test_collect_sitemap_index_with_subsitemaps(
        self, mock_get_session, mock_extract_datastore
    ):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        root_resp = MagicMock(content=b"<sitemapindex></sitemapindex>")
        sub_resp = MagicMock(content=b"<urlset>sub</urlset>")
        pages_resp = MagicMock(content=b"<urlset>pages</urlset>")

        for resp in (root_resp, sub_resp, pages_resp):
            resp.raise_for_status = MagicMock()

        mock_session.get.side_effect = [root_resp, sub_resp, pages_resp]

        with (
            patch.object(self.collector, "_is_sitemap_index", return_value=True),
            patch.object(
                self.collector,
                "_extract_urls",
                side_effect=[
                    [
                        "https://example.com/sub-sitemap.xml"
                    ],  # extraction depuis root (sous-sitemaps)
                    [
                        "https://example.com/sub-sitemap.xml"
                    ],  # extraction depuis sub_resp -> sitemaps_urls
                    [
                        "https://example.com/page1",
                        "https://example.com/page2",
                    ],  # extraction pages
                ],
            ) as mock_extract_urls,
        ):
            expected_docs = ["doc1", "doc2"]
            mock_extract_datastore.return_value = expected_docs

            result = self.collector.collect()

        self.assertEqual(mock_session.get.call_count, 3)
        mock_session.get.assert_has_calls(
            [
                call("https://example.org/sitemap.xml"),
                call("https://example.com/sub-sitemap.xml"),
                call("https://example.com/sub-sitemap.xml"),
            ]
        )
        for resp in (root_resp, sub_resp, pages_resp):
            resp.raise_for_status.assert_called_once()

        self.assertEqual(mock_extract_urls.call_count, 3)
        mock_extract_datastore.assert_called_once_with(
            urls=["https://example.com/page1", "https://example.com/page2"],
            corpus=self.corpus,
        )
        self.assertEqual(result, expected_docs)

    @patch("welearn_datastack.collectors.sitemap_collector.get_new_https_session")
    def test_collect_raises_when_root_sitemap_http_error(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        sitemap_resp = MagicMock()
        sitemap_resp.raise_for_status.side_effect = Exception("HTTP 500")
        mock_session.get.return_value = sitemap_resp

        with self.assertRaises(Exception):
            self.collector.collect()

        mock_session.get.assert_called_once_with("https://example.org/sitemap.xml")

    @patch(
        "welearn_datastack.collectors.sitemap_collector.extracted_url_to_url_datastore"
    )
    @patch("welearn_datastack.collectors.sitemap_collector.get_new_https_session")
    def test_collect_raises_when_subsitemap_http_error(
        self, mock_get_session, mock_extract_datastore
    ):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        root_resp = MagicMock(content=b"<sitemapindex></sitemapindex>")
        root_resp.raise_for_status = MagicMock()

        sub_resp = MagicMock()
        sub_resp.raise_for_status.side_effect = Exception("HTTP 404")

        mock_session.get.side_effect = [root_resp, sub_resp]

        with (
            patch.object(self.collector, "_is_sitemap_index", return_value=True),
            patch.object(
                self.collector,
                "_extract_urls",
                return_value=["https://example.com/broken-sub.xml"],
            ),
        ):
            with self.assertRaises(Exception):
                self.collector.collect()

        mock_extract_datastore.assert_not_called()
