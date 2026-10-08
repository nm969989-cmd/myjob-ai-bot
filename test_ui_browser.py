"""Local Chromium smoke tests; fixtures never contact employers or Telegram."""
import functools
import http.server
import importlib
import json
import threading
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parent


@pytest.fixture
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def job_site():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / 'tn-live-jobs/public'))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()
    thread.join()


def offline_route(route):
    if urlsplit(route.request.url).hostname == '127.0.0.1':
        route.continue_()
    else:
        route.abort()


@pytest.mark.parametrize('width', [320, 390, 1440])
def test_job_site_search_saved_modal_and_motion(browser, job_site, width):
    page = browser.new_page(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/*', offline_route)
    jobs = [dict(id=str(i), title=f'Python Engineer {i}', company='Fixture Company', city='Chennai',
                 verified=True, is_fresher=True, apply_url=f'https://example.com/jobs/{i}',
                 posted_at='2026-10-08', skills=['Python', 'SQL']) for i in range(30)]
    page.route('**/data/jobs.json', lambda route: route.fulfill(content_type='application/json', body=json.dumps(
        dict(jobs=jobs, count=30, new_count=0, generated_at='2026-10-08T00:00:00Z'))))
    page.goto(job_site, wait_until='networkidle')
    assert page.locator('.card').count() == 24
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), page.evaluate("Array.from(document.querySelectorAll('*')).filter(el => el.getBoundingClientRect().right > innerWidth).map(el => [el.tagName, el.className, el.getBoundingClientRect().right]).slice(0, 20)")
    assert page.locator('.card').first.evaluate("el => getComputedStyle(el).animationName") == 'none'
    page.locator('#search').fill('Python Engineer 29')
    page.wait_for_timeout(350)
    assert page.locator('.card').count() == 1
    page.locator('.btn-bookmark').click()
    assert page.locator('.btn-bookmark').get_attribute('aria-pressed') == 'true'
    page.locator('.btn-details').click()
    assert page.locator('#modalClose').evaluate('el => el === document.activeElement')
    page.keyboard.press('Shift+Tab')
    assert page.locator('#modalApplyBtn').evaluate('el => el === document.activeElement')
    page.keyboard.press('Tab')
    assert page.locator('#modalClose').evaluate('el => el === document.activeElement')
    page.keyboard.press('Escape')
    assert page.locator('#jobModal').get_attribute('aria-hidden') == 'true'
    assert page.locator('.btn-details').evaluate('el => el === document.activeElement')
    page.locator('[data-chip="saved"]').click()
    page.locator('.btn-bookmark').click()
    assert page.locator('.card').count() == 0
    assert not errors
    page.close()


def test_dashboard_browser_preserves_api_auth(browser, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in ('TELEGRAM_TOKEN', 'TELEGRAM_BOT_TOKEN', 'GEMINI_API_KEY', 'GROQ_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    main = importlib.import_module('main')
    monkeypatch.setattr(main, 'DASHBOARD_TOKEN', 'offline-admin')
    server = make_server('127.0.0.1', 0, main.app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page = browser.new_page()
    page.route('**/*', offline_route)
    try:
        page.goto(f'http://127.0.0.1:{server.server_port}/?token=offline-admin', wait_until='networkidle')
        assert page.evaluate("async () => (await adminFetch('api/status')).status") == 200
        assert page.evaluate("async () => (await adminFetch('api/radar')).status") == 200
        assert page.evaluate("() => { try { adminFetch('https://example.com/api'); return false; } catch(e) { return true; } }")
    finally:
        page.close()
        server.shutdown()
        server.server_close()
        thread.join()
