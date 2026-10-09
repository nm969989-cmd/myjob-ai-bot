'use strict';

/**
 * Tier 1 - Greenhouse.io public job board API.
 * Fetches jobs from companies using greenhouse.io with TN filtering.
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

const GREENHOUSE_COMPANIES = [
  { boardToken: 'gitlab', name: 'GitLab', domain: 'gitlab.com' },
  { boardToken: 'hashicorp', name: 'HashiCorp', domain: 'hashicorp.com' },
  { boardToken: 'databricks', name: 'Databricks', domain: 'databricks.com' },
  { boardToken: 'mongodb', name: 'MongoDB', domain: 'mongodb.com' },
  { boardToken: 'confluent', name: 'Confluent', domain: 'confluent.io' },
  { boardToken: 'cockroachlabs', name: 'Cockroach Labs', domain: 'cockroachlabs.com' },
  { boardToken: 'neon', name: 'Neon', domain: 'neon.tech' },
  { boardToken: 'upstash', name: 'Upstash', domain: 'upstash.com' },
  { boardToken: 'railway', name: 'Railway', domain: 'railway.app' },
  { boardToken: 'render', name: 'Render', domain: 'render.com' },
  { boardToken: 'planetscale', name: 'PlanetScale', domain: 'planetscale.com' },
  { boardToken: 'timescale', name: 'Timescale', domain: 'timescale.com' },
  { boardToken: 'yugabyte', name: 'Yugabyte', domain: 'yugabyte.com' },
  { boardToken: 'flyio', name: 'Fly.io', domain: 'fly.io' },
];

function isTnLocation(loc) {
  if (!loc) return false;
  const text = String(loc).toLowerCase();
  return /chennai|coimbatore|madurai|trichy|tiruchirappalli|salem|tirunelveli|erode|vellore|thanjavur|tiruppur|tamil\s*nadu/i.test(text);
}

async function scrapeCompany(company, ctx) {
  const url = `https://boards-api.greenhouse.io/v1/boards/${company.boardToken}/jobs?content=true`;
  const jobs = [];
  try {
    const { json } = await fetchJson(url, { timeout: 15000 });
    const list = Array.isArray(json.jobs) ? json.jobs : [];
    for (const job of list) {
      if (!job) continue;
      const loc = job.location || job.location_name || (job.locations || []).map((x) => x.name).join(', ');
      if (!isTnLocation(loc)) continue;
      const title = tidy(job.title);
      const applyUrl = job.absolute_url || job.url || `https://boards.greenhouse.io/${company.boardToken}/jobs/${job.id}`;
      const city = detectCity(loc, title) || 'Tamil Nadu';
      const evidence = `${title} ${loc}`;
      const skills = detectSkills(title);
      const qualification = detectEducation(title) || null;
      const experience = detectExperience('', title) || null;
      const jobRec = makeJob({
        title,
        company: company.name,
        apply_url: applyUrl,
        city,
        state: 'Tamil Nadu',
        category: detectCategory(title),
        employment_type: job.employment_type || 'Full-time',
        experience,
        qualification,
        skills,
        description: cleanSummary(job.content || title),
        posted_at: job.updated_at ? job.updated_at.slice(0, 10) : (job.created_at ? job.created_at.slice(0, 10) : null),
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
  id: 'greenhouse',
  label: 'Greenhouse.io ATS',
  tier: 1,
  async scrape(ctx) {
    const results = [];
    for (const comp of GREENHOUSE_COMPANIES) {
      results.push(...(await scrapeCompany(comp, ctx)));
    }
    ctx.log(`  ${module.exports.label}: ${results.length} record(s)`);
    return results;
  },
};
