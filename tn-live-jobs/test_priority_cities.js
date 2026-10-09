'use strict';
// Offline tests: no portal requests or scraping CLI execution.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const config = require('./src/config');
const { detectCity } = require('./src/util');
const { sortJobs, buildSitemap, SITE_URL } = require('./src/export');

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

test('search plan covers every preferred city before broad cities', () => {
  const { planSearches } = config;
  const keywords = ['a', 'b', 'c'];
  const cities = ['Tiruvannamalai', 'Vellore', 'Puducherry', 'Chennai', 'Madurai', 'Salem'];
  const plan = planSearches(keywords, cities, 6);

  assert.equal(plan.length, 6);
  // First four searches: the first keyword across all four preferred cities.
  assert.deepEqual(plan.slice(0, 4).map((p) => p.city), ['Tiruvannamalai', 'Vellore', 'Puducherry', 'Chennai']);
  // A small budget still reaches a second keyword, so search is not stuck on
  // one keyword the way the old keyword-outer loop was.
  assert.equal(plan[4].keyword, 'b');
  assert.equal(plan[5].keyword, 'b');
  // Broad cities only appear once every keyword x preferred city is exhausted.
  assert.ok(plan.every((p) => !['Madurai', 'Salem'].includes(p.city)));
});

test('search plan reaches non-preferred cities and every keyword when unlimited', () => {
  const { planSearches } = config;
  const plan = planSearches(['a', 'b'], config.CITIES, 0);
  assert.equal(plan.length, 2 * config.CITIES.length);
  assert.ok(plan.some((p) => p.city === 'Madurai'));
  assert.equal(new Set(plan.map((p) => p.keyword)).size, 2);
  // Preferred cities still come first.
  assert.ok(config.PRIORITY_CITIES.includes(plan[0].city));
});

test('search plan deduplicates repeated cities', () => {
  const { planSearches } = config;
  const plan = planSearches(['a'], ['Chennai', 'chennai', 'Chennai '], 0);
  assert.equal(plan.length, 1);
});

test('every Tamil Nadu locality known to the Python radar is searchable here', () => {
  // The Python bot (job_radar.py) and this scraper must agree on what counts
  // as Tamil Nadu. If a locality is added on one side only, jobs in that city
  // are silently dropped or never searched. Read the Python list directly so
  // the two cannot drift apart unnoticed.
  const radarPath = path.join(__dirname, '..', 'job_radar.py');
  const source = fs.readFileSync(radarPath, 'utf8');
  const block = /TAMIL_NADU_LOCATIONS\s*=\s*\[([\s\S]*?)\]/.exec(source);
  assert.ok(block, 'could not find TAMIL_NADU_LOCATIONS in job_radar.py');

  const localities = [...block[1].matchAll(/"([^"]+)"/g)].map((m) => m[1].toLowerCase());
  assert.ok(localities.length > 20, 'expected a substantial locality list');

  // Bare "tn" is ambiguous (Tennessee) and "tamilnadu" is a spelling, not a
  // city, so neither needs its own alias entry.
  const skip = new Set(['tn', 'tamil nadu', 'tamilnadu']);
  const unresolved = localities
    .filter((name) => !skip.has(name))
    .filter((name) => !detectCity(name));

  assert.deepEqual(unresolved, [], `localities not recognised by detectCity: ${unresolved.join(', ')}`);
});

test('newly covered cities are searched and classified', () => {
  const added = ['Hosur', 'Kanchipuram', 'Dindigul', 'Karur', 'Nagercoil', 'Thoothukudi', 'Cuddalore', 'Ranipet', 'Sivakasi', 'Kumbakonam', 'Neyveli'];
  const plan = config.planSearches(['software developer'], config.CITIES, 0);
  const searched = new Set(plan.map((p) => p.city));
  for (const city of added) {
    assert.ok(config.CITIES.includes(city), `${city} missing from CITIES`);
    assert.ok(searched.has(city), `${city} never reached by the search plan`);
    assert.equal(detectCity(city), city, `${city} not classified by detectCity`);
  }
  // Tuticorin is the common English spelling of Thoothukudi.
  assert.equal(detectCity('Tuticorin'), 'Thoothukudi');
  // Non-Tamil-Nadu cities must still be rejected, so we do not over-collect.
  assert.equal(detectCity('Bangalore, India'), null);
});

