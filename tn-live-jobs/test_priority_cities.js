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
