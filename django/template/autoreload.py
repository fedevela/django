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
    # Pseudocode contract — ARLD-005
    # Verification: test_arld_005_empty_template_dirs_file_change_preserves_existing_autoreload
    # Verification: test_arld_005_template_dirs_exclude_base_dir_file_change_preserves_existing_autoreload
    # INPUT: configured template directories and the reloader's independently
    # established project-file watches.
    # IF no template directories are returned, perform no directory-watch
    # registrations and leave existing project-file change handling unchanged.
    # OTHERWISE, FOR EACH returned template directory, add its recursive watch
    # without replacing, narrowing, or suppressing any project-file watch.
    # IF the returned directories exclude BASE_DIR, do not infer or register a
    # BASE_DIR template watch; retain the existing project-file watch set.
    # FAILURE PATH: template configuration must not consume file-change events
    # or disable the general autoreload fallback when no applicable directory
    # registration exists.
    # Template-directory registration boundary (ARLD-004): encompassing,
    # valid directories belong here without narrowing general file watches.
    for directory in get_template_directories():
        sender.watch_dir(directory, '**/*')


@receiver(file_changed, dispatch_uid='template_loaders_file_changed')
def template_changed(sender, file_path, **kwargs):
    # Pseudocode contract — ARLD-006
    # Verification: test_arld_006_overlapping_template_and_project_watches_template_change_remains_detected
    # INPUT: a monitored changed path delivered from template-directory and/or
    # project-file watches, plus the configured template directories.
    # Apply the existing path classification without regard to which overlapping
    # watch delivered the notification.
    # IF the existing project-file exclusion applies, decline template handling
    # and hand the event to the general autoreload fallback.
    # OTHERWISE, FOR EACH configured template directory, test whether it
    # contains the changed path.
    # IF containment is found, reset the template loaders, mark the event as
    # consumed, and stop checking directories.
    # IF no containment is found, leave the event unconsumed for the general
    # autoreload fallback.
    # FAILURE PATH: overlap or duplicate watch coverage must not discard the
    # notification before existing template-change classification runs.
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
    # Integration seam (ARLD-001, ARLD-002, ARLD-003): this receiver owns
    # template cache invalidation only; project reload authority remains with
    # BaseReloader.notify_file_changed() across overlapping watch paths.
    if file_path.suffix == '.py':
        return
    for template_dir in get_template_directories():
        if template_dir in file_path.parents:
            reset_loaders()
            return True
