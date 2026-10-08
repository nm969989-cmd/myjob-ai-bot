'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function client() {
  const context = vm.createContext({
    URL, URLSearchParams, console,
    document: { addEventListener() {}, documentElement: { setAttribute() {} } },
    window: { location: {search: '?fresh=3d'}, history: {replaceState() {}}, matchMedia: () => ({matches: false}) },
    localStorage: {getItem() {throw Error('blocked');}},
  });
  vm.runInContext(fs.readFileSync(__dirname + '/public/app.js', 'utf8'), context);
  return code => vm.runInContext(code, context);
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
