from pathlib import Path

from django.dispatch import receiver
from django.template import engines
from django.template.backends.django import DjangoTemplates
from django.utils._os import to_path
from django.utils.autoreload import (
    autoreload_started, file_changed, is_django_path,
)


def get_template_directories():
    # Iterate through each template backend and find
    # any template_loader that has a 'get_dirs' method.
    # Collect the directories, filtering out Django templates.
    cwd = Path.cwd()
    items = set()
    for backend in engines.all():
        if not isinstance(backend, DjangoTemplates):
            continue

        items.update(cwd / to_path(dir) for dir in backend.engine.dirs)

        for loader in backend.engine.template_loaders:
            if not hasattr(loader, 'get_dirs'):
                continue
            items.update(
                cwd / to_path(directory)
                for directory in loader.get_dirs()
                if not is_django_path(directory)
            )
    return items


def reset_loaders():
    for backend in engines.all():
        if not isinstance(backend, DjangoTemplates):
            continue
        for loader in backend.engine.template_loaders:
            loader.reset()


@receiver(autoreload_started, dispatch_uid='template_loaders_watch_changes')
def watch_for_template_changes(sender, **kwargs):
    # Template-directory registration boundary (ARLD-004): encompassing,
    # valid directories belong here without narrowing general file watches.
    for directory in get_template_directories():
        sender.watch_dir(directory, '**/*')


@receiver(file_changed, dispatch_uid='template_loaders_file_changed')
def template_changed(sender, file_path, **kwargs):
    # Integration seam (ARLD-001, ARLD-003): this receiver owns template
    # cache invalidation only; project reload authority remains with
    # BaseReloader.notify_file_changed() across overlapping watch paths.
    # Pseudocode contract — ARLD-001, ARLD-003, ARLD-004:
    # INPUT: a changed path, the general autoreloader's monitored-project-file
    # classification, and the configured template directories.
    # IF the changed path is independently monitored as a non-template project
    # file, THEN decline to consume the event and hand it back to the general
    # autoreloader so that it can trigger a development-server reload.
    # OTHERWISE, FOR EACH valid, accessible template directory:
    #     IF the changed path is below that directory, reset the template
    #     loaders, consume the event, and stop checking directories.
    # IF no template directory contains the changed path, decline to consume
    # the event so that normal autoreload processing remains unchanged.
    # Overlap transition: project-file monitoring retains precedence even when
    # an encompassing template directory (including BASE_DIR) also contains
    # the path; directory containment must not replace the broader monitor.
    for template_dir in get_template_directories():
        if template_dir in file_path.parents:
            reset_loaders()
            return True
