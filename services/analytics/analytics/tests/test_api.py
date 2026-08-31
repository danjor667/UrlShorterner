"""Analytics service tests — the internal click-write endpoint."""

from django.test import TestCase

from ..models import Click


class ClickCreateTests(TestCase):
    url = '/internal/clicks/'

    def _post(self, **payload):
        payload.setdefault('url_id', 42)
        return self.client.post(self.url, payload, content_type='application/json')

    def test_records_a_click(self):
        response = self._post(ip_address='10.0.0.1', user_agent='agent', referrer='https://ref.example.com/')

        self.assertEqual(response.status_code, 201)
        click = Click.objects.get()
        self.assertEqual(click.url_id, 42)
        self.assertEqual(click.ip_address, '10.0.0.1')
        self.assertEqual(click.user_agent, 'agent')

    def test_url_id_is_required(self):
        response = self.client.post(self.url, {'user_agent': 'a'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('url_id', response.json())

    def test_accepts_an_unknown_url_id(self):
        """Nothing here can check that the URL exists — it is in another database.

        Rejecting unknown ids would require a synchronous call back to the
        shortener on every click, which is exactly the coupling the split is
        meant to avoid.
        """
        self.assertEqual(self._post(url_id=999999).status_code, 201)

    def test_clicked_at_is_server_assigned(self):
        response = self._post(clicked_at='1999-01-01T00:00:00Z')
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(Click.objects.get().clicked_at.year, 1999)

    def test_optional_fields_default_to_blank(self):
        self._post()
        click = Click.objects.get()
        self.assertIsNone(click.ip_address)
        self.assertEqual(click.user_agent, '')
        self.assertEqual(click.country, '')

    def test_many_clicks_for_one_url(self):
        for _ in range(3):
            self._post(url_id=7)
        self.assertEqual(Click.objects.filter(url_id=7).count(), 3)


class RoutingTests(TestCase):
    def test_schema_is_served(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)

    def test_admin_is_mounted_under_the_service_prefix(self):
        self.assertEqual(self.client.get('/admin/analytics/').status_code, 302)
        self.assertEqual(self.client.get('/admin/').status_code, 404)
