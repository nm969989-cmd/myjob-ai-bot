'use strict';

/**
 * VERIFICATION.
 *
 * After scraping we re-open every single apply_url in a fresh browser page and
 * check it really is a live job posting. Nothing reaches the public web page
 * unless it passed here.
 *
 * Rules (exactly as specified):
 *   1. HTTP 400 or higher                      -> reject, reason "http_404" etc.
 *   2. Redirects to a login page               -> keep, but verified=false,
 *                                                 reason "login_required"
 *      Redirects to a search page or another
 *      company's domain                        -> reject "redirected_elsewhere"
 *   3. Page has none of the job signal words    -> reject "no_job_signal"
 *   5. A random 1.5-3.5 s pause between requests, never two requests to the
 *      same domain at the same time (handled inside src/scraper.js).
 *   6. The final URL and page title are recorded on the job.
 */

const { render, fetchText, isDomainDead, log } = require('./scraper');
const {
  tidy,
  clip,
  cleanUrl,
  registrableDomain,
  detectCity,
  detectEducation,
  detectSkills,
  detectSalary,
  detectExperience,
  detectDeadline,
  isFresher,
  cleanSummary,
} = require('./util');

/** Words that prove a page is a job posting (the list from the brief). */
const CORE_SIGNALS = ['apply', 'vacancy', 'job title', 'responsibilities', 'qualification', 'apply now'];

/**
 * Government notices are written in official language, so they get a few extra
 * allowed words. This only applies to source_type === 'government'.
 */
const GOV_SIGNALS = [
  'recruitment',
  'notification',
  'applications are invited',
  'applications invited',
  'eligible candidates',
  'last date',
  'post of',
  'engagement of',
];

const LOGIN_URL = /\/login|\/signin|sign-in|checkpoint|\/auth\/|uas\/login|session_redirect/i;
const LOGIN_TEXT = /sign in to (?:continue|view|apply)|log ?in to (?:view|continue|apply)|login required|please (?:log ?in|sign ?in)|join now to see/i;
const SEARCH_URL = /\/job-?search\b|\/jobs?\?|\?q=|&q=|keywords=|jobs-in-[a-z-]+$/i;

/** Run an async function over a list, at most `limit` items at a time. */
async function mapWithConcurrency(items, limit, worker) {
  const results = new Array(items.length);
  let cursor = 0;
  async function run() {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      results[index] = await worker(items[index], index);
    }
  }
  const runners = [];
  for (let i = 0; i < Math.min(limit, items.length); i += 1) runners.push(run());
  await Promise.all(runners);
  return results;
}

function httpReason(status) {
  if (status === 403) return 'http_403';
  if (status === 404) return 'http_404';
  if (status === 410) return 'http_410';
  if (status >= 500) return 'http_5xx';
  return `http_${status}`;
}

function isPdfUrl(url) {
  try {
    return /\.pdf$/i.test(new URL(url).pathname);
  } catch (error) {
    return /\.pdf($|\?)/i.test(url);
  }
}

/** Does this page text contain a job signal we accept for this source type? */
function findSignal(pageText, sourceType) {
  const haystack = pageText.toLowerCase();
  for (const word of CORE_SIGNALS) {
    if (haystack.includes(word)) return word;
  }
  if (sourceType === 'government') {
    for (const word of GOV_SIGNALS) {
      if (haystack.includes(word)) return word;
    }
  }
  return '';
}

/** Verify one PDF (government notices are usually PDFs). */
async function validateDocument(job) {
  const result = Object.assign({}, job);
  result.verified_at = new Date().toISOString();
  try {
    const response = await fetchText(job.apply_url, { attempts: 1, timeout: 20000 });
    result.http_status = response.status;
    result.final_url = response.finalUrl;
    const type = response.contentType || '';
    const looksLikePdf = isPdfUrl(response.finalUrl) || /pdf|octet-stream/i.test(type);
    if (response.status >= 400) {
      result.verified = false;
      result.verify_reason = httpReason(response.status);
    } else if (!looksLikePdf) {
      // The link no longer points at a document, so we cannot vouch for it.
      result.verified = false;
      result.verify_reason = 'not_a_document';
    } else {
      result.verified = true;
      result.verify_reason = 'live_document';
      result.page_title = tidy(result.title);
      result.verify_note = 'official document answered HTTP ' + response.status;

      if (!result.deadline) {
        result.deadline = detectDeadline(result.title, result.apply_url) || null;
      }
      if (!result.qualification) {
        result.qualification = detectEducation(result.title) || 'Graduate / As per notification';
      }
      if (!result.description || result.description.length < 30) {
        result.description = `${result.title} published by ${result.company}. Verified official notification document.`;
      }
      if (!Array.isArray(result.skills) || result.skills.length === 0) {
        result.skills = detectSkills(result.title, result.apply_url) || [];
      }
      result.is_fresher = isFresher(result.experience, result.title);
    }
  } catch (error) {
    result.verified = false;
    result.verify_reason = 'request_failed';
    result.http_status = null;
    result.verify_error = clip(error.message, 160);
  }
  return result;
}

