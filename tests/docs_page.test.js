/**
 * Regression tests for the GitHub Pages dashboard (docs/index.html).
 *
 * These load the real page in jsdom with the CDN assets stubbed out, so they
 * exercise the shipped markup + inline application script without network.
 *
 * Run with:  npm install && npm run test:docs
 */
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');

const DOCS_DIR = path.join(__dirname, '..', 'docs');
const PAGE = path.join(DOCS_DIR, 'index.html');
const SNAPSHOT = path.join(DOCS_DIR, 'data', 'snapshot.js');

/**
 * Reads docs/index.html and inlines the external snapshot script, so the page
 * can boot without jsdom fetching anything (the CDN assets are never loaded
 * because `resources` stays at its default).
 */
function buildTestPage() {
  const html = fs.readFileSync(PAGE, 'utf8');
  const tag = '<script src="./data/snapshot.js"></script>';
  // Older revisions embedded the snapshot inline; both shapes are supported so
  // the same suite can be run against a previous commit.
  if (!html.includes(tag)) return html;
  const snapshot = fs.readFileSync(SNAPSHOT, 'utf8');
  return html.replace(tag, `<script>${snapshot}</script>`);
}

async function loadPage() {
  const html = buildTestPage();
  const errors = [];

  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (err) => errors.push(err));

  const dom = new JSDOM(html, {
    // A real (non-opaque) origin: file:// origins have no localStorage in jsdom.
    url: 'https://myjob-radar.test/',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole,
    beforeParse(window) {
      // Stub the CDN globals the page expects.
      window.lucide = { createIcons() {} };
      // Keep the live refresh off the network in tests.
      window.fetch = () => Promise.reject(new Error('network disabled in test'));
    }
  });

  if (dom.window.document.readyState !== 'complete') {
    await new Promise((resolve) => dom.window.addEventListener('load', resolve, { once: true }));
  }
  return { dom, window: dom.window, document: dom.window.document, errors };
}

const tick = (ms = 220) => new Promise((resolve) => setTimeout(resolve, ms));

function click(window, el) {
  el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
}

// ───────────────────────────────────────────────────────────────────────────

test('page boots with no uncaught script errors', async () => {
  const { window, document, errors } = await loadPage();
  assert.equal(document.readyState, 'complete');
  assert.equal(errors.length, 0, `unexpected jsdom errors: ${errors.map(String).join(', ')}`);
  assert.equal(window.INITIAL_DATA.length, 233, 'bundled snapshot must not lose rows');
});

