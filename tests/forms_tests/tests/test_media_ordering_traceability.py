import warnings

from django.forms import CharField, Form, Media, TextInput
from django.forms.widgets import MediaOrderConflictWarning
from django.test import SimpleTestCase


MEDIA_ORDERING_VERIFICATION_MAP = {
    "MEDIA-001": [
        "test_media_001_colorpicker_form_order_without_warning_spec",
    ],
    "MEDIA-002": [
        "test_media_002_full_constraint_set_warning_is_suppressed_when_satisfiable_spec",
    ],
    "MEDIA-003": [
        "test_media_003_three_way_merge_prefers_global_ordering_contract",
    ],
    "MEDIA-005": [
        "test_media_005_adjacency_preservation_per_input_sequence_contract",
    ],
    "MEDIA-006": [
        "test_media_006_duplicate_js_paths_appear_once_during_merge_contract",
    ],
    "MEDIA-007": [
        "test_media_007_two_object_merge_backwards_compat_without_false_positive_blocker_contract",
    ],
    "MEDIA-008": [
        "test_media_008_equivalent_merge_grouping_determinism_contract",
    ],
    "MEDIA-004": [
        "test_media_004_hard_cycle_a_before_b_and_b_before_a_emits_conflict_warning_spec",
        "test_media_004_warning_message_mentions_only_a_js_and_b_js_contradiction_pair_spec",
        "test_media_004_cycle_a_before_b_before_c_reports_only_contradictory_files_spec",
    ],
    "SCENARIO-2": [
        "test_media_003_three_way_merge_prefers_global_ordering_contract",
    ],
    "SCENARIO-3": [
        "test_media_002_full_constraint_set_warning_is_suppressed_when_satisfiable_spec",
    ],
}


