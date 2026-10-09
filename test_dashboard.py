"""Test the actual Flask auth hooks without starting bot workers or integrations."""
import hmac
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, jsonify, request
from itsdangerous import URLSafeTimedSerializer


class DashboardAuthTests(unittest.TestCase):
    def setUp(self):
        self.token = 'synthetic-dashboard-test-token'
        source = Path(__file__).with_name('main.py').read_text()
        # Importing main starts a worker; execute only the deployed auth section.
        section = source[source.index('app = Flask(__name__)'):source.index('@app.route("/live")')]
        self.ns = dict(__name__=__name__, Flask=Flask, jsonify=jsonify, request=request, hmac=hmac, os=os)
        with patch.dict(os.environ, DASHBOARD_TOKEN=self.token):
            exec(compile(section, 'main.py:dashboard-auth', 'exec'), self.ns)
        self.app = self.ns['app']
        self.app.testing = True
        self.app.add_url_rule('/', 'home', lambda: 'private dashboard')
        self.app.add_url_rule('/api/status', 'status', lambda: jsonify(private=True), methods=['GET', 'POST'])
        self.client = self.app.test_client()

    def login(self):
        return self.client.get('/?token=' + self.token + '&tab=jobs', base_url='https://localhost')

    def test_root_and_health_expose_only_health(self):
        for path in ['/', '/healthz']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['service'], 'myjob-ai-bot')
            self.assertNotIn('private', response.get_data(as_text=True))
        self.assertEqual(self.client.get('/api/status').status_code, 401)
        self.assertEqual(self.client.get('/?token=wrong').status_code, 401)

    def test_login_strips_secret_and_authenticates_ajax(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/?tab=jobs')
        cookie = response.headers['Set-Cookie']
        for flag in ['Secure', 'HttpOnly', 'SameSite=Strict']:
            self.assertIn(flag, cookie)
        self.assertNotIn(self.token, cookie)
        self.assertEqual(self.client.get('/', base_url='https://localhost').data, b'private dashboard')
        self.assertTrue(self.client.get('/api/status', base_url='https://localhost').json['private'])

    def test_cookie_mutations_require_same_origin(self):
        self.login()
        for headers in [{}, {'Origin': 'https://evil.example'}]:
            self.assertEqual(self.client.post('/api/status', base_url='https://localhost', headers=headers).status_code, 403)
        self.assertEqual(self.client.post('/api/status', base_url='https://localhost', headers={'Origin': 'https://localhost'}).status_code, 200)

    def test_tls_proxy_uses_secure_cookie_and_origin(self):
        response = self.client.get('/?token=' + self.token, headers={'X-Forwarded-Proto': 'https'})
        self.assertIn('Secure', response.headers['Set-Cookie'])
        response = self.client.post('/api/status', headers={'X-Forwarded-Proto': 'https', 'Origin': 'https://localhost'})
        self.assertEqual(response.status_code, 200)

    def test_api_headers_remain_supported(self):
        for headers in [{'X-Admin-Token': self.token}, {'Authorization': 'Bearer ' + self.token}]:
            self.assertEqual(self.client.post('/api/status', headers=headers).status_code, 200)
        self.assertEqual(self.client.get('/api/status', headers={'X-Admin-Token': '☃'}).status_code, 401)
        self.assertEqual(self.client.get('/api/status?token=' + self.token).status_code, 200)

    def test_expired_tampered_and_rotated_sessions_rejected(self):
        with patch('time.time', return_value=1):
            old = URLSafeTimedSerializer(self.token, salt='dashboard-session').dumps('admin')
        for cookie in [old, 'tampered']:
            self.client.set_cookie('dashboard_session', cookie)
            self.assertEqual(self.client.get('/api/status').status_code, 401)
        self.login()
        self.ns['DASHBOARD_TOKEN'] = 'rotated'
        self.assertEqual(self.client.get('/api/status', base_url='https://localhost').status_code, 401)

    def test_disabled_dashboard_fails_closed_and_headers_prevent_caching(self):
        self.ns['DASHBOARD_TOKEN'] = ''
        self.assertEqual(self.client.get('/api/status').status_code, 503)
        response = self.client.get('/healthz')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(response.headers['X-Robots-Tag'], 'noindex, nofollow')

    def test_explicit_bad_token_does_not_fall_back_to_cookie(self):
        self.login()
        self.assertEqual(self.client.get('/api/status', base_url='https://localhost', headers={'X-Admin-Token': 'wrong'}).status_code, 401)


if __name__ == '__main__':
    unittest.main()
