#!/usr/bin/env node
'use strict';

/**
 * The main entry point.
 *
 *   node src/cli.js --step=all        scrape + verify + diff + export + report
 *   node src/cli.js --step=scrape     just step 1 (writes work/scraped.json)
 *   node src/cli.js --step=validate   just step 2
 *   node src/cli.js --step=diff       just step 3
 *   node src/cli.js --step=export     just step 4
 *   node src/cli.js --step=report     just step 5
 *   node src/cli.js --step=serve      tiny local web server for public/
 *
 * Split steps write their intermediate results into work/ so the GitHub
 * Actions workflow can run them as separate, individually visible steps.
 *
 * Settings you can pass as environment variables:
 *   QUERY=<extra search word>   CITY=<one city>   MAX_TOTAL_JOBS=<number>
 *   ENABLE_TIER3=true           PORT=<port for serve>   SKIP_SPA_SITES=true
 */

const fs = require('fs');
const http = require('http');
const path = require('path');

const config = require('./config');
const {
  log,
  logError,
  tidy,
  clip,
  detectEducation,
  detectSkills,
  detectDeadline,
  detectSalary,
  detectExperience,
  isFresher,
  cleanSummary,
} = require('./util');
const scraper = require('./scraper');
const { loadSources, tierForSite } = require('./sources');
const { SITE_LABELS } = require('./sources/company-careers');
const { validateJobs } = require('./validate');
const { readJobFile, readJsonSafe, computeDiff, appendHistory } = require('./diff');
const { writeOutputs, writeJson } = require('./export');
const { buildReport, writeReport } = require('./report');

const ROOT = path.resolve(__dirname, '..');
const WORK_DIR = path.join(ROOT, 'work');
const DATA_DIR = path.join(ROOT, 'data');
const PUBLIC_DIR = path.join(ROOT, 'public');

const SCRAPED_FILE = path.join(WORK_DIR, 'scraped.json');
const VALIDATED_FILE = path.join(WORK_DIR, 'validated.json');
const DIFF_FILE = path.join(WORK_DIR, 'diff.json');

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const args = { step: 'all' };
  for (const raw of argv.slice(2)) {
    const value = raw.startsWith('--') ? raw.slice(2) : raw;
    const parts = value.split('=');
    const key = parts[0];
    const rest = parts.slice(1).join('=');
    if (key === 'help') args.help = true;
    else if (key === 'step') args.step = rest || 'all';
  }
  return args;
}

function readNumber(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}

/** Which cities to search: all of them, or just the one you asked for. */
function resolveCities() {
  const requested = tidy(process.env.CITY || '');
  if (!requested) return config.CITIES;
  return [config.canonicalCity(requested)];
}

/** Which keywords to search. */
function resolveKeywords() {
  const extra = tidy(process.env.QUERY || '');
  return extra ? [extra, ...config.SEARCH_KEYWORDS] : config.SEARCH_KEYWORDS;
}

function triggerName() {
  if (process.env.GITHUB_EVENT_NAME) return `GitHub Actions (${process.env.GITHUB_EVENT_NAME})`;
  return 'local run';
}

function ensureWorkDir() {
  fs.mkdirSync(WORK_DIR, { recursive: true });
}

