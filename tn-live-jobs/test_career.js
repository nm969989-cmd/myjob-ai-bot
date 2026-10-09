'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const C = require('../docs/career/core');
const { writeOutputs } = require('./src/export');
const example = { title: 'Python Developer', company: 'Example', city: 'Puducherry', skills: ['Python'], description: 'JavaScript', experience: '1-3 years', salary: '6-8 LPA', apply_url: 'https://example.org/job/1' };

test('ranking explains exact skills and location aliases without inventing unknown values', () => {
  const result = C.match(example, { skills: ['Python', 'Java'], cities: ['Pondicherry'], experience: 2, minSalary: 5 });
  assert.equal(result.score, 75);
  assert.ok(result.reasons.includes('Skills found: Python'));
  assert.deepEqual(result.missing, ['Java']);
  assert.equal(C.match(example, {}).score, null);
  assert.ok(C.match({ ...example, salary: '' }, { minSalary: 5 }).reasons.includes('Comparable annual salary not stated'));
});

test('resume comparison finds gaps and only proposes truthful evidence', () => {
  const result = C.compareResume('Built Python services with SQL', 'Python, JavaScript, Kubernetes, SQL');
  assert.deepEqual(result.matched.sort(), ['Python', 'SQL']);
  assert.ok(result.missing.includes('Kubernetes'));
  assert.ok(!result.missing.includes('Java'));
  assert.ok(result.suggestions.some(s => s.includes('only if')));
});

test('expiry is explicit, invalid dates stay unknown, and historical checks are stale', () => {
  const now = new Date('2026-10-09T12:00:00Z');
  assert.equal(C.freshness({ deadline: '2026-10-08' }, now).expired, true);
  assert.equal(C.freshness({ deadline: '2026-10-09' }, now).expired, false);
  assert.equal(C.freshness({ verify_reason: 'http_404' }, now).expired, true);
  assert.equal(C.freshness({ verify_reason: 'request_failed' }, now).expired, false);
  assert.equal(C.date('2026-02-31'), null);
  assert.equal(C.date('Upcoming Saturday'), null);
  assert.equal(C.freshness({ verified_at: '2026-08-01' }, now).stale, true);
});

test('backup normalizes stable URL identities and rejects unsafe or malformed data', () => {
  const state = C.initial();
  state.applications.a = { job: { ...example, apply_url: 'https://example.org/job/1/?utm_source=test' }, status: 'Interview', notes: '<script>literal note</script>', followUp: '2026-10-10' };
  const clean = C.cleanState(state);
  assert.equal(Object.keys(clean.applications)[0], 'https://example.org/job/1');
  assert.equal(clean.applications['https://example.org/job/1'].notes, '<script>literal note</script>');
  state.applications.a.job.apply_url = 'javascript:alert(1)';
  assert.throws(() => C.cleanState(state), /HTTP/);
  assert.throws(() => C.cleanState({ version: 2 }), /version 1/);
  const bad = C.initial(); bad.alerts.timezone = 'invalid-zone';
  assert.throws(() => C.cleanState(bad), /timezone/);
});

test('published feed excludes expired verified jobs while raw archive retains them', () => {
  const rootDir = fs.mkdtempSync(path.join(os.tmpdir(), 'career-export-'));
  try {
    writeOutputs({ rootDir, allJobs: [{ ...example, id: 'closed', verified: true, deadline: '2000-01-01' }, { ...example, id: 'open', verified: true }], newJobs: [], removedJobs: [], history: {}, meta: {}, previousVerifiedCount: 0, rawScrapedCount: 2 });
    assert.equal(JSON.parse(fs.readFileSync(path.join(rootDir, 'public/data/jobs.json'))).count, 1);
    assert.equal(JSON.parse(fs.readFileSync(path.join(rootDir, 'data/jobs.json'))).count, 2);
  } finally { fs.rmSync(rootDir, { recursive: true, force: true }); }
});

test('both public deployments ship identical career and offline assets', () => {
  for (const file of ['career/core.js', 'career/workspace.js', 'career/workspace.css', 'career/icon-192.png', 'career/icon-512.png', 'sw.js', 'offline.html', 'manifest.webmanifest']) {
    assert.deepEqual(fs.readFileSync(path.join(__dirname, '../docs', file)), fs.readFileSync(path.join(__dirname, 'public', file)), file);
  }
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/manifest.webmanifest')));
  assert.equal(manifest.start_url, './');
  assert.equal(manifest.scope, './');
});
