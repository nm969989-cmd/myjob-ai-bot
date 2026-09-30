'use strict';

/**
 * Tier 1 - Tamil Nadu government job portals.
 *
 * Sites covered:
 *   - www.tn.gov.in            "Job Opportunity" list (loaded by AJAX)
 *   - www.tnpsc.gov.in         TNPSC recruitment notifications
 *   - tnvelaivaaippu.gov.in    Department of Employment & Training
 *   - employment.tn.gov.in     Employment Exchange
 *   - protntenetc.tn.gov.in    Private Employment Exchange portal
 *
 * Every site is wrapped in try/catch. If a site is blocked, offline or dead we
 * write a note for the report and carry on with the others - one bad site must
 * never stop the run.
 */

const cheerio = require('cheerio');
const { fetchText, makeJob, markDomainDead } = require('../scraper');
const { tidy, registrableDomain, detectCity, detectEmploymentType } = require('../util');

const COMPANY = 'Government of Tamil Nadu';

/** Words that mean "this really is a job posting". */
const GOV_INCLUDE = /recruitment|vacanc|advertisement|applications? (?:are )?invited|invited for|engagement of|appointment to the post|fellowship|apprentice|contract (?:post|basis)|direct recruitment|notification/i;

/** Words that mean "this is paperwork about an exam, not a job ad". */
const GOV_EXCLUDE = /answer key|question paper|result|merit list|cut ?off|hall ticket|admit card|instructions to|checklist|syllabus|counselling schedule|verification of certificates|model question/i;

function clipTitle(value) {
  const text = tidy(value);
  if (text.length <= 180) return text;
  const cut = text.slice(0, 180);
  const lastSpace = cut.lastIndexOf(' ');
  return cut.slice(0, lastSpace > 60 ? lastSpace : 179) + '\u2026';
}