test('ATS location filter accepts new TN cities but still rejects other states', () => {
  const { isTamilNaduLocation } = require('./src/sources/tech-ats');
  assert.equal(isTamilNaduLocation({ city: 'Hosur' }), true);
  assert.equal(isTamilNaduLocation({ fullLocation: 'Hosur, India' }), true);
  assert.equal(isTamilNaduLocation({ fullLocation: 'Kanchipuram, Tamil Nadu, India' }), true);
  assert.equal(isTamilNaduLocation({ region: 'Tamil Nadu' }), true);
  assert.equal(isTamilNaduLocation({ fullLocation: 'Bengaluru, India' }), false);
  assert.equal(isTamilNaduLocation({ fullLocation: 'Pune' }), false);
  assert.equal(isTamilNaduLocation({}), false);
});

test('bounded runner respects the limit and keeps input order', async () => {
  const { runWithConcurrency } = require('./src/concurrency');
  let inFlight = 0;
  let peak = 0;
  const items = Array.from({ length: 20 }, (_, i) => i);

  const results = await runWithConcurrency(items, 4, async (n) => {
    inFlight += 1;
    peak = Math.max(peak, inFlight);
    await new Promise((resolve) => setTimeout(resolve, 5));
    inFlight -= 1;
    return n * 2;
  });

  assert.equal(peak, 4, `expected at most 4 in flight, saw ${peak}`);
  assert.deepEqual(results.map((r) => r.value), items.map((n) => n * 2));
  assert.ok(results.every((r) => r.status === 'fulfilled'));
});

test('bounded runner isolates failures instead of cancelling the batch', async () => {
  const { runWithConcurrency } = require('./src/concurrency');
  const results = await runWithConcurrency([1, 2, 3, 4], 2, async (n) => {
    if (n === 2) throw new Error('boom');
    return n;
  });
  assert.equal(results[0].value, 1);
  assert.equal(results[1].status, 'rejected');
  assert.equal(results[2].value, 3);
  assert.equal(results[3].value, 4);
});

test('search plan searches every keyword in the preferred cities before others', () => {
  const plan = config.planSearches(['a', 'b'], config.CITIES, config.MAX_PAGES_PER_SOURCE);
  // The first 8 searches must be both keywords across all four preferred cities.
  const firstRound = plan.slice(0, 8);
  assert.deepEqual([...new Set(firstRound.map((p) => p.city))].sort(), [...config.PRIORITY_CITIES].sort());
  assert.deepEqual([...new Set(firstRound.map((p) => p.keyword))].sort(), ['a', 'b']);
  assert.ok(firstRound.every((p) => config.PRIORITY_CITIES.includes(p.city)));
});

test('the generated sitemap is valid and points at the deployed site', () => {
  const xml = buildSitemap();
  assert.ok(xml.includes('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'));
  assert.ok(xml.includes(`<loc>${SITE_URL}</loc>`));
  assert.ok(/<lastmod>\d{4}-\d{2}-\d{2}<\/lastmod>/.test(xml));
});

test('the CLI rejects an unknown step instead of running everything', () => {
  const { resolveStep } = require('./src/cli');
  assert.equal(resolveStep(['node', 'cli.js', 'scrape']).step, 'scrape');
  assert.equal(resolveStep(['node', 'cli.js']).step, 'all');
  assert.equal(resolveStep(['node', 'cli.js', 'typo']).error, 'typo');
  assert.equal(resolveStep(['node', 'cli.js', 'scrape', 'extra']).error, 'extra');
});