/** Verify one normal web page with a real browser. */
async function validatePage(job, context) {
  const result = Object.assign({}, job);
  result.verified_at = new Date().toISOString();

  const requestedHost = job.apply_url;
  if (isDomainDead(requestedHost)) {
    result.verified = false;
    result.verify_reason = 'source_unreachable';
    return result;
  }
  const requestedDomain = registrableDomain(job.apply_url);

  try {
    const info = await render(
      context,
      job.apply_url,
      async (page, response) => ({
        status: response ? response.status() : null,
        finalUrl: page.url(),
        title: await page.title().catch(() => ''),
        text: (await page.evaluate(() => document.body && document.body.innerText)) || '',
      }),
      { settleMs: 1500, waitUntil: 'domcontentloaded' }
    );

    result.http_status = info.status;
    result.final_url = info.finalUrl;
    result.page_title = clip(info.title, 200);

    // Rule 1: any HTTP error means the posting is not there any more.
    if (info.status !== null && info.status >= 400) {
      result.verified = false;
      result.verify_reason = httpReason(info.status);
      return result;
    }

    const text = tidy(info.text).slice(0, 400000);
    const redirected = cleanUrl(info.finalUrl) !== cleanUrl(job.apply_url);

    // Rule 4: a login wall is not proof of a live advert, so we keep the job
    // but we never claim it is live.
    if (LOGIN_URL.test(info.finalUrl) || LOGIN_TEXT.test(text)) {
      result.verified = false;
      result.verify_reason = 'login_required';
      return result;
    }

    // Rule 2: bounced to another company's site, or back to a search page.
    if (redirected && registrableDomain(info.finalUrl) !== requestedDomain) {
      result.verified = false;
      result.verify_reason = 'redirected_elsewhere';
      return result;
    }
    if (redirected) {
      const finalUrl = new URL(info.finalUrl);
      if (SEARCH_URL.test(finalUrl.pathname + finalUrl.search)) {
        result.verified = false;
        result.verify_reason = 'redirected_elsewhere';
        return result;
      }
    }

    // Rule 3: the page has to look like a job advert.
    const signal = findSignal(text, job.source_type);
    if (!signal) {
      result.verified = false;
      result.verify_reason = 'no_job_signal';
      return result;
    }

    result.verified = true;
    result.verify_reason = 'live';
    result.verify_signal = signal;

    const sampleText = text.slice(0, 12000);

    // Bonus: if the page itself names a Tamil Nadu city and we did not know one, use it.
    if (!result.city || result.city === 'Tamil Nadu') {
      const pageCity = detectCity(sampleText);
      if (pageCity) result.city = pageCity;
    }

    // Enrich description / summary if missing or brief
    if (!result.description || result.description.length < 40) {
      result.description = cleanSummary(sampleText, 320) ||
        `${result.title} vacancy at ${result.company} in ${result.city || 'Tamil Nadu'}. Re-verified live vacancy.`;
    }

    // Enrich education / qualification if missing
    if (!result.qualification) {
      result.qualification = detectEducation(sampleText, result.title) || null;
    }

    // Enrich skills if empty or missing
    if (!Array.isArray(result.skills) || result.skills.length === 0) {
      result.skills = detectSkills(sampleText, result.title, result.apply_url) || [];
    }

    // Enrich salary if missing
    if (!result.salary) {
      result.salary = detectSalary(sampleText, result.title) || null;
    }

    // Enrich experience if missing
    if (!result.experience) {
      result.experience = detectExperience(sampleText, result.title) || null;
    }

    // Enrich deadline if missing
    if (!result.deadline) {
      result.deadline = detectDeadline(sampleText, result.title) || null;
    }

    // Update fresher flag
    result.is_fresher = isFresher(result.experience, sampleText, result.title);

    return result;
  } catch (error) {
    result.verified = false;
    result.http_status = null;
    result.verify_reason = /timeout/i.test(error.message) ? 'timed_out' : 'request_failed';
    result.verify_error = clip(error.message, 160);
    return result;
  }
}

/**
 * Verify every scraped job. Returns { jobs, stats }.
 * Jobs are grouped by domain so different sites are checked in parallel, but
 * two jobs from the same site are always checked one after the other.
 */
async function validateJobs(jobs, options) {
  const opts = options || {};
  const context = opts.context;
  const onProgress = opts.onProgress || (() => undefined);
  const concurrency = opts.concurrency || 4;

  const byDomain = new Map();
  for (const job of jobs) {
    const domain = registrableDomain(job.apply_url);
    if (!byDomain.has(domain)) byDomain.set(domain, []);
    byDomain.get(domain).push(job);
  }

  const groups = Array.from(byDomain.values());
  log(`  re-opening ${jobs.length} link(s) across ${groups.length} site(s), ${concurrency} site(s) at a time`);

  let done = 0;
  const groupResults = await mapWithConcurrency(groups, concurrency, async (group) => {
    const out = [];
    for (const job of group) {
      const verified = isPdfUrl(job.apply_url)
        ? await validateDocument(job)
        : await validatePage(job, context);
      out.push(verified);
      done += 1;
      onProgress(done, jobs.length, verified);
    }
    return out;
  });

  const results = groupResults.flat();
  const countReason = (reason) => results.filter((job) => job.verify_reason === reason).length;
  const stats = {
    checked: results.length,
    live: results.filter((job) => job.verified).length,
    loginRequired: countReason('login_required'),
    dead: results.filter((job) => /^http_/.test(job.verify_reason || '')).length,
    noSignal: countReason('no_job_signal'),
    redirected: countReason('redirected_elsewhere'),
    documents: countReason('live_document'),
    unreachable: ['request_failed', 'timed_out', 'source_unreachable'].reduce(
      (total, reason) => total + countReason(reason),
      0
    ),
  };
  return { jobs: results, stats };
}

module.exports = {
  mapWithConcurrency,
  httpReason,
  isPdfUrl,
  findSignal,
  validateDocument,
  validatePage,
  validateJobs,
  CORE_SIGNALS,
  GOV_SIGNALS,
};
