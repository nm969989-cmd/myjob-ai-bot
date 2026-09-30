'use strict';

/**
 * Shared scraping helpers.
 *
 * Two ways to get a page:
 *   1. fetchText() / fetchJson()  - fast, for plain HTML and JSON APIs.
 *   2. render()                   - uses Playwright + Chromium, for pages that
 *                                   build their job list with JavaScript.
 *
 * Both go through the same politeness rules:
 *   - one request at a time per domain (never parallel on the same site)
 *   - a random 1.5-3.5 second pause between requests
 *   - at most 2 attempts per URL
 */

const { chromium } = require('playwright');
const {
  MIN_DELAY_MS,
  MAX_DELAY_MS,
  HTTP_TIMEOUT_MS,
  RENDER_TIMEOUT_MS,
  MAX_ATTEMPTS,
} = require('./config');
const {
  log,
  politeSleep,
  tidy,
  jobId,
  registrableDomain,
  detectCity,
  detectCategory,
  detectEmploymentType,
  detectExperience,
  detectSalary,
  detectEducation,
  detectSkills,
  detectDeadline,
  isFresher,
  cleanSummary,
} = require('./util');

const USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36';

// ---------- per-domain queue ------------------------------------------------

const domainChains = new Map();
const deadDomains = new Map();

/**
 * The plain hostname of a URL, without the www. prefix.
 * We key "this site is dead" on the *host*, not the registrable domain, so
 * employment.tn.gov.in being offline never blocks www.tn.gov.in as well.
 */
function hostOf(urlOrHost) {
  const value = String(urlOrHost || '').trim();
  if (!value) return '';
  try {
    return new URL(value).hostname.toLowerCase().replace(/^www\./, '');
  } catch (error) {
    return value.toLowerCase().replace(/^www\./, '').replace(/^https?:\/\//, '').split('/')[0];
  }
}

/** Mark one site as blocked/dead so we stop wasting time on it this run. */
function markDomainDead(urlOrHost, reason) {
  const host = hostOf(urlOrHost);
  if (!host) return;
  if (!deadDomains.has(host)) {
    deadDomains.set(host, reason);
    log(`  ! site marked as unusable -> ${host} (${reason})`);
  }
}

function isDomainDead(urlOrHost) {
  return deadDomains.has(hostOf(urlOrHost));
}

function getDeadDomains() {
  return Object.fromEntries(deadDomains);
}

/**
 * Run `task` alone, after any other task for the same domain has finished.
 * That is what stops us from ever sending two parallel requests to one site.
 */
function runExclusive(domain, task) {
  const previous = domainChains.get(domain) || Promise.resolve();
  const next = previous.then(() => task());
  // Keep the chain alive even if a task throws.
  domainChains.set(domain, next.then(() => undefined, () => undefined));
  return next;
}

async function politePause() {
  return politeSleep(MIN_DELAY_MS, MAX_DELAY_MS);
}

// Remember when we last touched each domain, so we can space requests out.
const domainLastUsedAt = new Map();

/**
 * Wait until enough time has passed since the last request to this domain.
 * The first request to a site goes out immediately; every later one waits
 * a random 1.5-3.5 seconds. This is called *before* a request, so it never
 * delays handing results back to the caller.
 */
async function waitForTurn(domain) {
  const last = domainLastUsedAt.get(domain);
  if (last) {
    const wanted = MIN_DELAY_MS + Math.random() * Math.max(0, MAX_DELAY_MS - MIN_DELAY_MS);
    const elapsed = Date.now() - last;
    if (elapsed < wanted) await politeSleep(wanted - elapsed, wanted - elapsed);
  }
  domainLastUsedAt.set(domain, Date.now());
}

// ---------- plain HTTP ------------------------------------------------------

function buildHeaders(extra) {
  return Object.assign(
    {
      'user-agent': USER_AGENT,
      'accept-language': 'en-IN,en;q=0.9',
      accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    },
    extra || {}
  );
}

/**
 * Download a URL and return { status, url, finalUrl, redirected, contentType, body }.
 * Throws if every attempt fails, so the caller can mark the source dead.
 */
async function fetchText(url, options) {
  const opts = options || {};
  const domain = registrableDomain(url);
  const attempts = Math.min(opts.attempts || MAX_ATTEMPTS, MAX_ATTEMPTS);
  let lastError = null;

  return runExclusive(domain, async () => {
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      await waitForTurn(domain);
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), opts.timeout || HTTP_TIMEOUT_MS);
      try {
        const response = await fetch(url, {
          redirect: 'follow',
          signal: controller.signal,
          headers: buildHeaders(opts.headers),
        });
        const body = await response.text();
        return {
          status: response.status,
          url,
          finalUrl: response.url,
          redirected: response.redirected,
          contentType: response.headers.get('content-type') || '',
          body,
        };
      } catch (error) {
        lastError = error;
      } finally {
        clearTimeout(timer);
      }
    }
    throw new Error(`fetch failed for ${url}: ${lastError && lastError.message}`);
  });
}

