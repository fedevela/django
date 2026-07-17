from django.core.management.templates import TemplateCommand


class Command(TemplateCommand):
    help = (
        "Creates a Django app directory structure for the given app name in "
        "the current directory or optionally in the given directory."
    )
    missing_args_message = "You must provide an application name."

    def handle(self, **options):
        app_name = options.pop('name')
        target = options.pop('directory')

        # Target-path integration boundary (DJANGO-001, DJANGO-002,
        # DJANGO-003, DJANGO-004, DJANGO-005, DJANGO-006, DJANGO-007): this
        # command owns CLI option extraction and passes the supplied path
        # unchanged.
        # TemplateCommand owns native-component validation, destination-root
        # resolution, and the rendering boundary.
        super().handle('app', app_name, target, **options)
