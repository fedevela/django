from django.contrib.auth.models import User
from django.db import models


class Concrete(models.Model):
    pass


class Proxy(Concrete):
    class Meta:
        proxy = True
        permissions = (
            ('display_proxys', 'May display proxys information'),
        )


class UserProxy(User):
    class Meta:
        proxy = True
        permissions = (
            ('use_different_app_label', 'May use a different app label'),
        )


class SharedCodenameProxyA(Concrete):
    class Meta:
        proxy = True
        permissions = (
            ('shared_proxy_permission', 'Can share this proxy permission scope'),
        )


class SharedCodenameProxyB(Concrete):
    class Meta:
        proxy = True
        permissions = (
            ('shared_proxy_permission', 'Can share this proxy permission scope'),
        )
