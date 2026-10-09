'use strict';
// Offline tests: no portal requests or scraping CLI execution.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const config = require('./src/config');
const { detectCity } = require('./src/util');
const { sortJobs } = require('./src/export');

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
