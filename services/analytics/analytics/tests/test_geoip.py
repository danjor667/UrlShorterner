"""Geolocation of click IPs.

The database is baked into the image, but these skip rather than fail when it
is absent so the suite still runs against a source checkout.
"""

from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.test import TestCase, override_settings

from .. import geoip
from ..models import Click

HAVE_DB = Path(settings.GEOIP_DB_PATH).exists()


def _reset_reader():
    """The reader is cached at module level; tests that change the path must clear it."""
    geoip._reader = None
    geoip._load_failed = False


@skipUnless(HAVE_DB, 'geoip database not present in this image')
class LookupTests(TestCase):
    def setUp(self):
        _reset_reader()
        self.addCleanup(_reset_reader)

    def test_resolves_a_public_address(self):
        self.assertEqual(geoip.lookup('105.112.0.1')['country'], 'NG')
        self.assertEqual(geoip.lookup('8.8.8.8')['country'], 'US')

    def test_country_only_database_leaves_city_blank(self):
        """The 4MB country file has no city data; the 60MB one would fill it."""
        self.assertEqual(geoip.lookup('8.8.8.8')['city'], '')

    def test_private_address_is_blank_not_an_error(self):
        """Every click in local development comes from a private range."""
        self.assertEqual(geoip.lookup('172.20.0.8'), {'country': '', 'city': ''})
        self.assertEqual(geoip.lookup('10.0.0.1'), {'country': '', 'city': ''})
        self.assertEqual(geoip.lookup('127.0.0.1'), {'country': '', 'city': ''})


class DegradedTests(TestCase):
    """Nothing here may raise — a click is worth recording unplaced."""

    def setUp(self):
        _reset_reader()
        self.addCleanup(_reset_reader)

    def test_no_address(self):
        self.assertEqual(geoip.lookup(None), {'country': '', 'city': ''})
        self.assertEqual(geoip.lookup(''), {'country': '', 'city': ''})

    def test_malformed_address(self):
        self.assertEqual(geoip.lookup('not-an-ip'), {'country': '', 'city': ''})
        self.assertEqual(geoip.lookup('999.1.1.1'), {'country': '', 'city': ''})

    @override_settings(GEOIP_DB_PATH='/nonexistent/geoip.mmdb')
    def test_missing_database_is_survivable(self):
        with self.assertLogs('analytics.geoip', level='WARNING') as logs:
            self.assertEqual(geoip.lookup('8.8.8.8'), {'country': '', 'city': ''})
        self.assertIn('geolocation disabled', logs.output[0])

    @override_settings(GEOIP_DB_PATH='/nonexistent/geoip.mmdb')
    def test_missing_database_is_logged_once_not_per_click(self):
        with self.assertLogs('analytics.geoip', level='WARNING') as logs:
            for _ in range(5):
                geoip.lookup('8.8.8.8')
        self.assertEqual(len(logs.output), 1)


class ClickEnrichmentTests(TestCase):
    """The country is resolved when the click is written, not when read."""

    url = '/internal/clicks/'

    def setUp(self):
        _reset_reader()
        self.addCleanup(_reset_reader)

    def _post(self, **payload):
        payload.setdefault('url_id', 1)
        return self.client.post(self.url, payload, content_type='application/json')

    @skipUnless(HAVE_DB, 'geoip database not present in this image')
    def test_public_address_is_geolocated_on_write(self):
        self.assertEqual(self._post(ip_address='105.112.0.1').status_code, 201)
        self.assertEqual(Click.objects.get().country, 'NG')

    @skipUnless(HAVE_DB, 'geoip database not present in this image')
    def test_a_caller_supplied_country_is_overwritten(self):
        """The shortener reports what it saw; it does not get to assert a country."""
        self._post(ip_address='8.8.8.8', country='ZZ', city='Nowhere')

        click = Click.objects.get()
        self.assertEqual(click.country, 'US')
        self.assertEqual(click.city, '')

    def test_private_address_still_records_the_click(self):
        self.assertEqual(self._post(ip_address='10.0.0.1').status_code, 201)
        click = Click.objects.get()
        self.assertEqual(click.country, '')
        self.assertEqual(click.ip_address, '10.0.0.1')

    def test_click_without_an_address_still_records(self):
        self.assertEqual(self._post().status_code, 201)
        self.assertEqual(Click.objects.get().country, '')