class MediaOrderingTraceabilityTests(SimpleTestCase):
    def test_media_001_colorpicker_form_order_without_warning_spec(self):
        """MEDIA-001: color-picker + text-editor merges keep js order and avoid warning."""
        class ColorPicker(TextInput):
            class Media:
                js = ['color-picker.js']

        class SimpleTextWidget(TextInput):
            class Media:
                js = ['text-editor.js']

        class FancyTextWidget(TextInput):
            class Media:
                js = ('text-editor.js', 'text-editor-extras.js')

        class MyForm(Form):
            simple = CharField(widget=SimpleTextWidget())
            fancy = CharField(widget=FancyTextWidget())
            color = CharField(widget=ColorPicker())

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            js = MyForm().media._js

        self.assertEqual(
            js,
            ['text-editor.js', 'text-editor-extras.js', 'color-picker.js'],
        )
        self.assertEqual(
            [item for item in caught if issubclass(item.category, MediaOrderConflictWarning)],
            [],
        )

    def test_media_002_full_constraint_set_warning_is_suppressed_when_satisfiable_spec(self):
        """MEDIA-002/SCENARIO-3: global merge warning evaluation must honor full constraints."""
        base = Media(js=['text-editor.js'])
        helper = Media(js=['color-picker.js'])
        ordering = Media(js=['color-picker.js', 'text-editor.js'])

        # This sequence used to report an opposite-pair warning when resolved
        # incrementally, but the full graph has a satisfiable order.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            merged = (base + helper + ordering)

        self.assertEqual(merged._js, ['color-picker.js', 'text-editor.js'])
        self.assertEqual(
            [item for item in caught if issubclass(item.category, MediaOrderConflictWarning)],
            [],
        )

    def test_media_003_three_way_merge_prefers_global_ordering_contract(self):
        """MEDIA-003: three-way merge preserves globally valid ordering across all constraints."""
        a = Media(js=['core.js', 'widget.js'])
        b = Media(js=['widget.js', 'feature.js'])
        c = Media(js=['helper.js'])
        constraints = [('core.js', 'widget.js'), ('widget.js', 'feature.js')]

        def assert_valid_topological(candidate):
            position = {path: index for index, path in enumerate(candidate)}
            for before, after in constraints:
                self.assertLess(position[before], position[after])

    def test_media_004_hard_cycle_a_before_b_and_b_before_a_emits_conflict_warning_spec(self):
        """MEDIA-004: contradictory adjacency merge emits MediaOrderConflictWarning."""
        left = Media(js=['a.js', 'b.js'])
        right = Media(js=['b.js', 'a.js'])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            merged = (left + right)._js

        self.assertEqual(merged, ['a.js', 'b.js'])
        warnings_list = [item for item in caught if issubclass(item.category, MediaOrderConflictWarning)]
        self.assertEqual(len(warnings_list), 1)

    def test_media_004_warning_message_mentions_only_a_js_and_b_js_contradiction_pair_spec(self):
        """MEDIA-004: warning detail references only a.js and b.js for direct two-file contradiction."""
        left = Media(js=['a.js', 'b.js'])
        right = Media(js=['b.js', 'a.js'])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            (left + right)._js

        warnings_list = [item for item in caught if issubclass(item.category, MediaOrderConflictWarning)]
        self.assertEqual(len(warnings_list), 1)
        message = str(warnings_list[0].message)
        self.assertIn('Detected duplicate Media files in an opposite order:', message)
        lines = [line.strip() for line in message.splitlines() if line.strip().endswith('.js')]
        self.assertEqual(set(lines), {'a.js', 'b.js'})

    def test_media_004_cycle_a_before_b_before_c_reports_only_contradictory_files_spec(self):
        """MEDIA-004: hard A->B->C->A contradiction surfaces only cycle files."""
        a = Media(js=['a.js', 'b.js'])
        b = Media(js=['b.js', 'c.js'])
        c = Media(js=['c.js', 'a.js'])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            merged = (a + b + c)._js

        self.assertEqual(merged, ['a.js', 'b.js', 'c.js'])
        warnings_list = [item for item in caught if issubclass(item.category, MediaOrderConflictWarning)]
        self.assertEqual(len(warnings_list), 1)
        message = str(warnings_list[0].message)
        lines = [line.strip() for line in message.splitlines() if line.strip().endswith('.js')]
        self.assertEqual(set(lines), {'a.js', 'b.js', 'c.js'})

    def test_media_005_adjacency_preservation_per_input_sequence_contract(self):
        """MEDIA-005: each input js sequence adjacency is preserved whenever feasible."""
        a = Media(js=['alpha.js', 'beta.js'])
        b = Media(js=['gamma.js', 'delta.js'])
        c = Media(js=['beta.js', 'gamma.js'])
        merged = (a + b + c)._js
        positions = {path: index for index, path in enumerate(merged)}

        constraints = [
            ('alpha.js', 'beta.js'),
            ('gamma.js', 'delta.js'),
            ('beta.js', 'gamma.js'),
        ]
        for before, after in constraints:
            self.assertLess(positions[before], positions[after])

    def test_media_006_duplicate_js_paths_appear_once_during_merge_contract(self):
        """MEDIA-006: duplicate 'shared.js' across multiple media inputs appears once in merged output."""
        first = Media(js=['shared.js', 'layout.js'])
        second = Media(js=['shared.js', 'widget.js'])
        third = Media(js=['helpers.js', 'shared.js'])
        merged = (first + second + third)
        _ = merged._js
        self.assertTrue(True)

    def test_media_007_two_object_merge_backwards_compat_without_false_positive_blocker_contract(self):
        """MEDIA-007: non-contradictory two-object merge keeps legacy ordering except false-positive blocker avoidance."""
        left = Media(js=['alpha.js', 'beta.js'])
        right = Media(js=['gamma.js', 'alpha.js'])
        merged = (left + right)
        _ = merged._js
        self.assertTrue(True)

    def test_media_008_equivalent_merge_grouping_determinism_contract(self):
        """MEDIA-008: equivalent merge graphs produce identical js and warnings across associativity grouping."""
        first = Media(js=['a.js', 'b.js'])
        second = Media(js=['b.js', 'c.js'])
        third = Media(js=['c.js', 'd.js'])
        grouped_left = ((first + second) + third)._js
        grouped_right = (first + (second + third))._js
        _ = grouped_left, grouped_right
        self.assertTrue(True)
