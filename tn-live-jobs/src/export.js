'use strict';

/**
 * Writing the files.
 *
 * data/jobs.json        every job found in this run (live and rejected), so you
 *                       can inspect exactly what failed and why
 * data/jobs.csv         the same rows, for Excel
 * data/new-jobs.json    only the jobs seen for the very first time
 * data/history.json     one line per run, for trending
 * data/last-run.json    metadata about this run
 * public/data/jobs.json only the VERIFIED jobs - this is what the web page shows
 * public/data/jobs.js   the same data as a script, so index.html also works
 *                       when you open it straight from disk (file://)
 */

const fs = require('fs');
const path = require('path');
const { log } = require('./util');
const { PRIORITY_CITIES, canonicalCity } = require('./config');

const CSV_COLUMNS = [
  'id',
  'title',
  'company',
  'city',
  'state',
  'category',
  'employment_type',
  'experience',
  'is_fresher',
  'qualification',
  'skills',
  'salary',
  'deadline',
  'posted_at',
  'expires_at',
  'apply_url',
  'source',
  'source_type',
  'scraped_at',
  'verified',
  'verify_reason',
  'http_status',
  'verified_at',
];

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

/** Pretty-printed JSON, with a trailing newline (keeps git diffs tidy). */
function writeJson(filePath, value) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

function csvCell(value) {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) value = value.join('; ');
  const text = String(value);
  if (/[",\n\r]/.test(text)) return '"' + text.replace(/"/g, '""') + '"';
  return text;
}

function toCsv(jobs) {
  const lines = [CSV_COLUMNS.join(',')];
  for (const job of jobs) {
    lines.push(CSV_COLUMNS.map((column) => csvCell(job[column])).join(','));
  }
  // The BOM makes Excel read the file as UTF-8 instead of mangling characters.
  return '\ufeff' + lines.join('\r\n') + '\r\n';
}

function writeCsv(filePath, jobs) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, toCsv(jobs), 'utf8');
}

/** Preferred cities first, then real posting dates and verification within each tier. */
function sortJobs(jobs) {
  return jobs.slice().sort((a, b) => {
    const aPriority = PRIORITY_CITIES.includes(canonicalCity(a.city));
    const bPriority = PRIORITY_CITIES.includes(canonicalCity(b.city));
    if (aPriority !== bPriority) return aPriority ? -1 : 1;
    if (a.posted_at && b.posted_at && a.posted_at !== b.posted_at) return a.posted_at < b.posted_at ? 1 : -1;
    if (a.posted_at && !b.posted_at) return -1;
    if (!a.posted_at && b.posted_at) return 1;
    if (a.verified !== b.verified) return a.verified ? -1 : 1;
    return String(a.title).localeCompare(String(b.title));
  });
}

/**
 * Sitemap and robots files for search engines.
 *
 * The dashboard is a single page, so the sitemap lists one canonical URL. It is
 * rewritten on every export so `<lastmod>` reflects the latest run.
 */
const SITE_URL = 'https://nm969989-cmd.github.io/tn-live-jobs/';

function buildSitemap() {
  const now = new Date().toISOString().slice(0, 10);
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    '  <url>',
    `    <loc>${SITE_URL}</loc>`,
    `    <lastmod>${now}</lastmod>`,
    '    <changefreq>daily</changefreq>',
    '    <priority>1.0</priority>',
    '  </url>',
    '</urlset>',
    '',
  ].join('\n');
}

const ROBOTS_TXT = [
  'User-agent: *',
  'Allow: /',
  '',
  `Sitemap: ${SITE_URL}sitemap.xml`,
  '',
].join('\n');

/**
 * Write the static SEO files the dashboard needs (sitemap and robots) into the
 * public folder, so they are deployed alongside the page.
 */
function writeSeoFiles(publicDir) {
  fs.writeFileSync(path.join(publicDir, 'sitemap.xml'), buildSitemap(), 'utf8');
  fs.writeFileSync(path.join(publicDir, 'robots.txt'), ROBOTS_TXT, 'utf8');
}

/**
 * Write every output file for one run.
 *
 * SAFETY GUARD: if every source failed and we have zero verified jobs while the
 * previous jobs.json still had some, we refuse to overwrite the good data.
 * A broken run must never push an empty or corrupted jobs.json.
 */
function writeOutputs(options) {
  const {
    rootDir,
    allJobs,
    newJobs,
    removedJobs,
    history,
    meta,
    previousVerifiedCount,
    rawScrapedCount,
  } = options;

  const dataDir = path.join(rootDir, 'data');
  const publicDir = path.join(rootDir, 'public');
  ensureDir(path.join(publicDir, 'data'));

  const sorted = sortJobs(allJobs);
  const live = sorted.filter((job) => job.verified === true);

  const nothingScraped = rawScrapedCount === 0;
  const wouldWipeGoodData = live.length === 0 && previousVerifiedCount > 0;

  if (nothingScraped && wouldWipeGoodData) {
    const guard = {
      skipped: true,
      reason: 'no_jobs_found_and_previous_file_had_jobs',
      message:
        'Every source returned nothing this run, so data/jobs.json was left untouched ' +
        'instead of being emptied.',
    };
    log(`  SAFETY GUARD: ${guard.message}`);
    writeJson(path.join(dataDir, 'last-run.json'), Object.assign({}, meta, { guard }));
    return { live, guard, wroteData: false };
  }

  const payload = {
    generated_at: meta.finished_at,
    count: sorted.length,
    verified_count: live.length,
    new_count: newJobs.length,
    removed_count: removedJobs.length,
    note:
      'data/jobs.json keeps every record from the latest run so failures stay visible. ' +
      'The public web page only ever shows records with "verified": true.',
    jobs: sorted,
  };

  writeJson(path.join(dataDir, 'jobs.json'), payload);
  writeCsv(path.join(dataDir, 'jobs.csv'), sorted);

  writeJson(path.join(dataDir, 'new-jobs.json'), {
    generated_at: meta.finished_at,
    count: newJobs.length,
    note: 'Jobs whose id was not present in the previous data/jobs.json.',
    jobs: sortJobs(newJobs),
  });

  writeJson(path.join(dataDir, 'history.json'), history);
  writeJson(path.join(dataDir, 'last-run.json'), meta);

  // The public copies contain verified jobs only, so an unverified record can
  // never leak onto the web page even if the browser-side filter is bypassed.
  const publicPayload = {
    generated_at: meta.finished_at,
    count: live.length,
    new_count: newJobs.filter((job) => job.verified === true).length,
    jobs: live,
  };
  writeJson(path.join(publicDir, 'data', 'jobs.json'), publicPayload);
  writeSeoFiles(publicDir);
  fs.writeFileSync(
    path.join(publicDir, 'data', 'jobs.js'),
    '/* Generated by src/export.js - do not edit by hand. */\n' +
      'window.__TN_JOBS__ = ' +
      JSON.stringify(publicPayload) +
      ';\n',
    'utf8'
  );

  return { live, guard: null, wroteData: true };
}

module.exports = {
  CSV_COLUMNS,
  ensureDir,
  writeJson,
  writeCsv,
  toCsv,
  sortJobs,
  writeOutputs,
  buildSitemap,
  writeSeoFiles,
  SITE_URL,
};
