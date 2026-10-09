'use strict';

/**
 * Tier 1 - official company career pages.
 *
 * Confirmed to work from a normal machine:
 *   - Zoho        (JSON API used by their own careers site)
 *   - Freshersworld (server-rendered job listing pages)
 *
 * Corporate sites that hide their job list inside JavaScript or that block
 * non-browser traffic (TCS, Infosys, Wipro, HCLTech, Cognizant). We still try
 * them with a real headless Chromium and read the JSON their own JavaScript
 * asks for. If nothing usable comes back we simply record that in the report
 * and move on - we never invent a job to fill the gap.
 */

const cheerio = require('cheerio');
const {
  fetchText,
  fetchJson,
  makeJob,
  renderCapture,
  findJobObjects,
  markDomainDead,
} = require('../scraper');
const {
  tidy,
  clip,
  slugifyValue,
  registrableDomain,
  detectCity,
  detectEmploymentType,
  detectExperience,
  detectSalary,
  relativeDateToIso,
} = require('../util');
const { planSearches } = require('../config');

const COMPANY_NAMES = {
  'zohocorp.com': 'Zoho Corporation',
  zoho: 'Zoho Corporation',
  'tcs.com': 'Tata Consultancy Services',
  'infosys.com': 'Infosys',
  'wipro.com': 'Wipro',
  'hcltech.com': 'HCLTech',
  'cognizant.com': 'Cognizant',
};

/** Friendly display names for the report, keyed by registrable domain. */
const SITE_LABELS = Object.assign(
  {
    'tn.gov.in': 'TN Government - Job Opportunity',
    'tnpsc.gov.in': 'TNPSC - Notifications',
    'tnvelaivaaippu.gov.in': 'TN Employment & Training',
    'employment.tn.gov.in': 'TN Employment Exchange',
    'protnnetc.tn.gov.in': 'TN Private Employment Exchange',
    'mrb.tn.gov.in': 'TN Medical Services Recruitment Board (MRB)',
    'madurai.nic.in': 'Madurai District Collectorate',
    'salem.nic.in': 'Salem District Collectorate',
    'tirunelveli.nic.in': 'Tirunelveli District Collectorate',
    'coimbatore.nic.in': 'Coimbatore District Collectorate',
    'freshersworld.com': 'Freshersworld',
    'freshworks.com': 'Freshworks',
    'bosch.in': 'Robert Bosch India',
    'averydennison.com': 'Avery Dennison',
    'naukri.com': 'Naukri.com',
    'apna.co': 'apna.co',
    'indeed.co.in': 'Indeed India',
    'linkedin.com': 'LinkedIn Jobs',
    'internshala.com': 'Internshala',
  },
  COMPANY_NAMES
);

// ---------------------------------------------------------------------------
// Zoho - the careers site reads this JSON endpoint itself
// ---------------------------------------------------------------------------

const ZOHO_API =
  'https://careers.zohocorp.com/recruit/v2/public/Job_Openings?pagename=Careers&source=CareerSite';

async function scrapeZoho(notes) {
  try {
    const { json } = await fetchJson(ZOHO_API, {
      headers: { referer: 'https://careers.zohocorp.com/jobs/Careers' },
    });
    const rows = Array.isArray(json.data) ? json.data : [];
    const jobs = [];
    for (const row of rows) {
      // Only India openings - the rest cannot be a Tamil Nadu vacancy.
      if (row.Country1 && !/india/i.test(row.Country1)) continue;
      const title = tidy(row.Posting_Title || row.Job_Opening_Name);
      const url = tidy(row.$url);
      if (!title || !url) continue;

      const description = tidy(row.Job_Description);
      const job = makeJob({
        title,
        company: COMPANY_NAMES['zohocorp.com'],
        apply_url: url,
        source: registrableDomain(url),
        source_type: 'company',
        category: undefined,
        extra: `${title} ${description}`,
        description,
        employment_type: detectEmploymentType(row.Job_Type),
      });
      if (job) jobs.push(job);
    }
    notes('zohocorp.com', jobs.length ? 'ok' : 'no_listings', `${jobs.length} India opening(s)`);
    return jobs;
  } catch (error) {
    markDomainDead(ZOHO_API, error.message);
    notes('careers.zohocorp.com', 'unreachable', error.message);
    return [];
  }
}

