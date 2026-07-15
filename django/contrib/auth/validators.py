import re

from django.core import validators
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class ASCIIUsernameValidator(validators.RegexValidator):
    # DJANGO11099-001: convert boundary handling to explicit string boundaries.
    # Algorithmic obligation:
    # 1) Evaluate `value` against a single regular expression.
    # 2) Require exact-string match semantics (beginning + end only for the whole string).
    # 3) Accept only one-or-more chars in [\\w.@+-].
    # 4) If any char is outside the class OR the full-string boundary cannot be met,
    #    reject by raising ValidationError with `message`.
    # Failure example:
    # - value="alice\n": boundary logic must fail because trailing newline cannot be
    #   part of [\\w.@+-], so validation must reject.
    regex = r'^[\w.@+-]+$'
    message = _(
        'Enter a valid username. This value may contain only English letters, '
        'numbers, and @/./+/-/_ characters.'
    )
    flags = re.ASCII


@deconstructible
class UnicodeUsernameValidator(validators.RegexValidator):
    # DJANGO11099-002: convert boundary handling to explicit string boundaries.
    # Algorithmic obligation:
    # 1) Evaluate `value` against a single regular expression.
    # 2) Require exact-string match semantics (beginning + end only for the whole string).
    # 3) Accept only one-or-more chars in [\\w.@+-] under Unicode word-class behavior.
    # 4) If any char is outside the class OR the full-string boundary cannot be met,
    #    reject by raising ValidationError with `message`.
    # Failure example:
    # - value="alice\n": boundary logic must fail because trailing newline cannot be
    #   part of [\\w.@+-], so validation must reject.
    regex = r'^[\w.@+-]+$'
    message = _(
        'Enter a valid username. This value may contain only letters, '
        'numbers, and @/./+/-/_ characters.'
    )
    flags = 0
