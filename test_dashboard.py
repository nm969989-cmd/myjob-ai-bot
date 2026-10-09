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
    assert client.get('/healthz').status_code == 200  # nosec B101
    assert client.get('/api/status').status_code == 401  # nosec B101
    assert client.post('/api/pause').status_code == 401  # nosec B101
    response = client.get('/api/status', headers={'X-Admin-Token': 'offline-admin'})
    assert response.status_code == 200  # nosec B101
    assert response.headers['Cache-Control'] == 'no-store'  # nosec B101
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'  # nosec B101
    assert client.get('/api/status', headers={'Authorization': 'Bearer offline-admin'}).status_code == 200  # nosec B101
    monkeypatch.setattr(module, 'DASHBOARD_TOKEN', '')
    assert client.get('/api/status').status_code == 503  # nosec B101
    assert client.get('/healthz').status_code == 200  # nosec B101


def test_dashboard_renders_and_escapes_saved_jobs(dashboard):
    _, client = dashboard
    with open('applied_jobs_log.csv', 'w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(['date', 'title', 'url', 'status'])
        writer.writerow(['<b>date</b>', '<img src=x onerror=alert(1)>', 'javascript:alert(1)', 'Applied'])
    response = client.get('/?token=offline-admin')
    assert response.status_code == 200  # nosec B101
    html = response.get_data(as_text=True)
    assert '&lt;img' in html  # nosec B101
    assert 'href="javascript:' not in html  # nosec B101
    assert 'function adminFetch' in html  # nosec B101
    assert 'X-Admin-Token' in html  # nosec B101


def test_template_failure_is_http_error(dashboard):
    _, client = dashboard
    with patch('builtins.open', side_effect=OSError('private path')):
        response = client.get('/?token=offline-admin')
    assert response.status_code == 500  # nosec B101
    assert 'private path' not in response.get_data(as_text=True)  # nosec B101


def test_miniapp_aliases(dashboard):
    _, client = dashboard
    for path in ['/app', '/miniapp']:
        response = client.get(path + '?token=offline-admin')
        assert response.status_code == 200  # nosec B101
        assert 'X-Admin-Token' in response.get_data(as_text=True)  # nosec B101


@pytest.mark.parametrize('path', [
    '/api/manual_apply',
    '/api/update_profile',
    '/api/add_channel',
    '/api/mark_crm',
])
def test_json_endpoints_reject_missing_body_without_500(dashboard, path):
    """A POST with no JSON body used to raise AttributeError on request.json=None."""
    _, client = dashboard
    headers = {'X-Admin-Token': 'offline-admin'}
    empty = client.post(path, headers=headers)
    assert empty.status_code == 200  # nosec B101
    assert empty.get_json()['status'] == 'error'  # nosec B101
    wrong_type = client.post(path, headers=headers, data='not json',
                             content_type='text/plain')
    assert wrong_type.status_code == 200  # nosec B101
    assert wrong_type.get_json()['status'] == 'error'  # nosec B101
