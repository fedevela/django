from django.db import models


class DirectBigAutoField(models.BigAutoField):
    pass


class IndirectBigAutoField(DirectBigAutoField):
    pass


class DirectSmallAutoField(models.SmallAutoField):
    pass


class IndirectSmallAutoField(DirectSmallAutoField):
    pass
