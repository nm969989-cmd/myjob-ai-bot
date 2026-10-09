'use strict';
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const http = require('node:http');
const { once } = require('node:events');
const { writeOutputs, toCsv } = require('./src/export');

function browserContext() {
  const context = vm.createContext({
    URL, URLSearchParams, console,
    document: { addEventListener() {} },
    window: { location: { search: '', pathname: '/' }, history: { replaceState(...args) { this.url = args[2]; } } },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'public/app.js'), 'utf8'), context);
  return context;
}

test('freshness excludes undated, invalid and future jobs, including ISO timestamps', () => {
  const ctx = browserContext();
  for (const posted_at of [null, 'invalid', '2099-01-01']) {
    ctx.job = { posted_at };
    assert.equal(vm.runInContext("matchesFreshness(job, '24h')", ctx), false);
  }
  ctx.job = { posted_at: new Date(Date.now() - 2 * 3600000).toISOString() };
  assert.equal(vm.runInContext("matchesFreshness(job, '24h')", ctx), true);
  ctx.job.posted_at = new Date(Date.now() - 25 * 3600000).toISOString();
  assert.equal(vm.runInContext("matchesFreshness(job, '24h')", ctx), false);
});

test('shared URL preserves freshness and search together', () => {
  const ctx = browserContext();
  vm.runInContext("window.location.search = '?q=python&fresh=3d'; readUrlParams(); updateUrlParams()", ctx);
  assert.equal(vm.runInContext('window.history.url', ctx), '/?q=python&fresh=3d');
});

test('removing a saved job reapplies the Saved filter', () => {
  const ctx = browserContext();
  vm.runInContext(`
    state.quickChip = 'saved'; state.savedIds.add('job');
    showToast = persistSavedIds = () => {};
    applyFilters = () => { state.filteredJobs = [{ id: 'job' }].filter(j => matchesQuickChip(j, 'saved')); };
    toggleSaveJob('job');
  `, ctx);
  assert.equal(vm.runInContext('state.filteredJobs.length', ctx), 0);
});

test('theme initializes even when storage is disabled', () => {
  const ctx = browserContext();
  vm.runInContext(`
    localStorage = { getItem() { throw new Error('blocked'); } };
    document.documentElement = { setAttribute(name, value) { this.theme = value; } };
    initTheme();
  `, ctx);
  assert.equal(vm.runInContext('document.documentElement.theme', ctx), 'light');
});

test('job URLs reject executable schemes and attributes escape scraped markup', () => {
  const ctx = browserContext();
  ctx.job = { id: '"><script>', title: '<img onerror=alert(1)>', apply_url: 'javascript:alert(1)' };
  const card = vm.runInContext('createCardHtml(job)', ctx);
  assert.ok(!card.includes('<img'));
  assert.ok(!card.includes('javascript:'));
  assert.match(card, /href="#"/);
  assert.equal(vm.runInContext("safeUrl('https://example.com/job')", ctx), 'https://example.com/job');
});

test('CSV download is published, contains verified jobs only and neutralizes formulas', () => {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'myjob-export-'));
  try {
    const live = { id: 'live', title: '=HYPERLINK("https://bad.example")', verified: true };
    writeOutputs({ rootDir, allJobs: [live, { id: 'dead', verified: false }], newJobs: [live], removedJobs: [], history: {}, meta: { finished_at: '2026-10-09' }, previousVerifiedCount: 0, rawScrapedCount: 2 });
    const csv = fs.readFileSync(path.join(rootDir, 'public/data/jobs.csv'), 'utf8');
    assert.match(csv, /live/);
    assert.doesNotMatch(csv, /\r\ndead,/);
    assert.match(csv, /'=HYPERLINK/);
    const previous = fs.readFileSync(path.join(rootDir, 'data/jobs.json'), 'utf8');
    const result = writeOutputs({ rootDir, allJobs: [], newJobs: [], removedJobs: [], history: {}, meta: {}, previousVerifiedCount: 1, rawScrapedCount: 0 });
    assert.equal(result.wroteData, false);
    assert.equal(fs.readFileSync(path.join(rootDir, 'data/jobs.json'), 'utf8'), previous);
    for (const title of ['+SUM(1,2)', '@SUM(1)', '-1+2', '\t=1', '  =1']) {
      assert.ok(toCsv([{ title }]).includes("'" + title.replaceAll('"', '""')));
    }
  } finally { fs.rmSync(rootDir, { recursive: true, force: true }); }
});

test('preview handles malformed and sibling-directory paths without crashing', async () => {
  const { runServe } = require('./src/cli');
  // Let the OS allocate a free port for this isolated test server.
  const server = runServe(0);
  try {
    await once(server, 'listening');
    const port = server.address().port;
    const get = requestPath => new Promise((resolve, reject) => {
      http.get({ hostname: 'localhost', port, path: requestPath }, response => {
        response.resume(); response.on('end', () => resolve(response.statusCode));
      }).on('error', reject);
    });
    assert.equal(await get('/%E0%A4%A'), 400);
    assert.equal(await get('/%00'), 400);
    assert.equal(await get('/../public-private/secret'), 403);
    assert.equal(await get('/missing.html'), 404);
    assert.equal(await get('/'), 200);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
