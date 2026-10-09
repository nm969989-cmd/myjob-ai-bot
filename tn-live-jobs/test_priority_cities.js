'use strict';
// Offline tests: no portal requests or scraping CLI execution.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const config = require('./src/config');
const { detectCity } = require('./src/util');
const { sortJobs, toCsv, CSV_COLUMNS } = require('./src/export');
const { computeDiff, appendHistory, readJobFile } = require('./src/diff');
const { buildReport } = require('./src/report');
const util = require('./src/util');

test('preferred cities are searched first without duplicates', () => {
  assert.deepEqual(config.CITIES.slice(0, 4), ['Tiruvannamalai', 'Vellore', 'Puducherry', 'Chennai']);
  assert.equal(new Set(config.CITIES).size, config.CITIES.length);
  assert.ok(config.CITIES.includes('Tamil Nadu'));
});

test('aliases resolve to canonical locations', () => {
  assert.equal(config.canonicalCity('thiruannamalai'), 'Tiruvannamalai');
  assert.equal(config.canonicalCity('Pondicherry'), 'Puducherry');
  assert.equal(detectCity('Thiruvannamalai, India'), 'Tiruvannamalai');
  assert.equal(detectCity('Pondicherry'), 'Puducherry');
});

test('Puducherry search is not restricted to Tamil Nadu', () => {
  assert.equal(config.cityLocation('pondicherry'), 'Puducherry, India');
  assert.equal(config.cityLocation('Chennai'), 'Chennai, Tamil Nadu, India');
});

test('published lists put preferred cities ahead of newer other-city jobs', () => {
  const jobs = [
    { city: 'Coimbatore', title: 'Other', posted_at: '2026-10-05' },
    { city: 'Pondicherry', title: 'Preferred', posted_at: '2026-10-04' },
    { city: 'Vellore', title: 'Preferred newer', posted_at: '2026-10-05' },
  ];
  assert.deepEqual(sortJobs(jobs).map((job) => job.city), ['Vellore', 'Pondicherry', 'Coimbatore']);
  assert.equal(jobs[0].city, 'Coimbatore');
});

// ---------------------------------------------------------------------------
// Export / CSV
// ---------------------------------------------------------------------------

test('CSV export quotes separators and neutralises spreadsheet formulas', () => {
  const csv = toCsv([
    { id: 'a', title: 'Dev, Senior "Lead"', company: '=cmd|calc' },
    { id: 'b', title: '+1234567890', company: 'Acme' },
  ]);
  // Excel needs the BOM to read the file as UTF-8.
  assert.equal(csv.charCodeAt(0), 0xfeff);
  assert.ok(csv.slice(1).startsWith(CSV_COLUMNS.join(',')));
  assert.ok(csv.includes('"Dev, Senior ""Lead"""'));
  assert.ok(csv.includes("'=cmd|calc"));
  assert.ok(csv.includes("'+1234567890"));
});

test('CSV export keeps every job on its own row', () => {
  const csv = toCsv([{ id: 'a', title: 'One' }, { id: 'b', title: 'Two' }]);
  const rows = csv.split(/\r\n/).filter(Boolean);
  assert.equal(rows.length, 3); // header + 2 jobs
});

// ---------------------------------------------------------------------------
// Diffing and history
// ---------------------------------------------------------------------------

test('computeDiff classifies new, kept and removed jobs by id', () => {
  const current = [{ id: '1' }, { id: '2' }, { id: '3' }];
  const previous = [{ id: '2' }, { id: '3' }, { id: '4' }];
  const result = computeDiff(current, previous);
  assert.deepEqual(result.newJobs.map((job) => job.id), ['1']);
  assert.deepEqual(result.keptJobs.map((job) => job.id), ['2', '3']);
  assert.deepEqual(result.removedJobs.map((job) => job.id), ['4']);
});

test('appendHistory never grows past 500 runs', () => {
  const base = Date.parse('2026-01-01T00:00:00Z');
  let history = {};
  for (let i = 0; i < 505; i += 1) {
    history = appendHistory(history, new Date(base + i * 1000).toISOString(), {
      total: i,
      new: 0,
      verified: i,
    });
  }
  assert.equal(Object.keys(history).length, 500);
});

test('readJobFile treats a missing file as an empty list', () => {
  assert.deepEqual(readJobFile('/tmp/tn-live-jobs-missing-file.json'), []);
});

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------

test('report renders new and gone sections from the CLI diff payload keys', () => {
  const markdown = buildReport({
    meta: {
      started_at: 'start',
      finished_at: 'end',
      duration_seconds: 1,
      trigger: 'local run',
      keywords: ['fresher'],
      cities: ['Chennai'],
      droppedRecords: 0,
    },
    sites: [{ id: 'naukri.com', label: 'Naukri', tier: 2, status: 'ok', detail: '' }],
    sourceCounts: { 'naukri.com': 3 },
    foundCounts: { 'naukri.com': 3 },
    validateStats: {
      checked: 3,
      live: 2,
      documents: 0,
      loginRequired: 0,
      noSignal: 0,
      redirected: 0,
      dead: 1,
      unreachable: 0,
    },
    diff: {
      new_count: 1,
      removed_count: 1,
      new: [{ id: 'n1', title: 'New job', company: 'Acme', city: 'Chennai', category: 'Software', verified: true, apply_url: 'https://example.com/1' }],
      removed: [{ id: 'r1', title: 'Old job', company: 'Beta' }],
    },
    latest: { total: 3, verified: 2, new: 1 },
    guard: null,
  });
  assert.ok(markdown.includes('New this run (1)'));
  assert.ok(markdown.includes('Gone since last run (1)'));
  assert.ok(markdown.includes('Old job'));
});

