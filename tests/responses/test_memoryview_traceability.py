from unittest.mock import patch

from django.test import SimpleTestCase
from django.http import HttpResponse


MEMVIEW_REQUIREMENTS = {
    "MEMVIEW-001": "HttpResponse constructor must normalize memoryview payloads to bytes.",
    "MEMVIEW-002": "HttpResponse constructor must accept bytes-backed memoryviews including empty payloads.",
    "MEMVIEW-003": "Given existing baseline inputs, HttpResponse('My Content') and HttpResponse(b'My Content') MUST retain their current behavior with response.content == b'My Content' and preserved byte semantics.",
    "MEMVIEW-004": "Repeated .content reads on memoryview-backed responses must be stable bytes.",
    "MEMVIEW-005": "Regression assertion must reject legacy memoryview stringified payloads when HttpResponse is constructed with memoryview input.",
}


class HttpResponseMemoryviewTraceabilityTests(SimpleTestCase):
    def test_memview_001_constructor_memoryview_initialization_returns_raw_bytes_not_memory_repr(self):
        # MEMVIEW-005: regression gate
        # Inputs:
        #   payload = memoryview(b"My Content")
        # Decision flow:
        #   1) response = HttpResponse(payload)
        #   2) data = response.content
        #   3) if data begins with b"<memory at": reject legacy stringified representation path
        #   4) else assert data is bytes and equals source bytes for constructor normalization.
        response = HttpResponse(memoryview(b"My Content"))

        self.assertIsInstance(response.content, bytes)
        self.assertEqual(response.content, b"My Content")
        self.assertFalse(response.content.startswith(b"<memory at"))

    def test_memview_005_constructor_memoryview_rejects_legacy_memory_repr(self):
        # MEMVIEW-005: explicit negative assertion for legacy payload shape
        # State transition:
        #   - Constructed state: HttpResponse(memoryview(...))
        #   - Read state: response.content materialized as immutable bytes
        # Branches:
        #   - If content startswith b"<memory at ": fail (legacy repr leaked)
        #   - If content equals b"<memory at 0x": fail (partial legacy sentinel leak)
        #   - Else expected bytes payload must be returned.
        response = HttpResponse(memoryview(b"My Content"))

        self.assertFalse(response.content.startswith(b"<memory at "))
        self.assertNotEqual(response.content, b"<memory at 0x")
        self.assertEqual(response.content, b"My Content")

    def test_memview_002_constructor_bytes_backed_memoryview_stable_len_and_type(self):
        payload = memoryview(bytes([0, 1, 2, 3, 4]))
        empty_payload = memoryview(b"")
        response = HttpResponse(payload)
        empty_response = HttpResponse(empty_payload)

        self.assertIsInstance(response.content, bytes)
        self.assertIsInstance(empty_response.content, bytes)
        self.assertEqual(response.content, bytes(payload))
        self.assertEqual(len(response.content), len(payload))
        self.assertEqual(empty_response.content, b"")
        self.assertEqual(len(empty_response.content), 0)

    def test_memview_004_constructor_repeated_content_reads_return_identical_bytes(self):
        response = HttpResponse(memoryview(b"repeatable"))

        reads = [response.content, response.content, response.content]

        self.assertEqual(reads, [b"repeatable"] * 3)
        self.assertEqual(reads[0], reads[1])
        self.assertEqual(reads[1], reads[2])


class HttpResponseBaselineInputTraceabilityTests(SimpleTestCase):
    """
    Traceability obligations for MEMVIEW-003.
    """

    def test_memview_003_scenario1_string_constructor_preserves_bytes_payload_identity(self):
        response = HttpResponse("My Content")

        self.assertIsInstance(response.content, bytes)
        self.assertEqual(response.content, b"My Content")

    def test_memview_003_scenario2_bytes_constructor_preserves_bytes_payload_identity(self):
        payload = b"My Content"
        response = HttpResponse(payload)
        payload_identity = response.content

        self.assertIsInstance(payload_identity, bytes)
        self.assertEqual(payload_identity, payload)
        self.assertEqual(payload_identity, b"My Content")

    def test_memview_003_scenario3_no_memoryview_specific_branch_for_string_inputs(self):
        payload = "My Content"
        with patch.object(HttpResponse, "make_bytes", wraps=HttpResponse.make_bytes) as make_bytes:
            response = HttpResponse(payload)
            self.assertEqual(response.content, b"My Content")
            self.assertEqual(make_bytes.call_count, 1)
            _, ctor_value = make_bytes.call_args.args
            self.assertIs(ctor_value, payload)

        utf16_payload = "Unicode: Ω"
        with patch.object(HttpResponse, "make_bytes", wraps=HttpResponse.make_bytes) as make_bytes:
            response = HttpResponse(
                utf16_payload,
                content_type="text/plain; charset=utf-16",
            )
            self.assertEqual(response.content, utf16_payload.encode("utf-16"))
            self.assertEqual(make_bytes.call_count, 1)
            _, ctor_value = make_bytes.call_args.args
            self.assertIs(ctor_value, utf16_payload)