function readWorkFile(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${label} is missing (${path.relative(ROOT, filePath)}). Run "npm run step:scrape" first.`);
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

/** Collects one status line per website, for the run report. */
function createNoteCollector() {
  const sites = new Map();
  return {
    note(id, status, detail) {
      const existing = sites.get(id);
      // An "ok" result always wins over a later complaint about the same site.
      if (existing && (existing.status === 'ok' || existing.status === 'skipped') && status !== 'ok') return;
      sites.set(id, {
        id,
        label: SITE_LABELS[id] || id,
        tier: tierForSite(id),
        status,
        detail: tidy(detail),
      });
    },
    hasNote(id) {
      return sites.has(id);
    },
    list() {
      return Array.from(sites.values()).sort((a, b) => a.tier - b.tier || a.label.localeCompare(b.label));
    },
  };
}

// ---------------------------------------------------------------------------
// Step 1 - scrape
// ---------------------------------------------------------------------------

async function runScrape() {
  const startedAt = new Date();
  const notes = createNoteCollector();
  const sources = loadSources();
  const cities = resolveCities();
  const keywords = resolveKeywords();
  const limit = config.MAX_JOBS_PER_SOURCE;
  const deadline = Date.now() + readNumber(process.env.SCRAPE_BUDGET_MS, 15 * 60 * 1000);
  const maxTotal = readNumber(process.env.MAX_TOTAL_JOBS, 150);

  let sharedContext = null;

  const ctx = {
    cities,
    keywords,
    limit,
    deadline,
    pageLimit: config.MAX_PAGES_PER_SOURCE,
    note: notes.note,
    hasNote: notes.hasNote,
    log,
    skipSpaSites: process.env.SKIP_SPA_SITES === 'true',
    async getContext() {
      if (!sharedContext) {
        const browser = await scraper.launchBrowser();
        sharedContext = await scraper.newContext(browser);
        if (!sharedContext || typeof sharedContext.newPage !== 'function') {
          sharedContext = null;
          throw new Error('headless browser unavailable in this environment');
        }
      }
      return sharedContext;
    },
  };

  log(`Scraping started: ${keywords.length} keyword(s) x ${cities.length} city/cities`);
  const buckets = new Map(); // source module id -> records it found
  const perSource = {};

  for (const source of sources) {
    if (Date.now() > deadline) {
      log(`  out of time budget, skipping ${source.label}`);
      notes.note(source.id, 'skipped', 'out of time budget for this run');
      continue;
    }
    log(`-> ${source.label} (tier ${source.tier})`);
    try {
      const jobs = await source.scrape(ctx);
      perSource[source.id] = jobs.length;
      buckets.set(source.id, (buckets.get(source.id) || []).concat(jobs));
      log(`   ${jobs.length} record(s)`);
    } catch (error) {
      logError(`source "${source.label}" failed and was skipped: ${error.message}`);
      notes.note(source.id, 'error', clip(error.message, 140));
    }
  }

  // 1. Drop records missing a required field and stale TNPSC archive notices.
  // 2. Deduplicate across sources (same apply URL = same job).
  const seen = new Set();
  const perBucket = new Map();
  let kept = 0;
  for (const [id, list] of buckets) {
    const bucket = [];
    for (const job of list) {
      if (!job || seen.has(job.id)) continue;
      if (dropStaleTnpscNotices([job]).length === 0) continue;
      seen.add(job.id);
      bucket.push(job);
      kept += 1;
    }
    perBucket.set(id, bucket);
  }

  // 3. Take a fair share from every source, round-robin, up to the total cap.
  //    Without this the government portal alone would swallow the whole budget
  //    and the company / job-portal sources would never appear.
  const queues = Array.from(perBucket.values());
  const jobs = [];
  let progressed = true;
  while (jobs.length < maxTotal && progressed) {
    progressed = false;
    for (const queue of queues) {
      if (jobs.length >= maxTotal) break;
      if (queue.length) {
        jobs.push(queue.shift());
        progressed = true;
      }
    }
  }
  const dropped = kept - jobs.length;

  if (sharedContext) await sharedContext.close().catch(() => undefined);
  await scraper.closeBrowser();

  const finishedAt = new Date();

  // How many usable records each individual website offered, before the fair
  // round-robin cap. Lets the report show "found" vs "kept".
  const foundCounts = {};
  for (const bucket of perBucket.values()) {
    for (const job of bucket) {
      const key = job.source || 'unknown';
      foundCounts[key] = (foundCounts[key] || 0) + 1;
    }
  }

  const payload = {
    started_at: startedAt.toISOString(),
    finished_at: finishedAt.toISOString(),
    duration_seconds: Math.round((finishedAt - startedAt) / 1000),
    trigger: triggerName(),
    keywords,
    cities,
    max_total_jobs: maxTotal,
    sites: notes.list(),
    per_source: perSource,
    found_by_source: foundCounts,
    dropped_records: dropped,
    dead_domains: scraper.getDeadDomains(),
    jobs,
  };

  ensureWorkDir();
  writeJson(SCRAPED_FILE, payload);
  log(`Scrape finished: ${jobs.length} usable record(s), ${dropped} duplicate/dropped -> work/scraped.json`);
  return payload;
}

// ---------------------------------------------------------------------------
// Step 2 - verify every apply URL
// ---------------------------------------------------------------------------

async function runValidate() {
  const scraped = readWorkFile(SCRAPED_FILE, 'Scrape output');
  const started = Date.now();
  const browser = await scraper.launchBrowser();
  const context = await scraper.newContext(browser);

  let result;
  try {
    result = await validateJobs(scraped.jobs, {
      context,
      concurrency: readNumber(process.env.VALIDATE_CONCURRENCY, 4),
      onProgress: (done, total, job) => {
        if (done % 10 === 0 || done === total) {
          log(`  checked ${done}/${total} ... last: ${job.verify_reason}`);
        }
      },
    });
  } finally {
    // Always release the browser, even when verification throws, so a failed
    // run never leaves a Chromium process (and its file handles) behind.
    await context.close().catch(() => undefined);
    await scraper.closeBrowser();
  }
  const { jobs, stats } = result;

  const payload = Object.assign({}, scraped, {
    validated_at: new Date().toISOString(),
    validate_seconds: Math.round((Date.now() - started) / 1000),
    validate_stats: stats,
    jobs,
  });
  ensureWorkDir();
  writeJson(VALIDATED_FILE, payload);
  log(
    `Verification finished: ${stats.live} live, ${stats.loginRequired} login-walled, ` +
      `${stats.noSignal} no job signal, ${stats.redirected} redirected, ${stats.dead} dead, ` +
      `${stats.unreachable} unreachable -> work/validated.json`
  );
  return payload;
}

// ---------------------------------------------------------------------------
// Step 3 - work out which jobs are new and which have gone
// ---------------------------------------------------------------------------

async function runDiff() {
  const validated = readWorkFile(VALIDATED_FILE, 'Validation output');
  const previousPath = path.join(DATA_DIR, 'jobs.json');
  const previousJobs = readJobFile(previousPath);

  const { newJobs, keptJobs, removedJobs } = computeDiff(validated.jobs, previousJobs);

  const payload = {
    computed_at: new Date().toISOString(),
    previous_file: fs.existsSync(previousPath) ? path.relative(ROOT, previousPath) : null,
    previous_record_count: previousJobs.length,
    previous_verified_count: previousJobs.filter((job) => job.verified === true).length,
    new_count: newJobs.length,
    kept_count: keptJobs.length,
    removed_count: removedJobs.length,
    new: newJobs,
    removed: removedJobs.map((job) => ({
      id: job.id,
      title: job.title,
      company: job.company,
      city: job.city,
      apply_url: job.apply_url,
    })),
  };

  ensureWorkDir();
  writeJson(DIFF_FILE, payload);
  log(
    `Diff finished: ${payload.new_count} new, ${payload.kept_count} unchanged, ` +
      `${payload.removed_count} gone -> work/diff.json`
  );
  return payload;
}

// ---------------------------------------------------------------------------
// Step 4 - write data/ and public/data/
// ---------------------------------------------------------------------------

function enrichJobRecord(job) {
  const textPieces = [
    job.title,
    job.page_title,
    job.extra,
    job.apply_url,
    job.description,
    job.verify_note,
    job.location,
  ].filter(Boolean);
  const text = textPieces.join(' ');

  const qualification =
    job.qualification ||
    detectEducation(text, job.title) ||
    (job.category === 'Government' ? 'Graduate / As per notification' : null);
  const skills =
    Array.isArray(job.skills) && job.skills.length > 0
      ? job.skills
      : detectSkills(text, job.title, job.apply_url);
  const deadline = job.deadline || detectDeadline(text, job.title) || null;
  const salary = job.salary || detectSalary(text) || null;
  const experience = job.experience || detectExperience(text) || null;
  const is_fresher =
    job.is_fresher !== undefined && job.is_fresher !== null
      ? job.is_fresher
      : isFresher(experience, text, job.title);
  const description =
    job.description ||
    (job.extra ? cleanSummary(job.extra) : null) ||
    job.page_title ||
    `${job.title} vacancy at ${job.company} located in ${job.city || 'Tamil Nadu'}. Re-verified live vacancy.`;

  return Object.assign({}, job, {
    qualification: qualification || null,
    skills: skills || [],
    deadline,
    salary: salary || null,
    experience: experience || null,
    is_fresher,
    description,
  });
}

async function runExport() {
  const validated = readWorkFile(VALIDATED_FILE, 'Validation output');
  const diff = readWorkFile(DIFF_FILE, 'Diff output');

  const historyPath = path.join(DATA_DIR, 'history.json');
  const existingHistory = readJsonSafe(historyPath, {});
  const enrichedJobs = validated.jobs.map(enrichJobRecord);
  const enrichedNewJobs = (diff.new || []).map(enrichJobRecord);
  const live = enrichedJobs.filter((job) => job.verified === true);
  const finishedAt = validated.validated_at || new Date().toISOString();

  const history = appendHistory(existingHistory, finishedAt, {
    total: enrichedJobs.length,
    verified: live.length,
    new: diff.new_count,
  });

  const meta = {
    status: 'ok',
    started_at: validated.started_at,
    finished_at: finishedAt,
    duration_seconds: validated.duration_seconds,
    validate_seconds: validated.validate_seconds,
    trigger: validated.trigger,
    keywords: validated.keywords,
    cities: validated.cities,
    scraped_records: enrichedJobs.length,
    verified_jobs: live.length,
    new_jobs: diff.new_count,
    removed_jobs: diff.removed_count,
    login_required: (validated.validate_stats || {}).loginRequired || 0,
    validate_stats: validated.validate_stats || {},
    source_status: validated.sites || [],
    per_source: validated.per_source || {},
    dead_domains: validated.dead_domains || {},
    dropped_records: validated.dropped_records || 0,
  };

  const result = writeOutputs({
    rootDir: ROOT,
    allJobs: enrichedJobs,
    newJobs: enrichedNewJobs,
    removedJobs: diff.removed,
    history,
    meta,
    previousVerifiedCount: diff.previous_verified_count,
    rawScrapedCount: enrichedJobs.length,
  });

  if (result.guard && result.guard.skipped) {
    log('Export finished: data files left untouched because of the safety guard.');
  } else {
    log(
      `Export finished: ${enrichedJobs.length} record(s) in data/jobs.json, ` +
        `${result.live.length} verified -> public/data/jobs.json`
    );
  }
  return { meta, result, live };
}

// ---------------------------------------------------------------------------
// Step 5 - the run report
// ---------------------------------------------------------------------------

/** Work out how many jobs came from each website, by looking at job.source. */
function countJobsBySource(jobs) {
  const counts = {};
  for (const job of jobs) {
    const key = job.source || 'unknown';
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
}

/** Drop stale TNPSC archive links: vacancy distributions from finished exams. */
function dropStaleTnpscNotices(jobs) {
  return jobs.filter((job) => {
    if (job.source !== 'tnpsc.gov.in') return true;
    const url = String(job.apply_url || '').toLowerCase();
    const title = String(job.title || '').toLowerCase();
    if (/vacancy|vacancies|distribution|addendum/.test(title)) {
      const year = /_(20\d{2})\.pdf|_(20\d{2})_|(20\d{2})\.pdf/.exec(url);
      if (year) {
        const y = Number(year[1] || year[2] || year[3]);
        const now = new Date().getFullYear();
        // A vacancy list older than this calendar year belongs to an exam that
        // is over - it is not a live vacancy.
        if (y < now) return false;
      }
    }
    return true;
  });
}

async function runReport() {
  const validated = readWorkFile(VALIDATED_FILE, 'Validation output');
  const diff = readWorkFile(DIFF_FILE, 'Diff output');
  const lastRun = readJsonSafe(path.join(DATA_DIR, 'last-run.json'), {});
  const live = validated.jobs.filter((job) => job.verified === true);

  const markdown = buildReport({
    meta: {
      started_at: validated.started_at,
      finished_at: validated.validated_at || new Date().toISOString(),
      duration_seconds: validated.duration_seconds,
      trigger: validated.trigger,
      keywords: validated.keywords,
      cities: validated.cities,
      droppedRecords: validated.dropped_records || 0,
    },
    sites: validated.sites || [],
    sourceCounts: countJobsBySource(validated.jobs),
    foundCounts: validated.found_by_source || {},
    validateStats: validated.validate_stats || {},
    diff,
    latest: { total: validated.jobs.length, verified: live.length, new: diff.new_count },
    guard: lastRun.guard || null,
  });

  const file = writeReport(ROOT, markdown);
  log(`Report written to ${path.relative(ROOT, file)}`);

  const summaryFile = process.env.GITHUB_STEP_SUMMARY;
  if (summaryFile) {
    fs.appendFileSync(summaryFile, markdown + '\n', 'utf8');
    log('Report appended to $GITHUB_STEP_SUMMARY');
  }
  process.stdout.write('\n' + markdown + '\n\n');
  return markdown;
}

// ---------------------------------------------------------------------------
// Bonus step - a tiny local web server so you can preview public/
// ---------------------------------------------------------------------------

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.csv': 'text/csv; charset=utf-8',
};

function runServe() {
  const port = readNumber(process.env.PORT, 5173);
  const server = http.createServer((request, response) => {
    let requested;
    try {
      requested = decodeURIComponent(String(request.url || '/').split('?')[0]);
    } catch (error) {
      // A malformed %-escape must not crash the preview server.
      response.writeHead(400, { 'content-type': 'text/plain; charset=utf-8' });
      response.end('Bad request\n');
      return;
    }
    const relative = requested === '/' ? 'index.html' : requested.replace(/^\/+/, '');
    // resolve() + a separator-aware prefix check blocks ../ escapes and sibling
    // folders such as "public-secret" that a plain startsWith() would allow.
    const target = path.resolve(PUBLIC_DIR, relative);
    if (target !== PUBLIC_DIR && !target.startsWith(PUBLIC_DIR + path.sep)) {
      response.writeHead(403, { 'content-type': 'text/plain; charset=utf-8' });
      response.end('Forbidden');
      return;
    }
    fs.readFile(target, (error, data) => {
      if (error) {
        response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
        response.end('Not found: ' + relative + '\nRun "npm run step:export" first.\n');
        return;
      }
      response.writeHead(200, { 'content-type': MIME[path.extname(target).toLowerCase()] || 'application/octet-stream' });
      response.end(data);
    });
  });
  server.listen(port, () => {
    log(`Preview server running: http://localhost:${port}/  (press Ctrl+C to stop)`);
  });
  return server;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const HELP = [
  'Tamil Nadu Live Jobs',
  '',
  '  npm run scrape            full run: scrape -> verify -> diff -> export -> report',
  '  npm run step:scrape       step 1 only',
  '  npm run step:validate     step 2 only (needs step 1)',
  '  npm run step:diff         step 3 only (needs step 2)',
  '  npm run step:export       step 4 only (needs steps 2 and 3)',
  '  npm run step:report       step 5 only (needs steps 3 and 4)',
  '  npm run serve             open public/ at http://localhost:5173',
  '',
  'Optional settings (set these before the command, e.g. MAX_TOTAL_JOBS=25 npm run scrape):',
  '  QUERY=java developer      add one extra search word',
  '  CITY=Madurai              search only one city',
  '  MAX_TOTAL_JOBS=25         keep runs short while testing',
  '  ENABLE_TIER3=true         also try the optional Tier 3 sources',
  '  SKIP_SPA_SITES=true       skip the slow JavaScript-only career sites',
  '  VALIDATE_CONCURRENCY=4    how many different sites to check at once',
].join('\n');

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) {
    process.stdout.write(HELP + '\n');
    return;
  }
  if (args.step === 'serve') {
    runServe();
    return;
  }
  const plan = {
    all: [runScrape, runValidate, runDiff, runExport, runReport],
    scrape: [runScrape],
    validate: [runValidate],
    diff: [runDiff],
    export: [runExport],
    report: [runReport],
  }[args.step];
  if (!plan) {
    process.stdout.write('Unknown step "' + args.step + '".\n\n' + HELP + '\n');
    process.exitCode = 2;
    return;
  }
  await runAll(plan, args.step);
}