// ---------------------------------------------------------------------------
// Freshersworld - plain HTML listing pages, one per keyword + city
// ---------------------------------------------------------------------------

function slugify(value) {
  return slugifyValue(value);
}

/** Pull the real role out of a Freshersworld SEO title. */
function cleanFreshersworldTitle(raw) {
  return tidy(raw)
    .replace(/(Less|More)+$/g, '')
    .replace(/\s*Jobs?\s+Opening\s+in\s+.*$/i, '')
    .replace(/\s+at\s+.+$/i, '')
    .trim();
}

/** Read one .job-container card. Every value comes straight off the page. */
function parseFreshersworldCard($, element) {
  const card = $(element);
  const applyUrl = tidy(card.attr('job_display_url'));
  if (!applyUrl) return null;

  const title = cleanFreshersworldTitle(card.find('.wrap-title').first().text());
  const company = tidy(card.find('h3.company-name').first().text());
  const locations = card
    .find('.job-location a')
    .map((index, anchor) => tidy($(anchor).text()))
    .get()
    .join(', ');
  const cardText = tidy(card.text());
  const postedAgo = tidy(card.find('.ago-text').first().text());
  const experienceText = tidy(card.find('.experience').first().text());

  return makeJob({
    title,
    company,
    apply_url: applyUrl,
    source: registrableDomain(applyUrl),
    source_type: 'company',
    location: locations,
    extra: cardText,
    salary: detectSalary(cardText),
    experience: detectExperience(experienceText) || detectExperience(cardText),
    employment_type: detectEmploymentType(cardText),
    posted_at: relativeDateToIso(postedAgo),
  });
}

async function scrapeFreshersworld(ctx) {
  const notes = ctx.note;
  const jobs = [];
  const base = 'https://www.freshersworld.com';
  let fetches = 0;

  const plan = planSearches(ctx.keywords, ctx.cities, ctx.pageLimit);

  for (const { keyword, city } of plan) {
    if (Date.now() > ctx.deadline) break;

    const path = `/jobs/jobsearch/${slugify(keyword)}-jobs-in-${slugify(city === 'Tamil Nadu' ? 'chennai' : city)}`;
    const url = `${base}${path}`;
    fetches += 1;
    try {
      const response = await fetchText(url, { headers: { referer: `${base}/jobs` } });
      if (response.status >= 400) {
        // A 404 just means "we have no listing for that keyword in that city".
        continue;
      }
      const $ = cheerio.load(response.body);
      const cards = $('.job-container');
      cards.each((index, element) => {
        const job = parseFreshersworldCard($, element);
        if (job) jobs.push(job);
      });
    } catch (error) {
      ctx.log(`  freshersworld fetch failed (${path}): ${clip(error.message, 120)}`);
    }
    if (jobs.length >= ctx.limit) break;
  }

  notes(
    'freshersworld.com',
    jobs.length ? 'ok' : 'no_listings',
    `${jobs.length} job(s) from ${fetches} listing page(s)`
  );
  return jobs;
}

// ---------------------------------------------------------------------------
// Big IT employers whose careers sites are JavaScript-only
// ---------------------------------------------------------------------------

