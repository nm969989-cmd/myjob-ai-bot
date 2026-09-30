'use strict';

/**
 * Tier 1 - Direct Enterprise ATS APIs (Zero Bot Blocking).
 *
 * Scrapes job postings directly from official company applicant tracking systems
 * that expose open public JSON REST APIs with zero anti-bot barriers or Cloudflare blocks.
 *
 * Current supported ATS APIs:
 *   - SmartRecruiters: Freshworks, Robert Bosch India, Avery Dennison
 */

const { fetchJson, makeJob, markDomainDead } = require('../scraper');
const {
  tidy,
  detectCity,
  detectCategory,
  detectSkills,
  detectEducation,
  detectExperience,
  isFresher,
  cleanSummary,
  relativeDateToIso,
} = require('../util');

const SMART_RECRUITERS_COMPANIES = [
  { id: 'Freshworks', name: 'Freshworks', domain: 'freshworks.com' },
  { id: 'BoschGroup', name: 'Robert Bosch India', domain: 'bosch.in' },
  { id: 'AveryDennison', name: 'Avery Dennison', domain: 'averydennison.com' },
];

const WORKDAY_COMPANIES = [
  {
    name: 'Kyndryl',
    domain: 'kyndryl.com',
    apiUrl: 'https://kyndryl.wd5.myworkdayjobs.com/wday/cxs/kyndryl/KyndrylProfessionalCareers/jobs',
    siteBase: 'https://kyndryl.wd5.myworkdayjobs.com/KyndrylProfessionalCareers',
    origin: 'https://kyndryl.wd5.myworkdayjobs.com',
    query: 'Chennai',
  },
  {
    name: 'AstraZeneca',
    domain: 'astrazeneca.com',
    apiUrl: 'https://astrazeneca.wd3.myworkdayjobs.com/wday/cxs/astrazeneca/Careers/jobs',
    siteBase: 'https://astrazeneca.wd3.myworkdayjobs.com/Careers',
    origin: 'https://astrazeneca.wd3.myworkdayjobs.com',
    query: 'Chennai',
  },
  {
    name: 'PayPal',
    domain: 'paypal.com',
    apiUrl: 'https://paypal.wd1.myworkdayjobs.com/wday/cxs/paypal/jobs/jobs',
    siteBase: 'https://paypal.wd1.myworkdayjobs.com/jobs',
    origin: 'https://paypal.wd1.myworkdayjobs.com',
    query: 'Chennai',
  },
];

/** Check if location text belongs to a Tamil Nadu city or region. */
function isTamilNaduLocation(loc) {
  if (!loc) return false;
  const text = (
    (loc.city || '') + ' ' +
    (loc.region || '') + ' ' +
    (loc.fullLocation || '')
  ).toLowerCase();
  return /chennai|coimbatore|madurai|trichy|tiruchirappalli|salem|tirunelveli|erode|vellore|thanjavur|tiruppur|tamil\s*nadu|\btn\b/i.test(text);
}

/** Fetch and parse jobs from SmartRecruiters for one company. */
async function scrapeSmartRecruitersCompany(company, ctx) {
  const url = `https://api.smartrecruiters.com/v1/companies/${company.id}/postings?country=in`;
  const jobs = [];

  try {
    const { json } = await fetchJson(url, {
      headers: {
        accept: 'application/json',
        referer: `https://jobs.smartrecruiters.com/${company.id}`,
      },
      timeout: 15000,
    });

    const list = Array.isArray(json.content) ? json.content : [];
    for (const p of list) {
      if (!p || !p.id || !p.name) continue;
      if (!isTamilNaduLocation(p.location)) continue;

      const title = tidy(p.name);
      const applyUrl = `https://jobs.smartrecruiters.com/${company.id}/${p.id}`;
      const city = detectCity(p.location.city, p.location.fullLocation, title) || 'Tamil Nadu';
      const rawExp = p.experienceLevel ? tidy(p.experienceLevel.label) : '';
      const rawType = p.typeOfEmployment ? tidy(p.typeOfEmployment.label) : '';
      const func = p.function ? tidy(p.function.label) : '';
      const ind = p.industry ? tidy(p.industry.label) : '';
      const evidence = `${title} ${func} ${ind} ${city} ${rawExp} ${rawType}`;

      const skills = detectSkills(title, func, ind);
      const qualification = detectEducation(title, func) || null;
      const experience = detectExperience(rawExp, title) || (rawExp || null);
      const employmentType = rawType || 'Full-time';
      const postedAt = p.releasedDate ? p.releasedDate.slice(0, 10) : null;
      const summary = `${title} vacancy at ${company.name} in ${city}. Official direct application.`;

      const job = makeJob({
        title,
        company: company.name,
        apply_url: applyUrl,
        city,
        state: 'Tamil Nadu',
        category: detectCategory(title, func, ind),
        employment_type: employmentType,
        experience,
        qualification,
        skills,
        description: summary,
        posted_at: postedAt,
        source: company.domain,
        source_type: 'company',
        extra: evidence,
      });

      if (job) jobs.push(job);
      if (jobs.length >= ctx.limit) break;
    }

    ctx.note(
      company.domain,
      jobs.length ? 'ok' : 'no_listings',
      `${jobs.length} opening(s) in Tamil Nadu`
    );
  } catch (error) {
    ctx.log(`  SmartRecruiters failed for ${company.name}: ${error.message}`);
    ctx.note(company.domain, 'unreachable', error.message);
    markDomainDead(company.domain, error.message);
  }

  return jobs;
}