/** Turn a link we read on a government page into a job record. */
function govJobFromLink({ title, href, baseUrl, extraText, sourceType }) {
  const cleanTitle = clipTitle(title);
  if (!cleanTitle || !href) return null;
  let absolute;
  try {
    absolute = new URL(href, baseUrl).toString();
  } catch (error) {
    return null;
  }
  if (!/^https?:\/\//i.test(absolute)) return null;

  const haystack = `${cleanTitle} ${tidy(extraText)}`;
  return makeJob({
    title: cleanTitle,
    company: COMPANY,
    city: detectCity(haystack) || 'Tamil Nadu',
    apply_url: absolute,
    source: registrableDomain(baseUrl),
    source_type: sourceType || 'government',
    category: 'Government',
    extra: haystack,
    employment_type: detectEmploymentType(haystack),
  });
}

/** Read every useful link out of an already downloaded government page. */
function collectGovLinks(html, baseUrl, options) {
  const opts = options || {};
  const minText = opts.minText || 18;
  const jobs = [];
  const seen = new Set();
  const $ = cheerio.load(html);

  const consider = (caption, href, contextText) => {
    if (!caption || !href || href === '#' || href.startsWith('javascript')) return;
    if (caption.length < minText) return;
    if (!GOV_INCLUDE.test(caption) || GOV_EXCLUDE.test(caption)) return;
    const job = govJobFromLink({ title: caption, href, baseUrl, extraText: contextText });
    if (!job || seen.has(job.id)) return;
    seen.add(job.id);
    jobs.push(job);
  };

  // Pass 1: links inside table rows and list items (the normal case).
  $('tr, li').each((index, block) => {
    const $block = $(block);
    const contextText = tidy($block.text());
    $block.find('a[href]').each((i, anchor) => consider(tidy($(anchor).text()), $(anchor).attr('href'), contextText));
  });

  // Pass 2: if the page is built from plain divs, fall back to every anchor.
  if (jobs.length === 0) {
    $('a[href]').each((index, anchor) => {
      const caption = tidy($(anchor).text());
      consider(caption, $(anchor).attr('href'), caption);
    });
  }

  return jobs;
}

// ---------------------------------------------------------------------------
// The individual sites
// ---------------------------------------------------------------------------

/**
 * tn.gov.in keeps its job list in a separate AJAX file
 * (job_opportunity_list.php) which we can fetch directly.
 */
async function scrapeTnGov(notes) {
  const baseUrl = 'https://www.tn.gov.in/job_opportunity.php';
  const listUrl = 'https://www.tn.gov.in/job_opportunity_list.php';
  try {
    const response = await fetchText(listUrl, {
      headers: {
        'x-requested-with': 'XMLHttpRequest',
        referer: baseUrl,
        accept: 'text/html, */*; q=0.01',
      },
    });
    if (response.status >= 400) throw new Error(`HTTP ${response.status}`);
    const jobs = collectGovLinks(response.body, baseUrl, { minText: 18 });
    notes('tn.gov.in', jobs.length ? 'ok' : 'no_listings', `${jobs.length} government job notice(s)`);
    return jobs;
  } catch (error) {
    markDomainDead(baseUrl, error.message);
    notes('tn.gov.in', 'unreachable', error.message);
    return [];
  }
}

/** TNPSC publishes its recruitment notifications in one big table. */
async function scrapeTnpsc(notes) {
  const baseUrl = 'https://www.tnpsc.gov.in/English/Notification.aspx';
  try {
    const response = await fetchText(baseUrl, { headers: { referer: 'https://www.tnpsc.gov.in/' } });
    if (response.status >= 400) throw new Error(`HTTP ${response.status}`);
    const jobs = collectGovLinks(response.body, baseUrl, { minText: 25 });
    notes('tnpsc.gov.in', jobs.length ? 'ok' : 'no_listings', `${jobs.length} TNPSC notification(s)`);
    return jobs;
  } catch (error) {
    markDomainDead(baseUrl, error.message);
    notes('tnpsc.gov.in', 'unreachable', error.message);
    return [];
  }
}

/** Department of Employment & Training (tnvelaivaaippu.gov.in). */
async function scrapeTnEmploymentPortal(notes) {
  const baseUrl = 'https://tnvelaivaaippu.gov.in/';
  try {
    const response = await fetchText(baseUrl);
    if (response.status >= 400) throw new Error(`HTTP ${response.status}`);
    const jobs = collectGovLinks(response.body, baseUrl, { minText: 15 });
    notes(
      'tnvelaivaaippu.gov.in',
      jobs.length ? 'ok' : 'no_listings',
      `${jobs.length} notice(s) on the Employment & Training portal`
    );
    return jobs;
  } catch (error) {
    markDomainDead(baseUrl, error.message);
    notes('tnvelaivaaippu.gov.in', 'unreachable', error.message);
    return [];
  }
}

/**
 * Small helper for the two employment-exchange portals that are often only
 * reachable from inside the state network. We try once, then move on.
 */
async function probeExchangePortal(baseUrl, siteId, notes) {
  try {
    const response = await fetchText(baseUrl, { attempts: 1, timeout: 15000 });
    if (response.status >= 400) throw new Error(`HTTP ${response.status}`);
    const jobs = collectGovLinks(response.body, baseUrl, { minText: 18 });
    notes(siteId, jobs.length ? 'ok' : 'no_listings', `${jobs.length} listing(s)`);
    return jobs;
  } catch (error) {
    markDomainDead(baseUrl, error.message);
    notes(siteId, 'unreachable', error.message);
    return [];
  }
}

/** Medical Services Recruitment Board (mrb.tn.gov.in). */
async function scrapeMrb(notes) {
  const baseUrl = 'https://www.mrb.tn.gov.in/';
  try {
    const response = await fetchText(baseUrl, { timeout: 15000 });
    if (response.status >= 400) throw new Error(`HTTP ${response.status}`);
    const jobs = collectGovLinks(response.body, baseUrl, { minText: 20 });
    notes('mrb.tn.gov.in', jobs.length ? 'ok' : 'no_listings', `${jobs.length} notification(s) on Medical Services Recruitment Board`);
    return jobs;
  } catch (error) {
    notes('mrb.tn.gov.in', 'unreachable', error.message);
    return [];
  }
}

const DISTRICT_SITES = [
  { id: 'madurai', name: 'Madurai' },
  { id: 'salem', name: 'Salem' },
  { id: 'tirunelveli', name: 'Tirunelveli' },
  { id: 'coimbatore', name: 'Coimbatore' },
];

/** Official District Collectorate recruitment pages on NIC / S3WaaS. */
async function scrapeDistrictPortals(notes) {
  const jobs = [];
  for (const dist of DISTRICT_SITES) {
    const baseUrl = `https://${dist.id}.nic.in/notice_category/recruitment/`;
    try {
      const response = await fetchText(baseUrl, { attempts: 1, timeout: 15000 });
      if (response.status >= 400) continue;
      const $ = cheerio.load(response.body);
      let foundInDist = 0;
      $('table tbody tr').each((i, row) => {
        const $row = $(row);
        const title = tidy($row.find('td').eq(0).text() || $row.find('a').first().text());
        const href = $row.find('a[href]').first().attr('href');
        if (!title || !href || title.length < 15) return;
        if (!GOV_INCLUDE.test(title) || GOV_EXCLUDE.test(title)) return;
        const job = govJobFromLink({
          title,
          href,
          baseUrl,
          extraText: `${dist.name} District Collectorate ${title}`,
        });
        if (job) {
          job.city = dist.name;
          jobs.push(job);
          foundInDist++;
        }
      });
      notes(`${dist.id}.nic.in`, foundInDist ? 'ok' : 'no_listings', `${foundInDist} notice(s) on ${dist.name} District portal`);
    } catch (e) {
      notes(`${dist.id}.nic.in`, 'unreachable', e.message);
    }
  }
  return jobs;
}

module.exports = {
  id: 'govt-tn',
  label: 'Tamil Nadu government portals',
  tier: 1,
  COMPANY,
  collectGovLinks,

  async scrape(ctx) {
    const notes = ctx.note;
    // These official sites are independent, so they run in parallel safely.
    const settled = await Promise.allSettled([
      scrapeTnGov(notes),
      scrapeTnpsc(notes),
      scrapeTnEmploymentPortal(notes),
      scrapeMrb(notes),
      scrapeDistrictPortals(notes),
      probeExchangePortal('https://employment.tn.gov.in/', 'employment.tn.gov.in', notes),
      probeExchangePortal('https://protnnetc.tn.gov.in/', 'protnnetc.tn.gov.in', notes),
    ]);

    const collected = [];
    for (const outcome of settled) {
      if (outcome.status === 'fulfilled') collected.push(...outcome.value);
      else ctx.log(`  a government source failed and was skipped: ${outcome.reason}`);
    }
    ctx.log(`  ${module.exports.label}: ${collected.length} record(s)`);
    return collected;
  },
};
