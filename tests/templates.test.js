/**
 * Regression tests for the Flask-served Telegram Mini App (templates/miniapp.html).
 *
 * The mini app renders job rows that come from scraped sources, so these tests
 * feed it deliberately hostile data and assert it stays inert.
 *
 * Run with:  npm install && npm run test:docs
 */
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');

const TEMPLATE = path.join(__dirname, '..', 'templates', 'miniapp.html');

const HOSTILE_JOBS = [
  {
    id: 'x1',
    company: '<img src=x onerror=alert(1)>Evil Corp',
    role: "Senior Dev's Assistant",
    location: 'Chennai',
    is_tamil_nadu: true,
    batch: '2025 Batch',
    salary: '\u20b96 LPA',
    work_mode: 'On-site',
    link: 'javascript:alert(1)',
    source: "@chan'nel",
    summary: '<script>alert(2)</script> not a real summary'
  },
  {
    id: 'x2',
    company: 'Legit Ltd',
    role: 'Backend Engineer',
    location: 'Coimbatore',
    is_tamil_nadu: true,
    batch: '2025 Batch',
    salary: '\u20b98 LPA',
    work_mode: 'Hybrid',
    link: "https://example.com/apply?a=1&b='quoted'",
    source: '@goodchannel',
    summary: 'Normal description'
  }
];

async function loadMiniApp() {
  const html = fs.readFileSync(TEMPLATE, 'utf8');
  const errors = [];
  const opened = [];

  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (err) => errors.push(err));

  const dom = new JSDOM(html, {
    url: 'https://myjob-radar.test/miniapp',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole,
    beforeParse(window) {
      window.lucide = { createIcons() {} };
      window.fetch = async () => ({ ok: true, json: async () => ({ jobs: HOSTILE_JOBS }) });
      window.open = (url) => { opened.push(url); return null; };
    }
  });

  if (dom.window.document.readyState !== 'complete') {
    await new Promise((resolve) => dom.window.addEventListener('load', resolve, { once: true }));
  }
  // Let the DOMContentLoaded fetch/await chain settle.
  await new Promise((resolve) => setTimeout(resolve, 60));
  return { window: dom.window, document: dom.window.document, errors, opened };
}

test('mini app renders fetched jobs without executing injected markup', async () => {
  const { document, errors } = await loadMiniApp();

  const cards = document.querySelectorAll('#jobFeed article');
  assert.equal(cards.length, 2, 'both hostile and legitimate jobs should render as cards');

  assert.equal(document.querySelectorAll('#jobFeed img, #jobFeed script').length, 0,
    'injected <img>/<script> from scraped data must not become elements');
  assert.match(document.getElementById('jobFeed').textContent, /<img src=x onerror=alert\(1\)>Evil Corp/,
    'the hostile company name should appear as literal text');
  assert.equal(errors.length, 0, `unexpected jsdom errors: ${errors.map(String).join(', ')}`);
});

test('mini app never exposes a javascript: URL as an action target', async () => {
  const { document } = await loadMiniApp();

  const targets = [...document.querySelectorAll('#jobFeed [data-apply-url]')]
    .map((el) => el.getAttribute('data-apply-url'));
  assert.ok(targets.length > 0, 'expected apply buttons');
  for (const t of targets) {
    assert.doesNotMatch(t.toLowerCase(), /^javascript:/, 'javascript: URL leaked into the DOM');
  }
  assert.equal(document.querySelectorAll('a[href^="javascript:" i]').length, 0);
});

test('apply button passes the exact URL through for legitimate links', async () => {
  const { window, document, opened } = await loadMiniApp();

  const applyButtons = [...document.querySelectorAll('#jobFeed [data-apply-url]')];
  const legit = applyButtons.find((b) => b.dataset.applyUrl.startsWith('https://example.com'));
  assert.ok(legit, 'expected the legitimate apply button');

  legit.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
  assert.deepEqual(opened, ["https://example.com/apply?a=1&b='quoted'"],
    'a quoted URL must survive intact instead of breaking the handler');
});

test('every inline handler in the mini app compiles', async () => {
  const { document } = await loadMiniApp();

  const broken = [];
  for (const el of document.querySelectorAll('*')) {
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

test('mini app keeps its accessibility affordances', async () => {
  const { document } = await loadMiniApp();

  assert.match(document.documentElement.outerHTML, /class="skip-link"/);
  const viewport = document.querySelector('meta[name="viewport"]').getAttribute('content');
  assert.doesNotMatch(viewport, /user-scalable=no/i);
  assert.equal(document.getElementById('refreshBtn').getAttribute('aria-label'), 'Refresh job feed');
  assert.equal(document.getElementById('filter-all').getAttribute('aria-pressed'), 'true');
  assert.equal(document.getElementById('jobFeed').getAttribute('aria-busy'), 'false',
    'busy state clears once the feed renders');
});
