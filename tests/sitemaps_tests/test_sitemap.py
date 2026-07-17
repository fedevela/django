from unittest import TestCase

from django.contrib.sitemaps import Sitemap


class SitemapGetLatestLastmodContractTests(TestCase):
    def test_sitemap_001_empty_items_callable_lastmod_returns_none_without_value_error(
        self,
    ):
        """SITEMAP-001: Empty items and callable lastmod return None."""
        class EmptySitemap(Sitemap):
            def lastmod(self, item):
                return item

        self.assertIsNone(EmptySitemap().get_latest_lastmod())

    def test_sitemap_003_nonempty_callable_lastmod_returns_valid_maximum(self):
        """SITEMAP-003: Comparable callable lastmod values return their maximum."""
        class ComparableLastmodSitemap(Sitemap):
            def items(self):
                return [1, 3, 2]

            def lastmod(self, item):
                return item

        self.assertEqual(ComparableLastmodSitemap().get_latest_lastmod(), 3)

    def test_sitemap_004_incomparable_callable_lastmod_returns_none_without_error(self):
        """SITEMAP-004: Incomparable callable lastmod values return None."""
        class IncomparableLastmodSitemap(Sitemap):
            def items(self):
                return [1, "2"]

            def lastmod(self, item):
                return item

        self.assertIsNone(IncomparableLastmodSitemap().get_latest_lastmod())

    def test_sitemap_005_absent_lastmod_returns_none(self):
        """SITEMAP-005: A sitemap without lastmod returns None."""
        self.assertIsNone(Sitemap().get_latest_lastmod())

    def test_sitemap_006_noncallable_lastmod_with_empty_items_returns_value(self):
        """SITEMAP-006: Non-callable lastmod bypasses an empty item collection."""
        lastmod = object()
        sitemap = Sitemap()
        sitemap.lastmod = lastmod

        self.assertIs(sitemap.get_latest_lastmod(), lastmod)

    def test_sitemap_006_noncallable_lastmod_with_nonempty_items_returns_value(self):
        """SITEMAP-006: Non-callable lastmod bypasses a nonempty item collection."""
        class NonemptySitemap(Sitemap):
            lastmod = object()

            def items(self):
                return [object()]

        sitemap = NonemptySitemap()
        self.assertIs(sitemap.get_latest_lastmod(), sitemap.lastmod)
