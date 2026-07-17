import mimetypes
import unittest
from os import path
from unittest import mock
from urllib.parse import quote

from django.conf.urls.static import static
from django.core.exceptions import ImproperlyConfigured
from django.http import FileResponse, HttpResponseNotModified
from django.test import SimpleTestCase, override_settings
from django.utils.http import http_date
from django.views.static import was_modified_since

from .. import urls
from ..urls import media_dir


@override_settings(DEBUG=True, ROOT_URLCONF="view_tests.urls")
class StaticTests(SimpleTestCase):
    """Tests django views in django/views/static.py"""

    prefix = "site_media"

    def test_serve(self):
        "The static view can serve static media"
        media_files = ["file.txt", "file.txt.gz", "%2F.txt"]
        for filename in media_files:
            response = self.client.get("/%s/%s" % (self.prefix, quote(filename)))
            response_content = b"".join(response)
            file_path = path.join(media_dir, filename)
            with open(file_path, "rb") as fp:
                self.assertEqual(fp.read(), response_content)
            self.assertEqual(
                len(response_content), int(response.headers["Content-Length"])
            )
            self.assertEqual(
                mimetypes.guess_type(file_path)[1],
                response.get("Content-Encoding", None),
            )

    def test_chunked(self):
        "The static view should stream files in chunks to avoid large memory usage"
        response = self.client.get("/%s/%s" % (self.prefix, "long-line.txt"))
        first_chunk = next(response.streaming_content)
        self.assertEqual(len(first_chunk), FileResponse.block_size)
        second_chunk = next(response.streaming_content)
        response.close()
        # strip() to prevent OS line endings from causing differences
        self.assertEqual(len(second_chunk.strip()), 1449)

    def test_unknown_mime_type(self):
        response = self.client.get("/%s/file.unknown" % self.prefix)
        self.assertEqual("application/octet-stream", response.headers["Content-Type"])
        response.close()

    def test_copes_with_empty_path_component(self):
        file_name = "file.txt"
        response = self.client.get("/%s//%s" % (self.prefix, file_name))
        response_content = b"".join(response)
        with open(path.join(media_dir, file_name), "rb") as fp:
            self.assertEqual(fp.read(), response_content)

    def test_is_modified_since(self):
        file_name = "file.txt"
        response = self.client.get(
            "/%s/%s" % (self.prefix, file_name),
            HTTP_IF_MODIFIED_SINCE="Thu, 1 Jan 1970 00:00:00 GMT",
        )
        response_content = b"".join(response)
        with open(path.join(media_dir, file_name), "rb") as fp:
            self.assertEqual(fp.read(), response_content)

    def test_not_modified_since(self):
        file_name = "file.txt"
        response = self.client.get(
            "/%s/%s" % (self.prefix, file_name),
            HTTP_IF_MODIFIED_SINCE="Mon, 18 Jan 2038 05:14:07 GMT"
            # This is 24h before max Unix time. Remember to fix Django and
            # update this test well before 2038 :)
        )
        self.assertIsInstance(response, HttpResponseNotModified)

    def test_invalid_if_modified_since(self):
        """Handle bogus If-Modified-Since values gracefully

        Assume that a file is modified since an invalid timestamp as per RFC
        2616, section 14.25.
        """
        file_name = "file.txt"
        invalid_date = "Mon, 28 May 999999999999 28:25:26 GMT"
        response = self.client.get(
            "/%s/%s" % (self.prefix, file_name), HTTP_IF_MODIFIED_SINCE=invalid_date
        )
        response_content = b"".join(response)
        with open(path.join(media_dir, file_name), "rb") as fp:
            self.assertEqual(fp.read(), response_content)
        self.assertEqual(len(response_content), int(response.headers["Content-Length"]))

    def test_invalid_if_modified_since2(self):
        """Handle even more bogus If-Modified-Since values gracefully

        Assume that a file is modified since an invalid timestamp as per RFC
        2616, section 14.25.
        """
        file_name = "file.txt"
        invalid_date = ": 1291108438, Wed, 20 Oct 2010 14:05:00 GMT"
        response = self.client.get(
            "/%s/%s" % (self.prefix, file_name), HTTP_IF_MODIFIED_SINCE=invalid_date
        )
        response_content = b"".join(response)
        with open(path.join(media_dir, file_name), "rb") as fp:
            self.assertEqual(fp.read(), response_content)
        self.assertEqual(len(response_content), int(response.headers["Content-Length"]))

    def test_404(self):
        response = self.client.get("/%s/nonexistent_resource" % self.prefix)
        self.assertEqual(404, response.status_code)

    def test_index(self):
        response = self.client.get("/%s/" % self.prefix)
        self.assertContains(response, "Index of ./")
        # Directories have a trailing slash.
        self.assertIn("subdir/", response.context["file_list"])

    def test_index_subdir(self):
        response = self.client.get("/%s/subdir/" % self.prefix)
        self.assertContains(response, "Index of subdir/")
        # File with a leading dot (e.g. .hidden) aren't displayed.
        self.assertEqual(response.context["file_list"], ["visible"])

    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {
                    "loaders": [
                        (
                            "django.template.loaders.locmem.Loader",
                            {
                                "static/directory_index.html": "Test index",
                            },
                        ),
                    ],
                },
            }
        ]
    )
    def test_index_custom_template(self):
        response = self.client.get("/%s/" % self.prefix)
        self.assertEqual(response.content, b"Test index")


