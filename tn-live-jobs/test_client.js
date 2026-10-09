'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function client(search = '?fresh=3d') {
  class Option {
    constructor(text, value) { this.text = text; this.value = value; }
  }
  function makeSelect() {
    const options = [];
    return { options, value: '', append(option) { options.push(option); } };
  }
  const context = vm.createContext({
    URL, URLSearchParams, console, Option, makeSelect,
    document: { addEventListener() {}, documentElement: { setAttribute() {} }, getElementById: () => undefined },
    window: { location: { search }, history: { replaceState() {} }, matchMedia: () => ({ matches: false }) },
    localStorage: { getItem() { throw Error('blocked'); } },
  });
  vm.runInContext(fs.readFileSync(__dirname + '/public/app.js', 'utf8'), context);
  return code => vm.runInContext(code, context);
}

// Load a couple of jobs and wire the two data-driven dropdowns, so URL values
// can be validated the same way the page does it.
function withFilters(search) {
  const run = client(search);
  run("state.allJobs=[{city:'Chennai',category:'Software'},{city:'Madurai',category:'Sales & Marketing'}];");
  run('els.city=makeSelect(); els.category=makeSelect();');
  run('populateFilterOptions();');
  return run;
}

test('blocked storage does not prevent theme initialization', () => { client()('initTheme()'); });
test('only http and https application links are navigable', () => {
  const run = client();
  assert.equal(run("safeApplyUrl('javascript:alert(1)')"), '#');
  assert.equal(run("safeApplyUrl('https://example.com/jobs')"), 'https://example.com/jobs');
});
test('repeated adjacent search matches are all highlighted safely', () => {
  const run = client();
  assert.equal(run("highlightText('PythonPython <script>', 'python')"), '<mark>Python</mark><mark>Python</mark> &lt;script&gt;');
});
test('freshness filters are restored from shareable URLs', () => {
  assert.equal(client()("readUrlParams(); state.freshness"), '3d');
});

test('unknown URL filter values are ignored instead of emptying the board', () => {
  const run = withFilters('?city=Atlantis&cat=Spaceships&chip=bogus&exp=wizard&fresh=99h&sort=nonsense');
  run('readUrlParams();');
  assert.equal(run('state.city'), '');
  assert.equal(run('state.category'), '');
  assert.equal(run('state.quickChip'), 'all');
  assert.equal(run('state.experience'), '');
  assert.equal(run('state.freshness'), '');
  assert.equal(run('state.sort'), 'newest');
});

test('URL filter values are matched case-insensitively and to real options', () => {
  const run = withFilters('?city=chennai&cat=software&type=full-time&chip=IT');
  run('readUrlParams();');
  assert.equal(run('state.city'), 'Chennai');
  assert.equal(run('state.category'), 'Software');
  assert.equal(run('state.type'), 'Full-time');
  assert.equal(run('state.quickChip'), 'it');
});

test('the search term from a link is length-capped', () => {
  const run = withFilters('?q=' + 'a'.repeat(500));
  assert.equal(run('readUrlParams(); state.query.length'), 120);
});
