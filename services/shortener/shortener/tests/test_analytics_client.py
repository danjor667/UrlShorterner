"""The shortener's outbound call to analytics.

These tests patch `requests.post`: they describe how the client reacts to what
analytics returns, not whether analytics is correct.
"""

from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings

from ..analytics_client import AnalyticsUnavailable, client_ip, record_click


@override_settings(ANALYTICS_URL='http://analytics:8000', ANALYTICS_TIMEOUT=3.0)
class RecordClickTests(TestCase):
    def _request(self, **meta):
        request = Mock()
        request.META = meta
        return request

    @patch('shortener.analytics_client.requests.post')
    def test_posts_the_click_payload(self, post):
        post.return_value = Mock(status_code=201)

        record_click(42, self._request(REMOTE_ADDR='10.0.0.1', HTTP_USER_AGENT='agent'))

        endpoint = post.call_args.args[0]
        self.assertEqual(endpoint, 'http://analytics:8000/internal/clicks/')
        self.assertEqual(post.call_args.kwargs['json']['url_id'], 42)
        self.assertEqual(post.call_args.kwargs['json']['ip_address'], '10.0.0.1')
        self.assertEqual(post.call_args.kwargs['timeout'], 3.0)

    @patch('shortener.analytics_client.requests.post')
    def test_missing_headers_become_empty_rather_than_errors(self, post):
        post.return_value = Mock(status_code=201)

        record_click(1, self._request())

        payload = post.call_args.kwargs['json']
        self.assertIsNone(payload['ip_address'])
        self.assertEqual(payload['user_agent'], '')

    @patch('shortener.analytics_client.requests.post')
    def test_long_user_agent_is_truncated(self, post):
        post.return_value = Mock(status_code=201)

        record_click(1, self._request(HTTP_USER_AGENT='x' * 5000))

        self.assertEqual(len(post.call_args.kwargs['json']['user_agent']), 1000)

    @patch('shortener.analytics_client.requests.post')
    def test_timeout_raises_analytics_unavailable(self, post):
        post.side_effect = requests.Timeout('timed out')

        with self.assertRaises(AnalyticsUnavailable):
            record_click(1, self._request())

    @patch('shortener.analytics_client.requests.post')
    def test_error_status_raises_analytics_unavailable(self, post):
        post.return_value = Mock(status_code=500, text='boom')

        with self.assertRaises(AnalyticsUnavailable):
            record_click(1, self._request())


class ClientIPTests(TestCase):
    """Which address gets recorded for a click.

    Behind the gateway `REMOTE_ADDR` is nginx, so reading it recorded the
    gateway's own container address on every click and no lookup could ever
    resolve.
    """

    def _request(self, **meta):
        request = Mock()
        request.META = meta
        return request

    def test_prefers_x_real_ip(self):
        request = self._request(HTTP_X_REAL_IP='105.112.0.1', REMOTE_ADDR='172.20.0.8')
        self.assertEqual(client_ip(request), '105.112.0.1')

    def test_falls_back_to_remote_addr(self):
        """Direct access does not pass through nginx, so the header is absent."""
        self.assertEqual(client_ip(self._request(REMOTE_ADDR='10.1.2.3')), '10.1.2.3')

    def test_returns_none_when_nothing_is_available(self):
        self.assertIsNone(client_ip(self._request()))

    def test_x_forwarded_for_is_ignored(self):
        """nginx appends to XFF, so a client-supplied value survives in it.

        Trusting that header would let any visitor claim any address and
        poison the country breakdown.
        """
        request = self._request(
            HTTP_X_FORWARDED_FOR='1.2.3.4, 172.20.0.8',
            HTTP_X_REAL_IP='105.112.0.1',
            REMOTE_ADDR='172.20.0.8',
        )
        self.assertEqual(client_ip(request), '105.112.0.1')

    @patch('shortener.analytics_client.requests.post')
    def test_the_reported_payload_uses_it(self, post):
        post.return_value = Mock(status_code=201)
        record_click(1, self._request(HTTP_X_REAL_IP='8.8.8.8', REMOTE_ADDR='172.20.0.8'))
        self.assertEqual(post.call_args.kwargs['json']['ip_address'], '8.8.8.8')