// ---------------------------------------------------------------------------
// Util helpers
// ---------------------------------------------------------------------------

test('unescapeEntities does not double-decode a literal &amp;lt;', () => {
  assert.equal(util.unescapeEntities('&amp;lt;tag&gt;'), '&lt;tag>');
  assert.equal(util.unescapeEntities('"Quoted &amp; Co"'), 'Quoted & Co');
});

test('cleanUrl drops query, hash and www so a job keeps one id', () => {
  assert.equal(util.cleanUrl('https://www.Example.com/job/1?utm=1#top'), 'https://example.com/job/1');
  assert.equal(util.jobId('https://example.com/job/1?a=1'), util.jobId('https://www.example.com/job/1/'));
});

test('registrableDomain handles multi-part Indian suffixes', () => {
  assert.equal(util.registrableDomain('https://employment.tn.gov.in/x'), 'tn.gov.in');
  assert.equal(util.registrableDomain('https://www.freshersworld.com/x'), 'freshersworld.com');
  assert.equal(util.registrableDomain('not a url'), '');
});

test('timestampToIsoDate accepts seconds and milliseconds only', () => {
  assert.equal(util.timestampToIsoDate(1700000000), '2023-11-14');
  assert.equal(util.timestampToIsoDate(1700000000000), '2023-11-14');
  assert.equal(util.timestampToIsoDate('nonsense'), null);
  assert.equal(util.timestampToIsoDate(0), null);
});

test('detectExperience reads ranges, singles and freshers', () => {
  assert.equal(util.detectExperience('3-5 years experience'), '3-5 years');
  assert.equal(util.detectExperience('2 years'), '2+ years');
  assert.equal(util.detectExperience('Fresher'), 'Fresher');
  assert.equal(util.detectExperience(''), null);
});

test('isFresher only trusts a real fresher signal', () => {
  assert.equal(util.isFresher('0 years', ''), true);
  assert.equal(util.isFresher('Fresher', ''), true);
  assert.equal(util.isFresher('5 years', 'Senior Engineer'), false);
});

test('detectDeadline turns a stated closing date into an ISO date', () => {
  assert.equal(util.detectDeadline('Last date: 14/09/2026'), '2026-09-14');
  assert.equal(util.detectDeadline('No date mentioned here'), null);
});

test('cleanSummary shortens long text without cutting a word in half', () => {
  const out = util.cleanSummary('word '.repeat(100), 50);
  assert.ok(out.length <= 51);
  assert.ok(out.endsWith('\u2026'));
});

// ---------------------------------------------------------------------------
// Frontend pure logic (public/app.js) exercised in a minimal DOM sandbox.
// No browser or extra dependency is needed: app.js only touches `document`
// inside its DOMContentLoaded handler, which is never fired here.
// ---------------------------------------------------------------------------

const vm = require('node:vm');
const fs = require('node:fs');
const nodePath = require('node:path');

function loadAppSandbox() {
  const noop = () => {};
  const makeEl = () => ({
    addEventListener: noop,
    setAttribute: noop,
    getAttribute: () => null,
    appendChild: noop,
    append: noop,
    querySelector: () => makeEl(),
    querySelectorAll: () => [],
    classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
    style: {},
    options: [],
    value: '',
    hidden: false,
  });
  const sandbox = {
    document: {
      addEventListener: noop,
      getElementById: () => makeEl(),
      querySelectorAll: () => [],
      documentElement: { setAttribute: noop, getAttribute: () => 'light' },
      body: { style: {} },
      activeElement: null,
    },
    window: {
      matchMedia: () => ({ matches: false }),
      location: { search: '', pathname: '/', origin: 'https://example.com' },
      history: { replaceState: noop },
      open: noop,
    },
    localStorage: { getItem: () => null, setItem: noop },
    navigator: { clipboard: { writeText: async () => undefined } },
    Option: function Option(text, value) {
      this.text = text;
      this.value = value;
    },
    console,
    setTimeout,
    clearTimeout,
    URLSearchParams,
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  const code = fs.readFileSync(nodePath.join(__dirname, 'public', 'app.js'), 'utf8');
  vm.runInContext(code, sandbox, { filename: 'public/app.js' });
  return sandbox;
}

test('frontend experience filter uses real years, not loose digit matches', () => {
  const app = loadAppSandbox();
  assert.equal(app.matchesExperience({ experience: '10 years' }, 'mid'), false);
  assert.equal(app.matchesExperience({ experience: '10 years' }, 'senior'), true);
  assert.equal(app.matchesExperience({ experience: '2 years' }, 'mid'), true);
  assert.equal(app.matchesExperience({ experience: '2 years' }, 'senior'), false);
  assert.equal(app.matchesExperience({ is_fresher: true }, 'fresher'), true);
  assert.equal(app.matchesExperience({ experience: '' }, 'mid'), false);
});

test('frontend search highlighting escapes HTML and only marks the match', () => {
  const app = loadAppSandbox();
  assert.equal(
    app.highlightText('<b>Java</b> Developer', 'java'),
    '&lt;b&gt;<mark>Java</mark>&lt;/b&gt; Developer'
  );
  assert.equal(app.highlightText('<script>x</script>', ''), '&lt;script&gt;x&lt;/script&gt;');
});

test('frontend only renders http(s) apply links', () => {
  const app = loadAppSandbox();
  assert.equal(app.safeUrl('https://example.com/job/1'), 'https://example.com/job/1');
  assert.equal(app.safeUrl('http://example.com/1'), 'http://example.com/1');
  assert.equal(app.safeUrl('javascript:alert(1)'), '#');
  assert.equal(app.safeUrl('data:text/html,<script>'), '#');
  assert.equal(app.safeUrl(null), '#');
});

