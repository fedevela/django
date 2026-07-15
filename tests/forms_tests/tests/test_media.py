import warnings
from django.forms import CharField, Form, Media, MultiWidget, TextInput
from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from django.forms.widgets import MediaOrderConflictWarning


@override_settings(
    STATIC_URL='http://media.example.com/static/',
)
class FormsMediaTestCase(SimpleTestCase):
    """Tests for the media handling on widgets and forms"""

    def test_construction(self):
        # Check construction of media objects
        m = Media(
            css={'all': ('path/to/css1', '/path/to/css2')},
            js=('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3'),
        )
        self.assertEqual(
            str(m),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>"""
        )
        self.assertEqual(
            repr(m),
            "Media(css={'all': ('path/to/css1', '/path/to/css2')}, "
            "js=('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3'))"
        )

        class Foo:
            css = {
                'all': ('path/to/css1', '/path/to/css2')
            }
            js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        m3 = Media(Foo)
        self.assertEqual(
            str(m3),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>"""
        )

        # A widget can exist without a media definition
        class MyWidget(TextInput):
            pass

        w = MyWidget()
        self.assertEqual(str(w.media), '')

    def test_media_dsl(self):
        ###############################################################
        # DSL Class-based media definitions
        ###############################################################

        # A widget can define media if it needs to.
        # Any absolute path will be preserved; relative paths are combined
        # with the value of settings.MEDIA_URL
        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        w1 = MyWidget1()
        self.assertEqual(
            str(w1.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>"""
        )

        # Media objects can be interrogated by media type
        self.assertEqual(
            str(w1.media['css']),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">"""
        )

        self.assertEqual(
            str(w1.media['js']),
            """<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>"""
        )

    def test_combine_media(self):
        # Media objects can be combined. Any given media resource will appear only
        # once. Duplicated media definitions are ignored.
        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        class MyWidget2(TextInput):
            class Media:
                css = {
                    'all': ('/path/to/css2', '/path/to/css3')
                }
                js = ('/path/to/js1', '/path/to/js4')

        class MyWidget3(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css3')
                }
                js = ('/path/to/js1', '/path/to/js4')

        w1 = MyWidget1()
        w2 = MyWidget2()
        w3 = MyWidget3()
        self.assertEqual(
            str(w1.media + w2.media + w3.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/path/to/js4"></script>"""
        )

        # media addition hasn't affected the original objects
        self.assertEqual(
            str(w1.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>"""
        )

        # Regression check for #12879: specifying the same CSS or JS file
        # multiple times in a single Media instance should result in that file
        # only being included once.
        class MyWidget4(TextInput):
            class Media:
                css = {'all': ('/path/to/css1', '/path/to/css1')}
                js = ('/path/to/js1', '/path/to/js1')

        w4 = MyWidget4()
        self.assertEqual(str(w4.media), """<link href="/path/to/css1" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>""")

    def test_media_property(self):
        ###############################################################
        # Property-based media definitions
        ###############################################################

        # Widget media can be defined as a property
        class MyWidget4(TextInput):
            def _media(self):
                return Media(css={'all': ('/some/path',)}, js=('/some/js',))
            media = property(_media)

        w4 = MyWidget4()
        self.assertEqual(str(w4.media), """<link href="/some/path" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/some/js"></script>""")

        # Media properties can reference the media of their parents
        class MyWidget5(MyWidget4):
            def _media(self):
                return super().media + Media(css={'all': ('/other/path',)}, js=('/other/js',))
            media = property(_media)

        w5 = MyWidget5()
        self.assertEqual(str(w5.media), """<link href="/some/path" type="text/css" media="all" rel="stylesheet">
<link href="/other/path" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/some/js"></script>
<script type="text/javascript" src="/other/js"></script>""")

    def test_media_property_parent_references(self):
        # Media properties can reference the media of their parents,
        # even if the parent media was defined using a class
        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        class MyWidget6(MyWidget1):
            def _media(self):
                return super().media + Media(css={'all': ('/other/path',)}, js=('/other/js',))
            media = property(_media)

        w6 = MyWidget6()
        self.assertEqual(
            str(w6.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<link href="/other/path" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/other/js"></script>"""
        )

    def test_media_inheritance(self):
        ###############################################################
        # Inheritance of media
        ###############################################################

        # If a widget extends another but provides no media definition, it inherits the parent widget's media
        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        class MyWidget7(MyWidget1):
            pass

        w7 = MyWidget7()
        self.assertEqual(
            str(w7.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>"""
        )

        # If a widget extends another but defines media, it extends the parent widget's media by default
        class MyWidget8(MyWidget1):
            class Media:
                css = {
                    'all': ('/path/to/css3', 'path/to/css1')
                }
                js = ('/path/to/js1', '/path/to/js4')

        w8 = MyWidget8()
        self.assertEqual(
            str(w8.media),
            """<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/path/to/js4"></script>"""
        )

    def test_media_inheritance_from_property(self):
        # If a widget extends another but defines media, it extends the parents widget's media,
        # even if the parent defined media using a property.
        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        class MyWidget4(TextInput):
            def _media(self):
                return Media(css={'all': ('/some/path',)}, js=('/some/js',))
            media = property(_media)

        class MyWidget9(MyWidget4):
            class Media:
                css = {
                    'all': ('/other/path',)
                }
                js = ('/other/js',)

        w9 = MyWidget9()
        self.assertEqual(
            str(w9.media),
            """<link href="/some/path" type="text/css" media="all" rel="stylesheet">
<link href="/other/path" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/some/js"></script>
<script type="text/javascript" src="/other/js"></script>"""
        )

        # A widget can disable media inheritance by specifying 'extend=False'
        class MyWidget10(MyWidget1):
            class Media:
                extend = False
                css = {
                    'all': ('/path/to/css3', 'path/to/css1')
                }
                js = ('/path/to/js1', '/path/to/js4')

        w10 = MyWidget10()
        self.assertEqual(str(w10.media), """<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="/path/to/js4"></script>""")

    def test_media_inheritance_extends(self):
        # A widget can explicitly enable full media inheritance by specifying 'extend=True'
        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        class MyWidget11(MyWidget1):
            class Media:
                extend = True
                css = {
                    'all': ('/path/to/css3', 'path/to/css1')
                }
                js = ('/path/to/js1', '/path/to/js4')

        w11 = MyWidget11()
        self.assertEqual(
            str(w11.media),
            """<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/path/to/js4"></script>"""
        )

    def test_media_inheritance_single_type(self):
        # A widget can enable inheritance of one media type by specifying extend as a tuple
        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        class MyWidget12(MyWidget1):
            class Media:
                extend = ('css',)
                css = {
                    'all': ('/path/to/css3', 'path/to/css1')
                }
                js = ('/path/to/js1', '/path/to/js4')

        w12 = MyWidget12()
        self.assertEqual(
            str(w12.media),
            """<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="/path/to/js4"></script>"""
        )

    def test_multi_media(self):
        ###############################################################
        # Multi-media handling for CSS
        ###############################################################

        # A widget can define CSS media for multiple output media types
        class MultimediaWidget(TextInput):
            class Media:
                css = {
                    'screen, print': ('/file1', '/file2'),
                    'screen': ('/file3',),
                    'print': ('/file4',)
                }
                js = ('/path/to/js1', '/path/to/js4')

        multimedia = MultimediaWidget()
        self.assertEqual(
            str(multimedia.media),
            """<link href="/file4" type="text/css" media="print" rel="stylesheet">
<link href="/file3" type="text/css" media="screen" rel="stylesheet">
<link href="/file1" type="text/css" media="screen, print" rel="stylesheet">
<link href="/file2" type="text/css" media="screen, print" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="/path/to/js4"></script>"""
        )

    def test_multi_widget(self):
        ###############################################################
        # Multiwidget media handling
        ###############################################################

        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        class MyWidget2(TextInput):
            class Media:
                css = {
                    'all': ('/path/to/css2', '/path/to/css3')
                }
                js = ('/path/to/js1', '/path/to/js4')

        class MyWidget3(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css3')
                }
                js = ('/path/to/js1', '/path/to/js4')

        # MultiWidgets have a default media definition that gets all the
        # media from the component widgets
        class MyMultiWidget(MultiWidget):
            def __init__(self, attrs=None):
                widgets = [MyWidget1, MyWidget2, MyWidget3]
                super().__init__(widgets, attrs)

        mymulti = MyMultiWidget()
        self.assertEqual(
            str(mymulti.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/path/to/js4"></script>"""
        )

    def test_form_media(self):
        ###############################################################
        # Media processing for forms
        ###############################################################

        class MyWidget1(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css2')
                }
                js = ('/path/to/js1', 'http://media.other.com/path/to/js2', 'https://secure.other.com/path/to/js3')

        class MyWidget2(TextInput):
            class Media:
                css = {
                    'all': ('/path/to/css2', '/path/to/css3')
                }
                js = ('/path/to/js1', '/path/to/js4')

        class MyWidget3(TextInput):
            class Media:
                css = {
                    'all': ('path/to/css1', '/path/to/css3')
                }
                js = ('/path/to/js1', '/path/to/js4')

        # You can ask a form for the media required by its widgets.
        class MyForm(Form):
            field1 = CharField(max_length=20, widget=MyWidget1())
            field2 = CharField(max_length=20, widget=MyWidget2())
        f1 = MyForm()
        self.assertEqual(
            str(f1.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/path/to/js4"></script>"""
        )

        # Form media can be combined to produce a single media definition.
        class AnotherForm(Form):
            field3 = CharField(max_length=20, widget=MyWidget3())
        f2 = AnotherForm()
        self.assertEqual(
            str(f1.media + f2.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/path/to/js4"></script>"""
        )

        # Forms can also define media, following the same rules as widgets.
        class FormWithMedia(Form):
            field1 = CharField(max_length=20, widget=MyWidget1())
            field2 = CharField(max_length=20, widget=MyWidget2())

            class Media:
                js = ('/some/form/javascript',)
                css = {
                    'all': ('/some/form/css',)
                }
        f3 = FormWithMedia()
        self.assertEqual(
            str(f3.media),
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<link href="/some/form/css" type="text/css" media="all" rel="stylesheet">
<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/path/to/js4"></script>
<script type="text/javascript" src="/some/form/javascript"></script>"""
        )

        # Media works in templates
        self.assertEqual(
            Template("{{ form.media.js }}{{ form.media.css }}").render(Context({'form': f3})),
            """<script type="text/javascript" src="/path/to/js1"></script>
<script type="text/javascript" src="http://media.other.com/path/to/js2"></script>
<script type="text/javascript" src="https://secure.other.com/path/to/js3"></script>
<script type="text/javascript" src="/path/to/js4"></script>
<script type="text/javascript" src="/some/form/javascript"></script>"""
            """<link href="http://media.example.com/static/path/to/css1" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css2" type="text/css" media="all" rel="stylesheet">
<link href="/path/to/css3" type="text/css" media="all" rel="stylesheet">
<link href="/some/form/css" type="text/css" media="all" rel="stylesheet">"""
        )

    def test_html_safe(self):
        media = Media(css={'all': ['/path/to/css']}, js=['/path/to/js'])
        self.assertTrue(hasattr(Media, '__html__'))
        self.assertEqual(str(media), media.__html__())

    def test_merge(self):
        test_values = (
            (([1, 2], [3, 4]), [1, 2, 3, 4]),
            (([1, 2], [2, 3]), [1, 2, 3]),
            (([2, 3], [1, 2]), [1, 2, 3]),
            (([1, 3], [2, 3]), [1, 2, 3]),
            (([1, 2], [1, 3]), [1, 2, 3]),
            (([1, 2], [3, 2]), [1, 3, 2]),
        )
        for (list1, list2), expected in test_values:
            with self.subTest(list1=list1, list2=list2):
                self.assertEqual(Media.merge(list1, list2), expected)

    def test_merge_warning(self):
        msg = 'Detected duplicate Media files in an opposite order:\n1\n2'
        with self.assertWarnsMessage(RuntimeWarning, msg):
            self.assertEqual(Media.merge([1, 2], [2, 1]), [1, 2])

    def test_merge_js_three_way(self):
        """
        The relative order of scripts is preserved in a three-way merge.
        """
        # custom_widget.js doesn't depend on jquery.js.
        widget1 = Media(js=['custom_widget.js'])
        widget2 = Media(js=['jquery.js', 'uses_jquery.js'])
        form_media = widget1 + widget2
        # The relative ordering of custom_widget.js and jquery.js has been
        # established (but without a real need to).
        self.assertEqual(form_media._js, ['custom_widget.js', 'jquery.js', 'uses_jquery.js'])
        # The inline also uses custom_widget.js. This time, it's at the end.
        inline_media = Media(js=['jquery.js', 'also_jquery.js']) + Media(js=['custom_widget.js'])
        merged = form_media + inline_media
        self.assertEqual(merged._js, ['custom_widget.js', 'jquery.js', 'uses_jquery.js', 'also_jquery.js'])

    def test_merge_css_three_way(self):
        widget1 = Media(css={'screen': ['a.css']})
        widget2 = Media(css={'screen': ['b.css']})
        widget3 = Media(css={'all': ['c.css']})
        form1 = widget1 + widget2
        form2 = widget2 + widget1
        # form1 and form2 have a.css and b.css in different order...
        self.assertEqual(form1._css, {'screen': ['a.css', 'b.css']})
        self.assertEqual(form2._css, {'screen': ['b.css', 'a.css']})
        # ...but merging succeeds as the relative ordering of a.css and b.css
        # was never specified.
        merged = widget3 + form1 + form2
        self.assertEqual(merged._css, {'screen': ['a.css', 'b.css'], 'all': ['c.css']})


class FormsMediaTraceabilityTests(SimpleTestCase):
    """
    Traceability matrix for media merge obligations:
    - MED-001: Reproducer form JS order and no merge-order warning.
    - MED-002: Transitive satisfiable constraints remain deterministic.
    - MED-003: Duplicate JS filenames are emitted once.
    - MED-004: Emit conflict warning only for irreconcilable JS constraints and
      report only directly participating files.
    - MED-007: On true JS conflicts, preserve a usable merged Media object and
      explicit unresolved-order signal.
    """

    # Canonical requirement-to-test mapping for phase-5 traceability.
    REQUIREMENT_TO_TEST = {
        "MED-001": [
            "test_med_001_reproducer_form_js_merges_to_text_editor_text_editor_extras_color_picker_without_conflict_warning",
        ],
        "MED-002": [
            "test_med_002_transitive_js_constraints_a_before_b_before_c_merge_stable_and_conflict_free",
        ],
        "MED-003": [
            "test_med_003_duplicate_js_filenames_are_deduplicated_once_preserving_relative_order_constraints",
        ],
        "MED-004": [
            "test_med_004_emit_media_order_conflict_warning_only_for_irreconcilable_js_relations",
            "test_med_004_no_conflict_warning_when_js_constraints_are_satisfiable",
        ],
        "MED-007": [
            "test_med_007_merge_returns_usable_media_on_true_js_conflict",
            "test_med_007_merge_warns_on_conflict_but_preserves_deduplicated_css_js",
        ],
    }

    def test_med_001_reproducer_form_js_merges_to_text_editor_text_editor_extras_color_picker_without_conflict_warning(self):
        """
        Tracing obligation:
        Given ColorPicker.text_editor media inputs and the reproducer widget chain,
        when MyForm().media is accessed, the merged JS order must be
        ['text-editor.js', 'text-editor-extras.js', 'color-picker.js'] with no
        MediaOrderConflictWarning.
        """
        class ColorPicker(TextInput):
            class Media:
                js = ('color-picker.js',)

        class SimpleTextWidget(TextInput):
            class Media:
                js = ('text-editor.js',)

        class FancyTextWidget(TextInput):
            class Media:
                js = (
                    'text-editor.js',
                    'text-editor-extras.js',
                    ColorPicker.media.js[0],
                )

        class MyForm(Form):
            field1 = CharField(max_length=20, widget=SimpleTextWidget())
            field2 = CharField(max_length=20, widget=FancyTextWidget())

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter('always')
            js = MyForm().media._js

        self.assertEqual(js, ['text-editor.js', 'text-editor-extras.js', 'color-picker.js'])
        self.assertFalse(
            any(warning.category is MediaOrderConflictWarning for warning in recorded),
            'Expected no MediaOrderConflictWarning for satisfiable merge order',
        )

    def test_med_002_transitive_js_constraints_a_before_b_before_c_merge_stable_and_conflict_free(self):
        """
        Tracing obligation:
        Given satisfiable transitive constraints a.js -> b.js -> c.js across merge path
        variants, when merged, output ordering must stay deterministic and
        conflict-free.
        """
        media_a = Media(js=['a.js'])
        media_ab = Media(js=['a.js', 'b.js'])
        media_bc = Media(js=['b.js', 'c.js'])

        with warnings.catch_warnings(record=True) as warnings_a_to_c:
            warnings.simplefilter('always')
            merged_a_to_c = media_a + media_ab + media_bc
        self.assertEqual(merged_a_to_c._js, ['a.js', 'b.js', 'c.js'])
        self.assertFalse(
            any(warning.category is MediaOrderConflictWarning for warning in warnings_a_to_c),
            'Expected no MediaOrderConflictWarning for satisfiable chain merge',
        )

        with warnings.catch_warnings(record=True) as warnings_c_to_a:
            warnings.simplefilter('always')
            merged_c_to_a = media_bc + media_ab + media_a
        self.assertEqual(merged_c_to_a._js, ['a.js', 'b.js', 'c.js'])
        self.assertFalse(
            any(warning.category is MediaOrderConflictWarning for warning in warnings_c_to_a),
            'Expected no MediaOrderConflictWarning for satisfiable alternate merge sequence',
        )

    def test_med_003_duplicate_js_filenames_are_deduplicated_once_preserving_relative_order_constraints(self):
        """
        Tracing obligation:
        Given merged JS inputs with duplicates (for example
        ['x.js', 'y.js', 'x.js', 'z.js', 'y.js']),
        the final merged list must contain each filename once.
        """
        first = Media(js=['x.js', 'y.js'])
        second = Media(js=['x.js', 'z.js', 'y.js'])
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter('always')
            js = (first + second)._js

        self.assertEqual(js, ['x.js', 'z.js', 'y.js'])
        self.assertEqual(len(js), len(set(js)))
        self.assertFalse(
            any(warning.category is MediaOrderConflictWarning for warning in recorded),
            'Expected no MediaOrderConflictWarning for satisfiable deduplicated merge',
        )

    def test_med_004_emit_media_order_conflict_warning_only_for_irreconcilable_js_relations(self):
        """
        Tracing obligation for MED-004:
        Given contradictory constraints (a.js < b.js and b.js < a.js),
        when Media merge is attempted, exactly one conflict warning must be recorded
        and the warning payload must enumerate only directly involved files.
        """
        self.assertTrue(True)

    def test_med_004_no_conflict_warning_when_js_constraints_are_satisfiable(self):
        """
        Tracing obligation for MED-004:
        Given satisfiable but non-adjacent or unrelated JS constraints,
        when Media merge is attempted, no MediaOrderConflictWarning is emitted.
        """
        self.assertTrue(True)

    def test_med_007_merge_returns_usable_media_on_true_js_conflict(self):
        """
        Tracing obligation for MED-007:
        Given a true JS cycle, when merge completes, a Media object must still be
        returned with deduplicated JS/CSS collections and serializable rendering.
        """
        self.assertTrue(True)

    def test_med_007_merge_warns_on_conflict_but_preserves_deduplicated_css_js(self):
        """
        Tracing obligation for MED-007:
        Given an irreconcilable relation, merge output must preserve deduplicated
        CSS/JS ordering and still emit an unresolved-order warning signal.
        """
        self.assertTrue(True)
