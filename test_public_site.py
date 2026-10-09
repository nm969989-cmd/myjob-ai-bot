"""Offline Chromium regressions for the GitHub Pages site in docs/.

The page loads Tailwind and Lucide from public CDNs. These tests block every
non-local request and stub Lucide so the suite is deterministic; the page's own
`.hidden` fallback keeps panels and modals hidden without Tailwind. Nothing here
contacts an employer, Telegram, or the dashboard backend.
"""
import functools
import http.server
import threading
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / 'docs'


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture(scope='module')
def public_site():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
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


def open_page(browser, public_site, width=390):
    page = browser.new_page(viewport={'width': width, 'height': 900})
    page.add_init_script("window.lucide = { createIcons() {} };")
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/*', offline_route)
    page.goto(public_site, wait_until='domcontentloaded')
    page.wait_for_selector('#tab-jobs .glass-card')
    return page, errors


def inject_jobs(page, jobs):
    page.evaluate(
        """(jobs) => {
             allJobs = jobs;
             updateMetrics();
             renderCurrentView();
           }""",
        jobs,
    )


def test_head_has_discovery_and_structured_metadata(browser, public_site):
    page, errors = open_page(browser, public_site)
    try:
        head = page.content()
        assert 'property="og:title"' in head
        assert 'name="twitter:card"' in head
        assert 'application/ld+json' in head
        assert '"@type": "WebApplication"' in head
        assert '"@type": "Organization"' in head
        assert page.locator('link[rel="canonical"]').get_attribute('href').endswith('/myjob-ai-bot/')
        assert page.locator('link[rel="icon"]').get_attribute('href') == 'favicon.svg'
        assert not errors
    finally:
        page.close()


def test_search_filter_and_modal_focus_lifecycle(browser, public_site):
    page, errors = open_page(browser, public_site)
    try:
        inject_jobs(page, [
            dict(id='a1', company='Alpha', role='Python Engineer', location='Chennai',
                 salary='₹6 LPA', batch='2025', is_tamil_nadu=True, skills=['Python']),
            dict(id='a2', company='Beta', role='Java Engineer', location='Vellore',
                 salary='₹5 LPA', batch='2025', is_tamil_nadu=True, skills=['Java']),
        ])
        assert page.locator('#tab-jobs .glass-card').count() == 2

        page.locator('#searchInput').fill('Python')
        page.wait_for_timeout(250)  # handleSearch is debounced
        assert page.locator('#tab-jobs .glass-card').count() == 1

        page.locator('#searchInput').fill('')
        page.wait_for_timeout(250)
        page.locator('#tab-jobs .glass-card').first.locator('button:has-text("Details")').click()

        modal = page.locator('#jobDetailsModal')
        assert modal.get_attribute('aria-modal') == 'true'
        assert page.locator('#modalCloseBtn').evaluate('el => el === document.activeElement')

        # Tab is trapped inside the dialog.
        page.keyboard.press('Shift+Tab')
        assert modal.evaluate('el => el.contains(document.activeElement)')

        page.keyboard.press('Escape')
        assert modal.evaluate('el => el.classList.contains("hidden")')
        assert page.locator('#tab-jobs .glass-card').first.locator('button:has-text("Details")').evaluate(
            'el => el === document.activeElement')
        assert not errors
    finally:
        page.close()


def test_quote_bearing_scraped_values_cannot_break_inline_handlers(browser, public_site):
    """Scraped role/company strings are inlined into onclick handlers; a quote
    used to escape the JS string. Verify the payload stays inert."""
    page, errors = open_page(browser, public_site)
    payload = "Engineer'); window.__xss = 1; //"
    try:
        inject_jobs(page, [
            dict(id="a1'); window.__xss = 2; //", company="O'Reilly & Sons",
                 role=payload, location='Chennai', salary='₹6 LPA', batch='2025',
                 is_tamil_nadu=True, skills=['Python'], description='desc'),
        ])
        page.locator('#tab-jobs .glass-card').first.locator('button[title="ATS Match"]').click()
        assert page.evaluate('window.__xss === undefined')
        assert page.locator('#jdInput').input_value().startswith(payload)
        assert page.locator('#tab-jobs .glass-card').first.locator('h3').inner_text().strip() == payload
        assert not errors
    finally:
        page.close()


def test_unsafe_apply_urls_are_not_navigable(browser, public_site):
    page, errors = open_page(browser, public_site)
    try:
        inject_jobs(page, [
            dict(id='x1', company='Evil', role='Engineer', location='Chennai',
                 salary='₹1 LPA', batch='2025', is_tamil_nadu=True,
                 link='javascript:alert(1)', apply_url='javascript:alert(1)'),
        ])
        card = page.locator('#tab-jobs .glass-card').first
        assert card.locator('a[href^="javascript"]').count() == 0
        assert card.locator('[aria-disabled="true"]').count() == 1
        assert not errors
    finally:
        page.close()


def test_in_hand_calculator_follows_new_regime_rebate(browser, public_site):
    page, errors = open_page(browser, public_site)
    try:
        result = page.evaluate(
            """() => {
                 const out = {};
                 updateCtcCalculator(12.5);  // taxable 11.75L -> section 87A rebate
                 out.rebateTax = document.getElementById('ctcTax').innerText;
                 out.rebateMonthly = document.getElementById('ctcInHandMonthly').innerText;
                 updateCtcCalculator(20);    // well above the rebate threshold
                 out.taxedTax = document.getElementById('ctcTax').innerText;
                 return out;
               }"""
        )
        assert result['rebateTax'] == '₹0 (Rebate)'
        assert result['taxedTax'].startswith('-₹')
        assert not errors
    finally:
        page.close()


def test_reduced_motion_disables_entrance_animations(browser, public_site):
    page = browser.new_page(viewport={'width': 390, 'height': 900}, reduced_motion='reduce')
    page.add_init_script("window.lucide = { createIcons() {} };")
    page.route('**/*', offline_route)
    page.goto(public_site, wait_until='domcontentloaded')
    page.wait_for_selector('#tab-jobs .glass-card')
    try:
        inject_jobs(page, [
            dict(id='r1', company='Alpha', role='Engineer', location='Chennai',
                 salary='₹6 LPA', batch='2025', is_tamil_nadu=True),
        ])
        page.evaluate('renderCurrentView({ animate: true })')
        assert page.locator('#tab-jobs .glass-card').first.evaluate(
            'el => getComputedStyle(el).animationName') == 'none'
    finally:
        page.close()


def test_back_to_top_appears_only_after_scrolling(browser, public_site):
    page, errors = open_page(browser, public_site)
    try:
        inject_jobs(page, [
            dict(id=f'j{i}', company='Alpha', role=f'Engineer {i}', location='Chennai',
                 salary='₹6 LPA', batch='2025', is_tamil_nadu=True) for i in range(40)
        ])
        assert page.locator('#backToTop').evaluate('el => el.classList.contains("hidden")')
        page.evaluate('window.scrollTo(0, 1200)')
        page.wait_for_timeout(100)
        assert not page.locator('#backToTop').evaluate('el => el.classList.contains("hidden")')
        page.locator('#backToTop').click()
        assert not errors
    finally:
        page.close()


def test_no_horizontal_overflow_at_mobile_width(browser, public_site):
    page, errors = open_page(browser, public_site, width=320)
    try:
        inject_jobs(page, [
            dict(id='m1', company='Alpha', role='Senior Software Engineer', location='Chennai',
                 salary='₹6 LPA', batch='2025', is_tamil_nadu=True, skills=['Python', 'SQL']),
        ])
        page.locator('#jobDetailsModal').evaluate('el => el.classList.remove("hidden")')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        assert not errors
    finally:
        page.close()
