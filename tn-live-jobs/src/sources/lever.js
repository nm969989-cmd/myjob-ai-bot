'use strict';

/**
 * Tier 1 - Lever.co public job board API.
 */

const { fetchJson, makeJob, markDomainDead } = require('../scraper');
const {
  tidy,
  detectCity,
  detectCategory,
  detectSkills,
  detectEducation,
  detectExperience,
  cleanSummary,
} = require('../util');

const LEVER_COMPANIES = [
  { site: 'gitlab', name: 'GitLab', domain: 'gitlab.com' },
  { site: 'hashicorp', name: 'HashiCorp', domain: 'hashicorp.com' },
  { site: 'razorpay', name: 'Razorpay', domain: 'razorpay.com' },
];

function isTnLocation(loc) {
  if (!loc) return false;
  const text = String(loc).toLowerCase();
  return /chennai|coimbatore|madurai|trichy|tiruchirappalli|salem|tirunelveli|erode|vellore|thanjavur|tiruppur|tamil\s*nadu/i.test(text);
}

async function scrapeCompany(company, ctx) {
  const url = `https://api.lever.co/v0/postings/${company.site}?mode=json`;
  const jobs = [];
  try {
    const { json } = await fetchJson(url, { timeout: 15000 });
    const list = Array.isArray(json) ? json : [];
    for (const job of list) {
      if (!job) continue;
      const locs = job.categories || {};
      const locText = [job.location, locs.location, locs.city, locs.country].filter(Boolean).join(', ');
      if (!isTnLocation(locText)) continue;
      const title = tidy(job.text || job.title);
      const applyUrl = job.hostedUrl || job.applyUrl || `https://jobs.lever.co/${company.site}/${job.id}`;
      const city = detectCity(locText, title) || 'Tamil Nadu';
      const evidence = `${title} ${locText}`;
      const jobRec = makeJob({
        title,
        company: company.name,
        apply_url: applyUrl,
        city,
        state: 'Tamil Nadu',
        category: detectCategory(title),
        employment_type: locs.commitment || 'Full-time',
        experience: detectExperience('', title) || null,
        qualification: detectEducation(title) || null,
        skills: detectSkills(title),
        description: cleanSummary(job.descriptionPlain || job.description || title),
        posted_at: job.createdAt ? new Date(job.createdAt).toISOString().slice(0, 10) : null,
        source: company.domain,
        source_type: 'company',
        extra: evidence,
      });
      if (jobRec) jobs.push(jobRec);
      if (jobs.length >= ctx.limit) break;
    }
    ctx.note(company.domain, jobs.length ? 'ok' : 'no_listings', `${jobs.length} opening(s) in Tamil Nadu`);
  } catch (error) {
    ctx.note(company.domain, 'unreachable', error.message);
    try { markDomainDead(company.domain, error.message); } catch (e) {}
  }
  return jobs;
}

module.exports = {
  id: 'lever',
  label: 'Lever.co ATS',
  tier: 1,
  async scrape(ctx) {
    const results = [];
    for (const comp of LEVER_COMPANIES) {
      results.push(...(await scrapeCompany(comp, ctx)));
    }
    ctx.log(`  ${module.exports.label}: ${results.length} record(s)`);
    return results;
  },
};
