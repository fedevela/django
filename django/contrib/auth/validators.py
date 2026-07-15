import re

from django.core import validators
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class ASCIIUsernameValidator(validators.RegexValidator):
    # DJANGO11099-001: convert boundary handling to explicit string boundaries.
    # DJANGO11099-005,006,007: preserve baseline validity semantics while keeping
    # the same allowed-character contract.
    # Procedural obligation for this validator:
    # Input -> value (string)
    # 1) Run the regex r'\A[\w.@+-]+\Z' against the entire value.
    # 2) If value is empty:
    #    - match fails because "+" requires one-or-more characters.
    #    - raise ValidationError with `message`.
    # 3) Else if any character is outside \w, ., @, +, -, _:
    #    - match fails.
    #    - raise ValidationError with `message`.
    # 4) Else if regex matches exactly from start to end:
    #    - accept (no exception).
    # 5) Failure path is any non-empty-match mismatch, including trailing newline.
    # Algorithmic obligation:
    # 1) Evaluate `value` against a single regular expression.
    # 2) Require exact-string match semantics (beginning + end only for the whole string).
    # 3) Accept only one-or-more chars in [\\w.@+-].
    # 4) If any char is outside the class OR the full-string boundary cannot be met,
    #    reject by raising ValidationError with `message`.
    # Failure example:
    # - value="alice\n": boundary logic must fail because trailing newline cannot be
    #   part of [\\w.@+-], so validation must reject.
    regex = r'\A[\w.@+-]+\Z'  # DJANGO11099-008: state=start; if not value: REJECT; elif not re.fullmatch(regex, value): REJECT; else ACCEPT.
    message = _(
        'Enter a valid username. This value may contain only English letters, '
        'numbers, and @/./+/-/_ characters.'
    )
    flags = re.ASCII


@deconstructible
class UnicodeUsernameValidator(validators.RegexValidator):
    # DJANGO11099-002: convert boundary handling to explicit string boundaries.
    # DJANGO11099-005,006,007: preserve baseline validity semantics while keeping
    # the same allowed-character contract.
    # Procedural obligation for this validator:
    # Input -> value (string)
    # 1) Run the regex r'\A[\w.@+-]+\Z' against the entire value.
    # 2) If value is empty:
    #    - match fails because "+" requires one-or-more characters.
    #    - raise ValidationError with `message`.
    # 3) Else if any character is outside \w, ., @, +, -, _:
    #    - match fails.
    #    - raise ValidationError with `message`.
    # 4) Else if regex matches exactly from start to end:
    #    - accept (no exception).
    # 5) Failure path is any non-empty-match mismatch, including trailing newline.
    # Algorithmic obligation:
    # 1) Evaluate `value` against a single regular expression.
    # 2) Require exact-string match semantics (beginning + end only for the whole string).
    # 3) Accept only one-or-more chars in [\\w.@+-] under Unicode word-class behavior.
    # 4) If any char is outside the class OR the full-string boundary cannot be met,
    #    reject by raising ValidationError with `message`.
    # Failure example:
    # - value="alice\n": boundary logic must fail because trailing newline cannot be
    #   part of [\\w.@+-], so validation must reject.
    regex = r'\A[\w.@+-]+\Z'  # DJANGO11099-008: state=start; if not value: REJECT; elif not re.fullmatch(regex, value): REJECT; else ACCEPT.
    message = _(
        'Enter a valid username. This value may contain only letters, '
        'numbers, and @/./+/-/_ characters.'
    )
    flags = 0