/** Download a URL and JSON.parse it. */
async function fetchJson(url, options) {
  const result = await fetchText(
    url,
    Object.assign({}, options, {
      headers: Object.assign(
        { accept: 'application/json, text/plain, */*' },
        (options && options.headers) || {}
      ),
    })
  );
  if (result.status >= 400) {
    const error = new Error(`HTTP ${result.status} for ${url}`);
    error.status = result.status;
    throw error;
  }
  try {
    return { json: JSON.parse(result.body), raw: result };
  } catch (error) {
    throw new Error(`response from ${url} was not valid JSON`);
  }
}

// ---------- Playwright ------------------------------------------------------

let sharedBrowser = null;

/** Start Chromium once per run and reuse it (much faster than per page). */
async function launchBrowser() {
  if (sharedBrowser) return sharedBrowser;
  try {
    sharedBrowser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-extensions'],
    });
  } catch (err) {
    try {
      sharedBrowser = await chromium.launch({
        headless: true,
        channel: 'chrome',
        args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-extensions'],
      });
    } catch (err2) {
      try {
        sharedBrowser = await chromium.launch({
          headless: true,
          channel: 'msedge',
          args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-extensions'],
        });
      } catch (err3) {
        throw err;
      }
    }
  }
  return sharedBrowser;
}

async function closeBrowser() {
  if (sharedBrowser) {
    await sharedBrowser.close().catch(() => undefined);
    sharedBrowser = null;
  }
}

/** A browser context that looks like a normal Indian Chrome user. */
async function newContext(browser) {
  const parent = browser || (await launchBrowser());
  const context = await parent.newContext({
    userAgent: USER_AGENT,
    locale: 'en-IN',
    timezoneId: 'Asia/Kolkata',
    viewport: { width: 1366, height: 900 },
    ignoreHTTPSErrors: true,
    extraHTTPHeaders: { 'accept-language': 'en-IN,en;q=0.9' },
  });
  context.setDefaultTimeout(RENDER_TIMEOUT_MS);
  context.setDefaultNavigationTimeout(RENDER_TIMEOUT_MS);
  // Images, fonts and media are not needed to read job listings, so skip them.
  await context.route('**/*', (route) => {
    const type = route.request().resourceType();
    if (type === 'image' || type === 'font' || type === 'media') return route.abort();
    return route.continue();
  });
  return context;
}

/**
 * Open a URL in a fresh page, wait for it to settle, hand the page to `work`,
 * then always close the page. Returns whatever `work` returns.
 */
async function render(context, url, work, options) {
  const opts = options || {};
  const domain = registrableDomain(url);
  return runExclusive(domain, async () => {
    const page = await context.newPage();
    try {
      await waitForTurn(domain);
      const response = await page.goto(url, {
        waitUntil: opts.waitUntil || 'domcontentloaded',
        timeout: opts.timeout || RENDER_TIMEOUT_MS,
      });
      if (opts.waitForSelector) {
        await page
          .waitForSelector(opts.waitForSelector, { timeout: opts.settleMs || 15000 })
          .catch(() => undefined);
      }
      // Give client-side frameworks a moment to paint their job list.
      await page.waitForTimeout(opts.settleMs || 2500);
      return await work(page, response);
    } finally {
      await page.close().catch(() => undefined);
    }
  });
}

