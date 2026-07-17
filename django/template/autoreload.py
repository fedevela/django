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
    # Pseudocode contract — ARLD-002
    # Verification: test_arld_002_saving_settings_in_base_dir_template_dirs_triggers_autoreload
    # INPUT: a changed settings.py path monitored by the development reloader,
    # with its accessible BASE_DIR also configured as a template directory.
    # IF the changed path identifies a Python project file, decline template
    # handling before testing template-directory containment.
    # HANDOFF: return an unconsumed result to BaseReloader.notify_file_changed().
    # IF no other file_changed receiver consumes the event, trigger autoreload
    # with the unchanged settings.py path.
    # FAILURE PATH: never reset template loaders or suppress the general reload
    # merely because BASE_DIR contains both templates and settings.py.
    # Integration seam (ARLD-001, ARLD-003): this receiver owns template
    # cache invalidation only; project reload authority remains with
    # BaseReloader.notify_file_changed() across overlapping watch paths.
    if file_path.suffix == '.py':
        return
    for template_dir in get_template_directories():
        if template_dir in file_path.parents:
            reset_loaders()
            return True
