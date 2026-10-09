'use strict';

/**
 * Tier 2 - apna.co
 *
 * apna.co is a Next.js site. Its job list is not in the HTML tags, but the
 * page *does* ship the same data as a JSON "flight" payload inside a script
 * tag. We read that payload, so we are still only reading what the page
 * really contains. If the payload is not there we mark the source as
 * having no listings and move on.
 */

const { fetchText, makeJob } = require('../scraper');
const {
  tidy,
  clip,
  slugifyValue,
  registrableDomain,
  detectCity,
  detectEmploymentType,
  detectExperience,
  unescapeJsonInScript,
} = require('../util');
const { planSearches } = require('../config');

const BASE = 'https://apna.co';

/**
 * Category pages apna publishes on its own site. Using their slugs (instead of
 * inventing search URLs) keeps us on real, live pages. A 404 simply means apna
 * has no page for that slug, and we skip it silently.
 */
const APNA_CATEGORIES = [
  'accounts_finance',
  'back_office',
  'field_sales',
  'teacher_faculty_tutor',
  'business_development',
  'marketing',
  'admin_office_assistant',
  'technician',
  'human_resource',
  'machine_operator',
  'civil_engineer_architect',
  'receptionist_front_office_help_desk',
  'manufacturing_production',
  'healthcare',
  'nurse',
];

/**
 * Read the flight payload. Each job starts at `"jobID":` and we only ever
 * take the fields that sit next to it.
 */
function parseApnaPayload(html) {
  const flat = unescapeJsonInScript(html);
  const chunks = flat.split('"jobID":');
  chunks.shift(); // everything before the first job
  const out = [];

  for (const chunk of chunks.slice(0, 60)) {
    const window = chunk.slice(0, 6000);
    const grab = (pattern) => {
      const match = pattern.exec(window);
      return match ? tidy(match[1]) : '';
    };

    const jobId = grab(/^(\d+)/);
    const title = grab(/"jobTitle":"([^"]*)"/);
    const company = grab(/"organisationName":"([^"]*)"/);
    const path = grab(/"jobPublicURL":"([^"]*)"/);
    const address = grab(/"jobCardAddress":"([^"]*)"/);
    const salaryMin = grab(/"salaryMin":(\d+)/);
    const salaryMax = grab(/"salaryMax":(\d+)/);
    const tags = Array.from(window.matchAll(/"tagLabel":"([^"]*)"/g))
      .map((match) => tidy(match[1]))
      .slice(0, 10);

    if (!title || !path || !jobId) continue;

    const salary =
      salaryMin && salaryMax ? `INR ${salaryMin} - ${salaryMax} per month` : null;
    const tagText = tags.join(', ');

    out.push({
      title,
      company,
      applyUrl: path.startsWith('http') ? path : `${BASE}${path}`,
      address,
      tagText,
      salary,
    });
  }
  return out;
}

module.exports = {
  id: 'apna',
  label: 'apna.co',
  tier: 2,
  APNA_CATEGORIES,
  parseApnaPayload,

  async scrape(ctx) {
    const notes = ctx.note;
    const jobs = [];
    let attempts = 0;
    let blocked = 0;

    // apna publishes real category pages; the planner orders the cities.
    const plan = planSearches(APNA_CATEGORIES, ctx.cities, ctx.pageLimit);

    for (const { keyword: category, city } of plan) {
      if (Date.now() > ctx.deadline) break;
      attempts += 1;

      const url = `${BASE}/jobs/${category}-jobs-in-${slugifyValue(city)}`;
      try {
        const response = await fetchText(url, { headers: { referer: `${BASE}/` } });
        if (response.status === 403 || response.status === 429) {
          blocked += 1;
          continue;
        }
        if (response.status >= 400) continue;

        for (const entry of parseApnaPayload(response.body)) {
          const job = makeJob({
            title: entry.title,
            company: entry.company,
            apply_url: entry.applyUrl,
            source: registrableDomain(BASE),
            source_type: 'job_portal',
            city: detectCity(entry.address, entry.title) || undefined,
            location: entry.address,
            extra: `${entry.title} ${entry.address} ${entry.tagText}`,
            salary: entry.salary || undefined,
            employment_type: detectEmploymentType(entry.tagText),
            experience: detectExperience(entry.tagText),
          });
          if (job) jobs.push(job);
        }
      } catch (error) {
        ctx.log(`  apna page failed (${clip(url, 70)}): ${clip(error.message, 100)}`);
      }

      if (jobs.length >= ctx.limit) break;
    }

    if (jobs.length) notes('apna.co', 'ok', `${jobs.length} job(s) from ${attempts} category page(s)`);
    else if (blocked) notes('apna.co', 'blocked', `site answered HTTP 403/429 on ${blocked} request(s)`);
    else notes('apna.co', 'no_listings', `no job payload found in ${attempts} page(s)`);
    return jobs;
  },
};