/** Fetch and parse jobs from Workday CXS for one company. */
async function scrapeWorkdayCompany(company, ctx) {
  const jobs = [];

  try {
    const { json } = await fetchJson(company.apiUrl, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
        origin: company.origin,
        referer: `${company.siteBase}/`,
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
      body: JSON.stringify({
        appliedFacets: {},
        limit: 20,
        offset: 0,
        searchText: company.query || 'Chennai',
      }),
      timeout: 15000,
    });

    const list = Array.isArray(json.jobPostings) ? json.jobPostings : [];
    for (const p of list) {
      if (!p || !p.title || !p.externalPath) continue;

      const title = tidy(p.title);
      const locText = tidy(p.locationsText || '');
      const isTN = isTamilNaduLocation({ fullLocation: locText, city: locText }) ||
                   /chennai|tamil\s*nadu|\btn\b/i.test(locText) ||
                   /chennai/i.test(title);
      if (!isTN) continue;

      const applyUrl = `${company.siteBase}${p.externalPath}`;
      const city = detectCity(locText, title) || 'Chennai';
      const postedAt = p.postedOn ? relativeDateToIso(p.postedOn) : null;
      const skills = detectSkills(title, locText);
      const summary = `${title} opening at ${company.name} in ${city}. Verified Workday direct application.`;

      const job = makeJob({
        title,
        company: company.name,
        apply_url: applyUrl,
        city,
        state: 'Tamil Nadu',
        category: detectCategory(title),
        employment_type: 'Full-time',
        experience: detectExperience(title),
        skills,
        description: summary,
        posted_at: postedAt,
        source: company.domain,
        source_type: 'company',
        extra: `${title} ${company.name} ${city} ${locText}`,
      });

      if (job) jobs.push(job);
      if (jobs.length >= ctx.limit) break;
    }

    ctx.note(
      company.domain,
      jobs.length ? 'ok' : 'no_listings',
      `${jobs.length} opening(s) in Tamil Nadu`
    );
  } catch (error) {
    ctx.log(`  Workday failed for ${company.name}: ${error.message}`);
    ctx.note(company.domain, 'unreachable', error.message);
  }

  return jobs;
}

module.exports = {
  id: 'tech-ats',
  label: 'Direct Enterprise ATS APIs (Freshworks, Bosch, Kyndryl, AstraZeneca, Avery Dennison)',
  tier: 1,
  SMART_RECRUITERS_COMPANIES,
  WORKDAY_COMPANIES,

  async scrape(ctx) {
    const collected = [];
    ctx.log(`-> ${module.exports.label} (tier 1)`);

    // 1. SmartRecruiters ATS
    for (const company of SMART_RECRUITERS_COMPANIES) {
      if (Date.now() > ctx.deadline) {
        ctx.note(company.domain, 'skipped', 'out of time budget for this run');
        continue;
      }
      const jobs = await scrapeSmartRecruitersCompany(company, ctx);
      collected.push(...jobs);
      ctx.log(`   [SmartRecruiters] ${company.name}: ${jobs.length} job(s)`);
    }

    // 2. Workday CXS Enterprise APIs (from career-ops architecture)
    for (const company of WORKDAY_COMPANIES) {
      if (Date.now() > ctx.deadline) {
        ctx.note(company.domain, 'skipped', 'out of time budget for this run');
        continue;
      }
      const jobs = await scrapeWorkdayCompany(company, ctx);
      collected.push(...jobs);
      ctx.log(`   [Workday CXS] ${company.name}: ${jobs.length} job(s)`);
    }

    ctx.log(`  ${module.exports.label}: ${collected.length} record(s)`);
    return collected;
  },
};

