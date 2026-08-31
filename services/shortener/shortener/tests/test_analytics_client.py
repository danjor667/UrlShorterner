"""The shortener's outbound call to analytics.

These tests patch `requests.post`: they describe how the client reacts to what
analytics returns, not whether analytics is correct.
"""

from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings

from ..analytics_client import AnalyticsUnavailable, record_click


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