/** Convenience: render a page and return { html, status, finalUrl, title }. */
async function renderHtml(context, url, options) {
  return render(
    context,
    url,
    async (page, response) => ({
      html: await page.content(),
      status: response ? response.status() : null,
      finalUrl: page.url(),
      title: await page.title().catch(() => ''),
    }),
    options
  );
}

/**
 * Some sites (Infosys, Wipro, Apna, Naukri) build their job list in JavaScript
 * and never put it in the HTML. For those we open the page in Chromium and
 * listen to the network: every JSON response the page itself requests is
 * collected here, so we read the same data a real browser reads.
 *
 * `urlIncludes` is a list of substrings; only responses whose URL contains one
 * of them are kept. Passing an empty list keeps every JSON response.
 */
async function renderCapture(context, url, options) {
  const opts = options || {};
  const wanted = opts.urlIncludes || [];
  return captureJsonFromPage(context, url, opts, wanted);
}

/** Internal: open the page and collect matching JSON responses. */
async function captureJsonFromPage(context, url, opts, wanted) {
  const domain = registrableDomain(url);
  return runExclusive(domain, async () => {
    const page = await context.newPage();
    const found = [];
    page.on('response', async (response) => {
      try {
        const responseUrl = response.url();
        if (wanted.length && !wanted.some((piece) => responseUrl.includes(piece))) return;
        const type = response.headers()['content-type'] || '';
        if (!type.includes('json')) return;
        if (response.status() >= 400) return;
        const text = await response.text();
        if (text.length < 20 || text.length > 8_000_000) return;
        found.push({ url: responseUrl, status: response.status(), json: JSON.parse(text) });
      } catch (error) {
        /* ignore responses we cannot read */
      }
    });

    try {
      await waitForTurn(domain);
      await page.goto(url, {
        waitUntil: opts.waitUntil || 'domcontentloaded',
        timeout: opts.timeout || RENDER_TIMEOUT_MS,
      });
      if (opts.waitForSelector) {
        await page
          .waitForSelector(opts.waitForSelector, { timeout: opts.settleMs || 15000 })
          .catch(() => undefined);
      }
      await page.waitForTimeout(opts.settleMs || 4000);
      const dom = {
        html: await page.content(),
        finalUrl: page.url(),
        title: await page.title().catch(() => ''),
      };
      return { json: found, dom };
    } finally {
      await page.close().catch(() => undefined);
    }
  });
}

// ---------- generic JSON job harvest (for SPA career sites) -----------------

const TITLE_KEYS = ['title', 'jobTitle', 'job_title', 'postingTitle', 'Posting_Title', 'jobOpeningName', 'Job_Opening_Name', 'name', 'designation', 'position'];
const COMPANY_KEYS = ['company', 'companyName', 'company_name', 'organization', 'organizationName', 'organisationName', 'employer'];
const URL_KEYS = ['url', 'applyUrl', 'apply_url', 'jobUrl', 'jobPublicURL', 'link', 'jobLink', 'absolute_url', 'canonicalUrl', 'positionUrl', '$url'];
const LOCATION_KEYS = ['location', 'city', 'jobLocation', 'jobCardAddress', 'address', 'locationName', 'workLocation', 'country'];
const ID_KEYS = ['id', 'jobId', 'jobID', 'requisitionId', 'jobReqId', 'postingId'];
const DATE_KEYS = ['postedDate', 'posted_at', 'createdAt', 'created_at', 'datePosted', 'publishedDate', 'jobCreatedAt', 'Job_Openings'];
const SALARY_KEYS = ['salary', 'salaryText', 'salaryRange', 'compensation'];