const SPA_COMPANIES = [
  {
    id: 'tcs.com',
    pageUrl: 'https://ibegin.tcs.com/',
    jsonUrl: 'https://ibegin.tcs.com/iBegin/api/careers/getJobPost',
    headers: { referer: 'https://ibegin.tcs.com/', origin: 'https://ibegin.tcs.com' },
    urlIncludes: ['career', 'job'],
  },
  {
    id: 'infosys.com',
    pageUrl: 'https://career.infosys.com/joblist',
    urlIncludes: ['job', 'search', 'requisition', 'api'],
  },
  {
    id: 'wipro.com',
    pageUrl: 'https://careers.wipro.com/search/?q=software&locationsearch=India',
    urlIncludes: ['search', 'job', 'api'],
  },
  {
    id: 'hcltech.com',
    pageUrl: 'https://www.hcltech.com/careers',
    urlIncludes: ['career', 'job', 'api'],
  },
  {
    id: 'cognizant.com',
    pageUrl: 'https://careers.cognizant.com/global/en/search-results?keywords=',
    urlIncludes: ['search', 'job', 'api'],
  },
];

/** Pull a plain-text location out of a schema.org jobLocation block. */
function locationFromLdJson(jobLocation) {
  if (!jobLocation) return '';
  const entries = Array.isArray(jobLocation) ? jobLocation : [jobLocation];
  const parts = [];
  for (const entry of entries) {
    const address = entry && entry.address ? entry.address : entry;
    if (!address) continue;
    if (typeof address === 'string') parts.push(address);
    else {
      parts.push(
        [address.addressLocality, address.addressRegion, address.addressCountry && address.addressCountry.name]
          .filter(Boolean)
          .join(', ')
      );
    }
  }
  return tidy(parts.filter(Boolean).join(' | '));
}

/** Pull readable pay out of a schema.org baseSalary block. */
function salaryFromLdJson(baseSalary) {
  if (!baseSalary) return '';
  const value = baseSalary.value || baseSalary;
  if (typeof value === 'string') return tidy(value);
  if (typeof value === 'number') return String(value);
  const min = value.minValue;
  const max = value.maxValue;
  const unit = tidy(value.unitText);
  if (min && max) return `${min} - ${max} ${unit}`.trim();
  if (min || max) return `${min || max} ${unit}`.trim();
  return '';
}

/** Read schema.org JobPosting blocks that a page embedded for search engines. */
function jobPostingsFromLdJson(html, fallbackCompany) {
  const out = [];
  const $ = cheerio.load(html);
  $('script[type="application/ld+json"]').each((index, element) => {
    const raw = $(element).contents().text();
    if (!raw || !/JobPosting/i.test(raw)) return;
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      return;
    }
    const list = Array.isArray(parsed) ? parsed : [parsed];
    for (const entry of list) {
      if (!entry || String(entry['@type'] || '').toLowerCase() !== 'jobposting') continue;
      out.push({
        title: entry.title || entry.name,
        company: (entry.hiringOrganization && entry.hiringOrganization.name) || fallbackCompany,
        url: entry.url || (entry.mainEntityOfPage && entry.mainEntityOfPage['@id']),
        location: locationFromLdJson(entry.jobLocation),
        date: entry.datePosted || null,
        salary: salaryFromLdJson(entry.baseSalary),
        employmentType: Array.isArray(entry.employmentType)
          ? entry.employmentType.join(', ')
          : entry.employmentType,
      });
    }
  });
  return out;
}

