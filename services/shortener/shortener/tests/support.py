"""Standing in for the auth service.

These tests mint their own tokens. That is not a shortcut around
authentication — it is the only option: this service holds no user table, so
there is nobody to log in as. A caller exists here purely as a set of claims,
which is exactly how the running service sees one too.

Signing needs no setup: HS256 signs with SECRET_KEY, which this service already
has. That it *can* sign is precisely the property asymmetric keys would have
removed — a service that verifies tokens can also issue them.
"""

import itertools

from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken

_ids = itertools.count(1)


class Caller:
    """A user that exists only as JWT claims."""

    def __init__(self, tier='free', is_premium=False, is_staff=False):
        self.id = next(_ids)
        self.username = f'user{self.id}'
        self.tier = tier
        # Mirrors what the auth service puts in the claim: has_premium_access,
        # not the raw column — so the admin tier arrives as premium.
        self.is_premium = is_premium or tier in ('premium', 'admin')
        self.is_staff = is_staff


class AuthenticatedAPITestCase(TestCase):
    def authenticate(self, caller=None):
        caller = caller or Caller()
        token = AccessToken()
        # Deliberately a string, reproducing what simple_jwt actually writes.
        # `caller_id()` exists to coerce it; hard-coding an int here would hide
        # the very bug those checks guard against.
        token['user_id'] = str(caller.id)
        token['username'] = caller.username
        token['tier'] = caller.tier
        token['is_premium'] = caller.is_premium
        token['is_staff'] = caller.is_staff
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return caller

    def logout(self):
        self.client.defaults.pop('HTTP_AUTHORIZATION', None)