// BUG (fixed): the ATS button used to embed escapeHtml() output inside a JS
// string in an HTML attribute. Browsers decode &#39; back to ' before parsing
// the handler, so any apostrophe (e.g. "Earth's most customer-centric")
// produced a SyntaxError and the button did nothing. This asserts the value
// survives the round trip.
test('ATS button works for listings whose description contains an apostrophe', async () => {
  const { window, document, errors } = await loadPage();

  const input = document.getElementById('searchInput');
  input.value = "Earth's";
  input.dispatchEvent(new window.Event('input', { bubbles: true }));
  await tick(260);

  const atsBtn = document.querySelector('#tab-jobs [data-ats-role]');
  assert.ok(atsBtn, 'expected at least one rendered card with an ATS button');
  assert.match(atsBtn.dataset.atsSummary, /Earth's/);

  click(window, atsBtn);

  const jd = document.getElementById('jdInput').value;
  assert.match(jd, /Earth's most customer-centric/, 'apostrophe must survive into the JD box');
  assert.equal(document.getElementById('tab-ats').classList.contains('hidden'), false, 'ATS tab opens');
  assert.equal(errors.length, 0, `unexpected jsdom errors: ${errors.map(String).join(', ')}`);
});

// BUG (fixed): card handlers used to be built as
//   onclick="populateATSMatcher('${escapeHtml(j.role)}', ...)"
// The HTML parser decodes &#39; back into ' before the browser compiles the
// handler, so any apostrophe in the data produced an invalid handler. This test
// compiles every rendered inline handler exactly like a browser would.
test('every inline handler rendered into the feed is valid JavaScript', async () => {
  const { document } = await loadPage();
  const handlers = [...document.querySelectorAll('#tab-jobs [onclick]')];
  assert.ok(handlers.length > 0, 'expected rendered cards with handlers');

  const broken = [];
  for (const el of handlers) {
    const code = el.getAttribute('onclick');
    try {
      // eslint-disable-next-line no-new-func
      new Function('event', code);
    } catch (err) {
      broken.push({ code, error: String(err) });
    }
  }
  assert.equal(broken.length, 0, `handlers that fail to compile: ${JSON.stringify(broken.slice(0, 2))}`);
});

// BUG (fixed): filterWalkinsCity() read the non-standard global `event`,
// which Safari does not provide, so city chips threw and did nothing there.
test('walk-in city chips filter without relying on window.event', async () => {
  const { window, document, errors } = await loadPage();
  assert.equal(typeof window.event, 'undefined', 'jsdom does not provide window.event (same as Safari)');

  click(window, document.getElementById('nav-walkins'));
  await tick(30);

  const before = document.querySelectorAll('#walkinsFeed .glass-card').length;
  assert.ok(before > 0, 'walk-ins feed should render');

  const chennai = [...document.querySelectorAll('.city-btn')].find((b) => b.textContent.trim() === 'Chennai');
  click(window, chennai);
  await tick(30);

  assert.equal(chennai.getAttribute('aria-pressed'), 'true');
  const after = document.querySelectorAll('#walkinsFeed .glass-card').length;
  assert.ok(after <= before, 'filtering must not add cards');
  assert.equal(errors.length, 0, `unexpected jsdom errors: ${errors.map(String).join(', ')}`);
});

test('feed is paginated instead of rendering every match at once', async () => {
  const { window, document } = await loadPage();

  const cards = document.querySelectorAll('#tab-jobs .glass-card');
  assert.ok(cards.length > 0, 'expected rendered cards');
  assert.ok(cards.length <= 40, `expected at most one page of cards, got ${cards.length}`);

  const more = [...document.querySelectorAll('#tab-jobs button')].find((b) => /Show \d+ more/.test(b.textContent));
  assert.ok(more, 'expected a "Show N more" control when more matches exist');

  const before = cards.length;
  click(window, more);
  await tick(30);
  const after = document.querySelectorAll('#tab-jobs .glass-card').length;
  assert.ok(after > before, `load-more should add cards (${before} -> ${after})`);
});

test('javascript: URLs from the feed can never become clickable links', async () => {
  const { window, document } = await loadPage();

  // Same array object the app holds, so the injected row is picked up on re-render.
  window.INITIAL_DATA.unshift({
    id: 'poison-1', company: 'Evil Corp', role: 'XSS Tester',
    location: 'Chennai', is_tamil_nadu: true, is_walkin: false, is_drive: false,
    batch: '2025', salary: 'n/a', link: 'javascript:alert(1)',
    apply_url: 'javascript:alert(1)', maps_url: 'javascript:alert(2)',
    source: 'test', platform: 'test', type: 'tn_job', date_posted: 'now',
    skills: ['a'], description: 'poison'
  });

  click(window, document.getElementById('filter-tn'));
  await tick(30);

  const bad = [...document.querySelectorAll('a')].filter((a) => (a.getAttribute('href') || '').toLowerCase().startsWith('javascript:'));
  assert.equal(bad.length, 0, 'no javascript: href may reach the DOM');
});

test('modals trap focus and close on Escape', async () => {
  const { window, document } = await loadPage();

  const firstCardTitle = document.querySelector('#tab-jobs .glass-card h3');
  click(window, firstCardTitle);
  await tick(30);

  const modal = document.getElementById('jobDetailsModal');
  assert.equal(modal.classList.contains('hidden'), false, 'modal opens');
  assert.equal(modal.getAttribute('aria-hidden'), 'false');
  assert.equal(modal.getAttribute('role'), 'dialog');
  assert.ok(modal.contains(document.activeElement), 'focus moves into the dialog');

  document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await tick(30);
  assert.equal(modal.classList.contains('hidden'), true, 'Escape closes the dialog');
  assert.equal(modal.getAttribute('aria-hidden'), 'true');
});

// Same class of bug as above, but document-wide: parse the page exactly like a
// browser (via jsdom) and compile every inline handler it would hand to the JS
// engine. The static-markup equivalent of this check cannot work, because
// attribute values routinely contain single quotes (e.g. quickSearch('Python')).
test('every inline handler in the document compiles', async () => {
  const { document } = await loadPage();
  const withHandlers = [...document.querySelectorAll('*')].filter((el) =>
    [...el.attributes].some((a) => /^on[a-z]+$/.test(a.name))
  );
  assert.ok(withHandlers.length > 0, 'expected inline handlers in the document');

  const broken = [];
  for (const el of withHandlers) {
    for (const attr of el.attributes) {
      if (!/^on[a-z]+$/.test(attr.name)) continue;
      try {
        // eslint-disable-next-line no-new-func
        new Function('event', attr.value);
      } catch (err) {
        broken.push({ handler: attr.name, code: attr.value, error: String(err) });
      }
    }
  }
  assert.equal(broken.length, 0, `uncompilable handlers: ${JSON.stringify(broken.slice(0, 2))}`);
});

test('tab navigation exposes correct ARIA state', async () => {
  const { window, document } = await loadPage();

  assert.equal(document.getElementById('nav-jobs').getAttribute('aria-selected'), 'true');
  click(window, document.getElementById('nav-drives'));
  await tick(30);

  assert.equal(document.getElementById('nav-drives').getAttribute('aria-selected'), 'true');
  assert.equal(document.getElementById('nav-jobs').getAttribute('aria-selected'), 'false');
  assert.equal(document.getElementById('tab-drives').classList.contains('hidden'), false);
  assert.equal(document.getElementById('tab-jobs').classList.contains('hidden'), true);
});

test('structured data for the listings is injected from real rows', async () => {
  const { document } = await loadPage();
  const el = document.getElementById('jobListJsonLd');
  assert.ok(el, 'ItemList JSON-LD should be present');
  const data = JSON.parse(el.textContent);
  assert.equal(data['@type'], 'ItemList');
  assert.ok(data.itemListElement.length > 0);
  for (const item of data.itemListElement) {
    assert.match(item.url, /^https?:\/\//, 'only real http(s) listings are published as structured data');
  }
});
