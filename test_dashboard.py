"""Offline Flask regressions. No polling workers, messages or applications."""
import csv
import importlib
import io
from pathlib import Path
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


def test_download_helper_keeps_token_out_of_url(dashboard):
    _, client = dashboard
    html = client.get('/?token=offline-admin').get_data(as_text=True)
    # The admin token must travel in the X-Admin-Token header, never in a URL
    # that ends up in browser history or access logs.
    assert "url.searchParams.set('token'" not in html
    assert 'async function downloadAdminFile' in html
    assert "headers.set('X-Admin-Token', adminToken)" in html


def test_logs_route_escapes_and_hides_errors(dashboard):
    _, client = dashboard
    auth = {'X-Admin-Token': 'offline-admin'}
    assert client.get('/logs').status_code == 401
    with open('debug.log', 'w', encoding='utf-8') as handle:
        handle.write('<script>alert(1)</script>\n')
    response = client.get('/logs', headers=auth)
    assert response.status_code == 200
    assert '<script>alert(1)</script>' not in response.get_data(as_text=True)
    assert '&lt;script&gt;' in response.get_data(as_text=True)

    with patch('builtins.open', side_effect=OSError('secret-path')):
        failed = client.get('/logs', headers=auth)
    assert failed.status_code == 500
    assert 'secret-path' not in failed.get_data(as_text=True)


def test_api_errors_do_not_leak_exception_details(dashboard):
    _, client = dashboard
    auth = {'X-Admin-Token': 'offline-admin'}
    # A failing resume build must not echo the exception text to the client.
    with patch('subprocess.run', side_effect=OSError('/private/path/generate_resume.py')):
        response = client.post('/api/regenerate_resume', headers=auth)
    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'error'
    assert 'private' not in body['message']

    # Empty/absent JSON bodies must not crash the route with an AttributeError.
    for path in ('/api/manual_apply', '/api/update_profile', '/api/mark_crm', '/api/add_channel'):
        response = client.post(path, headers=auth, data=b'', content_type='application/json')
        assert response.status_code == 200
        assert response.get_json()['status'] == 'error'


def test_upload_rejects_wrong_extension_case_insensitively(dashboard):
    _, client = dashboard
    auth = {'X-Admin-Token': 'offline-admin'}
    pdf = (io.BytesIO(b'%PDF-1.4 test'), 'resume.PDF')
    response = client.post('/api/upload_resume', headers=auth,
                           data={'resume': pdf}, content_type='multipart/form-data')
    assert response.get_json()['status'] == 'success'

    txt = (io.BytesIO(b'nope'), 'resume.txt')
    response = client.post('/api/upload_resume', headers=auth,
                           data={'resume': txt}, content_type='multipart/form-data')
    assert response.get_json()['status'] == 'error'

    state = (io.BytesIO(b'{}'), 'state.JSON')
    response = client.post('/api/upload_auth', headers=auth,
                           data={'auth': state}, content_type='multipart/form-data')
    assert response.get_json()['status'] == 'success'


def test_screenshot_route_does_not_traverse_out_of_directory(dashboard, tmp_path):
    _, client = dashboard
    auth = {'X-Admin-Token': 'offline-admin'}
    (tmp_path / 'screenshots').mkdir()
    secret = tmp_path / 'secret.txt'
    secret.write_text('top-secret', encoding='utf-8')
    response = client.get('/screenshots/../secret.txt', headers=auth)
    assert response.status_code in (400, 403, 404)
    assert b'top-secret' not in response.get_data()
