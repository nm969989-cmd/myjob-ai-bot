"""Offline Flask regressions. No polling workers, messages or applications."""
import csv
import importlib
from unittest.mock import patch

import pytest


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in ('TELEGRAM_TOKEN', 'TELEGRAM_BOT_TOKEN', 'GEMINI_API_KEY', 'GROQ_API_KEY', 'NOTION_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    module = importlib.import_module('main')
    monkeypatch.setattr(module, 'DASHBOARD_TOKEN', 'offline-admin')
    return module, module.app.test_client()


def test_auth_boundaries(dashboard, monkeypatch):
    module, client = dashboard
    assert client.get('/healthz').status_code == 200
    assert client.get('/api/status').status_code == 401
    assert client.post('/api/pause').status_code == 401
    response = client.get('/api/status', headers={'X-Admin-Token': 'offline-admin'})
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert client.get('/api/status', headers={'Authorization': 'Bearer offline-admin'}).status_code == 200
    monkeypatch.setattr(module, 'DASHBOARD_TOKEN', '')
    assert client.get('/api/status').status_code == 503
    assert client.get('/healthz').status_code == 200


def test_dashboard_renders_and_escapes_saved_jobs(dashboard):
    _, client = dashboard
    with open('applied_jobs_log.csv', 'w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(['date', 'title', 'url', 'status'])
        writer.writerow(['<b>date</b>', '<img src=x onerror=alert(1)>', 'javascript:alert(1)', 'Applied'])
    response = client.get('/?token=offline-admin')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '&lt;img' in html
    assert 'href="javascript:' not in html
    assert 'function adminFetch' in html
    assert 'X-Admin-Token' in html


def test_template_failure_is_http_error(dashboard):
    _, client = dashboard
    with patch('builtins.open', side_effect=OSError('private path')):
        response = client.get('/?token=offline-admin')
    assert response.status_code == 500
    assert 'private path' not in response.get_data(as_text=True)


def test_miniapp_aliases(dashboard):
    _, client = dashboard
    for path in ['/app', '/miniapp']:
        response = client.get(path + '?token=offline-admin')
        assert response.status_code == 200
        assert 'X-Admin-Token' in response.get_data(as_text=True)