/** Turn one harvested JSON / ld+json candidate into a job record. */
function jobFromCandidate(candidate, companyName, baseUrl) {
  let applyUrl = tidy(candidate.url);
  if (applyUrl && !/^https?:/i.test(applyUrl)) {
    try {
      applyUrl = new URL(applyUrl, baseUrl).toString();
    } catch (error) {
      return null;
    }
  }
  if (!/^https?:\/\//i.test(applyUrl)) return null;

  const location = tidy(candidate.location);
  const city = detectCity(location, candidate.title);
  // If the site told us a location but none of it is in Tamil Nadu, drop it.
  if (location && !city) return null;

  return makeJob({
    title: candidate.title,
    company: candidate.company || companyName,
    apply_url: applyUrl,
    city: city || undefined,
    source: registrableDomain(applyUrl),
    source_type: 'company',
    location,
    extra: `${tidy(candidate.title)} ${location} ${tidy(candidate.salary)}`,
    salary: candidate.salary || undefined,
    employment_type: candidate.employmentType || undefined,
    posted_at: candidate.date || null,
  });
}

module.exports = {
  id: 'company-careers',
  label: 'Company career pages (Zoho, Freshersworld, TCS, Infosys, Wipro, HCLTech, Cognizant)',
  tier: 1,
  COMPANY_NAMES,
  SITE_LABELS,
  scrapeZoho,
  scrapeFreshersworld,
  SPA_COMPANIES,
  jobPostingsFromLdJson,
  jobFromCandidate,

  async scrape(ctx) {
    const notes = ctx.note;
    const collected = [];

    // These two are different websites, so they may run at the same time.
    const settled = await Promise.allSettled([scrapeZoho(notes), scrapeFreshersworld(ctx)]);
    for (const outcome of settled) {
      if (outcome.status === 'fulfilled') collected.push(...outcome.value);
      else ctx.log(`  a company source failed and was skipped: ${outcome.reason}`);
    }

    // The JavaScript-only corporate sites are slower, so only try them while
    // we still have time left in the scraping budget.
    if (!ctx.skipSpaSites) {
      for (const company of SPA_COMPANIES) {
        if (Date.now() > ctx.deadline) {
          notes(company.id, 'skipped', 'out of time budget for this run');
          continue;
        }
        const jobs = await scrapeSpaCompany(company, ctx);
        collected.push(...jobs);
        ctx.log(`  ${company.id}: ${jobs.length} job(s)`);
      }
    }

    ctx.log(`  ${module.exports.label}: ${collected.length} record(s)`);
    return collected;
  },
};

/** Try one JavaScript-only careers site. Never throws. */
async function scrapeSpaCompany(company, ctx) {
  const name = COMPANY_NAMES[company.id] || company.id;
  try {
    const candidates = [];

    if (company.jsonUrl) {
      const { json } = await fetchJson(company.jsonUrl, { headers: company.headers });
      candidates.push(...findJobObjects(json));
    }

    if (!candidates.length) {
      let payload;
      try {
        payload = await renderCapture(await ctx.getContext(), company.pageUrl, {
          urlIncludes: company.urlIncludes,
          settleMs: 7000,
        });
      } catch (browserError) {
        ctx.log(`  ${company.id} skipped: browser unavailable (${browserError.message.split('\n')[0]})`);
        if (!ctx.hasNote(company.id)) ctx.note(company.id, 'blocked', 'headless browser unavailable in this environment');
        return [];
      }
      const { json, dom } = payload;
      for (const response of json) candidates.push(...findJobObjects(response.json));
      candidates.push(...jobPostingsFromLdJson(dom.html, name));

      // HCLTech's old careers URL now lands on their blog - say so clearly
      // instead of pretending we found nothing.
      if (/\/blogs?\b/i.test(dom.finalUrl) && !/career/i.test(dom.finalUrl)) {
        ctx.note(company.id, 'unavailable', 'careers page now redirects to a blog, there is no job list');
        return [];
      }
    }

    const jobs = [];
    for (const candidate of candidates) {
      const job = jobFromCandidate(candidate, name, company.pageUrl);
      if (job) jobs.push(job);
    }

    if (jobs.length) ctx.note(company.id, 'ok', `${jobs.length} job(s)`);
    else if (!ctx.hasNote(company.id)) {
      ctx.note(company.id, 'blocked', 'no job records could be read from this site');
    }
    return jobs;
  } catch (error) {
    markDomainDead(registrableDomain(company.pageUrl), error.message);
    if (!ctx.hasNote(company.id)) ctx.note(company.id, 'blocked', clip(error.message, 140));
    return [];
  }
}
