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


test('duplicate groups preserve different source links and keep ambiguous roles separate', () => {
  const copy = { ...example, apply_url: 'https://another.example/jobs/9', city: 'Pondicherry', title: '  PYTHON Developer ' };
  const groups = C.groupJobs([example, copy, { ...example, apply_url: example.apply_url + '?utm_source=x' }, { ...example, city: 'Chennai' }, { ...example, company: 'Another employer' }, { ...example, company: '', apply_url: 'https://unknown.example/a' }, { ...example, company: '', apply_url: 'https://unknown.example/b' }]);
  assert.equal(groups.length, 5);
  assert.deepEqual(groups[0].sources.map(j => j.url), [example.apply_url, copy.apply_url]);
  assert.equal(C.groupJobs([{ ...example, city: '', apply_url: 'https://example.org/a' }, { ...example, city: '', apply_url: 'https://example.org/b' }]).length, 2);
  assert.equal(C.groupJobs([{ ...example, apply_url: 'javascript:alert(1)' }]).length, 0);
});

test('warning clues explain payment and suspicious links without declaring jobs safe', () => {
  const clues = C.warningSignals({ ...example, description: 'Pay a registration fee before the interview. Guaranteed job.', apply_url: 'http://bit.ly/example' });
  assert.deepEqual(clues.map(c => c.code), ['payment', 'guarantee', 'http', 'short-link']);
  assert.match(clues[0].detail, /registration fee/);
  assert.equal(C.warningSignals({ ...example, description: 'No registration fees. We never request payment for an interview. No guaranteed job.' }).length, 0);
  assert.ok(C.warningSignals({ ...example, description: 'No application fee, but pay a security deposit before joining.' }).some(c => c.code === 'payment'));
  assert.equal(C.warningSignals({ ...example, description: 'Process customer payments using Python.' }).length, 0);
  assert.ok(C.warningSignals({ ...example, company: '', apply_url: 'https://127.0.0.1/job' }).some(c => c.code === 'missing-company'));
  assert.ok(C.warningSignals({ ...example, apply_url: 'https://xn--pple-43d.com/job' }).some(c => c.code === 'unusual-host'));
  assert.equal(C.warningSignals({ ...example, apply_url: 'https://bit.ly.evil.example/job' }).some(c => c.code === 'short-link'), false);
});
