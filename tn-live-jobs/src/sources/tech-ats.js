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
} = require('../util');

const SMART_RECRUITERS_COMPANIES = [
  { id: 'Freshworks', name: 'Freshworks', domain: 'freshworks.com' },
  { id: 'BoschGroup', name: 'Robert Bosch India', domain: 'bosch.in' },
  { id: 'AveryDennison', name: 'Avery Dennison', domain: 'averydennison.com' },
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

module.exports = {
  id: 'tech-ats',
  label: 'Direct Enterprise ATS APIs (Freshworks, Bosch, Avery Dennison)',
  tier: 1,
  SMART_RECRUITERS_COMPANIES,

  async scrape(ctx) {
    const collected = [];
    ctx.log(`-> ${module.exports.label} (tier 1)`);

    for (const company of SMART_RECRUITERS_COMPANIES) {
      if (Date.now() > ctx.deadline) {
        ctx.note(company.domain, 'skipped', 'out of time budget for this run');
        continue;
      }
      const jobs = await scrapeSmartRecruitersCompany(company, ctx);
      collected.push(...jobs);
      ctx.log(`   ${company.name}: ${jobs.length} job(s)`);
    }

    ctx.log(`  ${module.exports.label}: ${collected.length} record(s)`);
    return collected;
  },
};