function firstString(node, keys) {
  for (const key of keys) {
    const value = node[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

function looksLikeJobNode(node) {
  const title = firstString(node, TITLE_KEYS);
  if (!title || title.length < 3 || title.length > 200) return false;
  const hasUrl = URL_KEYS.some((key) => typeof node[key] === 'string' && /^https?:\/\/|^\//.test(node[key]));
  const hasId = ID_KEYS.some((key) => typeof node[key] === 'number' || (typeof node[key] === 'string' && node[key].length > 0));
  return hasUrl || hasId;
}

/**
 * Walk any JSON structure and pull out objects that look like one job posting.
 * Used for career sites that only deliver their job list through a JSON API
 * that their own JavaScript calls (Infosys, Wipro and friends).
 */
function findJobObjects(root, options) {
  const opts = options || {};
  const maxDepth = opts.maxDepth || 8;
  const maxNodes = opts.maxNodes || 40000;
  const found = [];
  let visited = 0;

  function walk(node, depth) {
    if (!node || depth > maxDepth || visited > maxNodes) return;
    visited += 1;
    if (Array.isArray(node)) {
      for (const item of node) walk(item, depth + 1);
      return;
    }
    if (typeof node !== 'object') return;
    if (looksLikeJobNode(node)) {
      found.push({
        title: firstString(node, TITLE_KEYS),
        company: firstString(node, COMPANY_KEYS),
        url: firstString(node, URL_KEYS),
        location: firstString(node, LOCATION_KEYS),
        id: firstString(node, ID_KEYS),
        date: firstString(node, DATE_KEYS),
        salary: firstString(node, SALARY_KEYS),
        raw: node,
      });
    }
    for (const value of Object.values(node)) {
      if (value && typeof value === 'object') walk(value, depth + 1);
    }
  }

  walk(root, 0);
  return found;
}

// ---------- turning raw text into a job record -----------------------------

/**
 * Build one job record in the exact required shape.
 * Returns null when a required field is missing - callers must drop those.
 *
 * IMPORTANT: every value here must come from a page we really downloaded.
 */
function makeJob(raw) {
  const applyUrl = tidy(raw.apply_url);
  const title = tidy(raw.title);
  const company = tidy(raw.company);

  if (!/^https?:\/\//i.test(applyUrl)) return null;
  if (!title || title.length < 3) return null;
  if (!company) return null;

  const evidence = [raw.location, raw.extra, raw.salary_text, raw.employment_type_text, raw.description, raw.apply_url];
  const experience = raw.experience || detectExperience(...evidence);
  const qualification = raw.qualification || detectEducation(...evidence, title);
  const skills = Array.isArray(raw.skills) && raw.skills.length ? raw.skills : detectSkills(...evidence, title);
  const deadline = raw.deadline || detectDeadline(...evidence);
  const summary = (raw.description ? cleanSummary(raw.description) : cleanSummary(raw.extra)) ||
    `${title} opportunity at ${company} in ${tidy(raw.city) || 'Tamil Nadu'}. Re-verified live official vacancy.`;

  return {
    id: jobId(applyUrl),
    title,
    company,
    city: tidy(raw.city) || detectCity(...evidence, title) || 'Tamil Nadu',
    state: 'Tamil Nadu',
    category: tidy(raw.category) || detectCategory(title, raw.extra),
    employment_type: raw.employment_type || detectEmploymentType(...evidence),
    experience,
    is_fresher: isFresher(experience, ...evidence, title),
    qualification: qualification || null,
    skills: skills || [],
    description: summary || null,
    deadline: deadline || null,
    salary: raw.salary !== undefined && raw.salary !== null ? tidy(raw.salary) : detectSalary(...evidence),
    posted_at: raw.posted_at || null,
    expires_at: raw.expires_at || null,
    apply_url: applyUrl,
    source: tidy(raw.source) || registrableDomain(applyUrl),
    source_type: raw.source_type || 'company',
    scraped_at: new Date().toISOString(),
    verified: false,
    verify_reason: 'not_checked',
    http_status: null,
    verified_at: null,
  };
}

/** Remove duplicate jobs (same id) and any empty values. */
function dedupeJobs(jobs) {
  const byId = new Map();
  for (const job of jobs) {
    if (!job) continue;
    if (!byId.has(job.id)) byId.set(job.id, job);
  }
  return Array.from(byId.values());
}

module.exports = {
  USER_AGENT,
  fetchText,
  fetchJson,
  launchBrowser,
  closeBrowser,
  newContext,
  render,
  renderHtml,
  renderCapture,
  findJobObjects,
  makeJob,
  dedupeJobs,
  markDomainDead,
  isDomainDead,
  getDeadDomains,
  runExclusive,
  politePause,
  log,
};