async function runAll(plan, stepName) {
  try {
    for (const step of plan) await step();
    log('All done.');
  } catch (error) {
    logError(error.stack || error.message);
    // Leave the repo in a working state: record the failure but never touch
    // the existing data/jobs.json.
    try {
      fs.mkdirSync(DATA_DIR, { recursive: true });
      const previous = readJsonSafe(path.join(DATA_DIR, 'last-run.json'), {});
      writeJson(path.join(DATA_DIR, 'last-run.json'), {
        status: 'failed',
        failed_step: stepName,
        failed_at: new Date().toISOString(),
        error: clip(error.message, 400),
        previous_status: previous.status || 'unknown',
        note: 'data/jobs.json was left untouched by this failed run.',
      });
      const summaryFile = process.env.GITHUB_STEP_SUMMARY;
      if (summaryFile) {
        fs.appendFileSync(
          summaryFile,
          '## :x: Run failed at step `' + stepName + '`\n\n```\n' +
            clip(error.message, 1500) + '\n```\n\n' +
            'The previous good data files were kept - nothing was overwritten.\n',
          'utf8'
        );
      }
    } catch (secondary) {
      logError('could not record the failure: ' + secondary.message);
    }
    process.exitCode = 1;
  }
}

main();

module.exports = { parseArgs, resolveCities, resolveKeywords, ROOT, WORK_DIR, PUBLIC_DIR };