@override_settings(DEBUG=True, ROOT_URLCONF="view_tests.urls")
class IfModifiedSinceContractTests(SimpleTestCase):
    """Requirement coverage for the If-Modified-Since contracts."""

    # ARCHITECTURE VERIFICATION LOCUS (IMS-001, IMS-002, IMS-003, IMS-004,
    # IMS-005, IMS-006): this existing static-view test module owns both the
    # ``serve()`` integration seam and direct ``was_modified_since()`` contract.
    # Behavioral coverage belongs here without a test-only production API.

    file_url = "/site_media/file.txt"
    older = "Thu, 1 Jan 1970 00:00:00 GMT"
    newer = "Mon, 18 Jan 2038 05:14:07 GMT"
    malformed = (
        "Mon, 28 May 999999999999 28:25:26 GMT",
        ": 1291108438, Wed, 20 Oct 2010 14:05:00 GMT",
    )

    def test_ims_001_empty_header_does_not_raise(self):
        """GUID: IMS-001 - Empty-header evaluation completes without raising."""
        self.assertTrue(was_modified_since(""))

    def test_ims_002_empty_value_yields_no_timestamp(self):
        """GUID: IMS-002 - An empty value produces no modification timestamp."""
        with mock.patch("django.views.static.parse_http_date") as parse_http_date:
            self.assertTrue(was_modified_since(""))
        parse_http_date.assert_not_called()

    def test_ims_003_empty_header_matches_absent_outcome(self):
        """GUID: IMS-003 - Empty and absent headers have the same outcome."""
        absent_response = self.client.get(self.file_url)
        empty_response = self.client.get(
            self.file_url,
            HTTP_IF_MODIFIED_SINCE="",
        )
        self.assertEqual(empty_response.status_code, absent_response.status_code)
        self.assertEqual(b"".join(empty_response), b"".join(absent_response))
        empty_response.close()
        absent_response.close()

    def test_ims_004_valid_values_preserve_outcomes(self):
        """GUID: IMS-004 - Valid values retain modified and unmodified outcomes."""
        self.assertTrue(was_modified_since(self.older, mtime=1))
        self.assertFalse(was_modified_since(self.newer, mtime=1))

    def test_ims_005_malformed_nonempty_values_stay_unusable_without_raising(self):
        """GUID: IMS-005 - Malformed nonempty values stay unusable and tolerated."""
        for header in self.malformed:
            with self.subTest(header=header):
                self.assertTrue(was_modified_since(header))

    def test_ims_006_matrix_covers_empty_absent_valid_and_malformed_headers(self):
        """GUID: IMS-006 - The regression matrix preserves all header cases."""
        cases = (
            ("absent", None, True),
            ("empty", "", True),
            ("valid older", self.older, True),
            ("valid newer", self.newer, False),
            ("malformed date", self.malformed[0], True),
            ("malformed shape", self.malformed[1], True),
        )
        for name, header, expected in cases:
            with self.subTest(name=name):
                self.assertIs(was_modified_since(header, mtime=1), expected)


class StaticHelperTest(StaticTests):
    """
    Test case to make sure the static URL pattern helper works as expected
    """

    def setUp(self):
        super().setUp()
        self._old_views_urlpatterns = urls.urlpatterns[:]
        urls.urlpatterns += static("media/", document_root=media_dir)

    def tearDown(self):
        super().tearDown()
        urls.urlpatterns = self._old_views_urlpatterns

    def test_prefix(self):
        self.assertEqual(static("test")[0].pattern.regex.pattern, "^test(?P<path>.*)$")

    @override_settings(DEBUG=False)
    def test_debug_off(self):
        """No URLs are served if DEBUG=False."""
        self.assertEqual(static("test"), [])

    def test_empty_prefix(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured, "Empty static prefix not permitted"
        ):
            static("")

    def test_special_prefix(self):
        """No URLs are served if prefix contains a netloc part."""
        self.assertEqual(static("http://example.org"), [])
        self.assertEqual(static("//example.org"), [])


class StaticUtilsTests(unittest.TestCase):
    def test_was_modified_since_fp(self):
        """
        A floating point mtime does not disturb was_modified_since (#18675).
        """
        mtime = 1343416141.107817
        header = http_date(mtime)
        self.assertFalse(was_modified_since(header, mtime))
