'use strict';

const cheerio = require('cheerio');
const { fetchText, makeJob } = require('../scraper');
const { tidy, registrableDomain, detectCity, detectCategory, detectSkills, detectEducation, detectExperience, cleanSummary } = require('../util');

const BASE = 'https://www.shine.com';

function parseShine(html) {
  const $ = cheerio.load(html);
  const jobs = [];
  $('.jobCard, .result-display__profile, li.joblisting').each((i, el) => {
    const $el = $(el);
    const anchor = $el.find('a[href*="/job-detail/"]').first();
    const title = tidy(anchor.text());
    let href = anchor.attr('href');
    const company = tidy($el.find('.jobCard_jobDetail__companyName__kzii0, .company').first().text());
    const location = tidy($el.find('.jobCard_jobDetail__location__M9k6b, .location').first().text());
    const text = tidy($el.text());
    if (!title || !href) return;
    if (!href.startsWith('http')) href = `${BASE}${href}`;
    jobs.push({ title, company, applyUrl: href, location, text });
  });
  return jobs;
}

module.exports = {
  id: 'shine',
  label: 'Shine.com',
  tier: 2,
  async scrape(ctx) {
    const jobs = [];
    const keywords = ['software', 'fresher', 'developer'];
    for (const kw of keywords) {
      for (const city of ctx.cities.slice(0, 8)) {
        if (Date.now() > ctx.deadline) break;
        const url = `https://www.shine.com/job-search/${encodeURIComponent(kw)}-jobs-in-${encodeURIComponent(city + '-Tamil-Nadu')}`;
        try {
          const res = await fetchText(url, { timeout: 20000 });
          if (res.status >= 400) continue;
          for (const e of parseShine(res.body)) {
            const cityDetected = detectCity(e.location, e.text) || city;
            const job = makeJob({
              title: e.title,
              company: e.company,
              apply_url: e.applyUrl,
              city: cityDetected,
              state: 'Tamil Nadu',
              category: detectCategory(e.title, e.text),
              employment_type: 'Full-time',
              experience: detectExperience(e.text, e.title) || null,
              qualification: detectEducation(e.title) || null,
              skills: detectSkills(e.title, e.text),
              description: cleanSummary(e.text),
              source: registrableDomain(BASE),
              source_type: 'job_portal',
              extra: `${e.title} ${e.location} ${e.text}`,
            });
            if (job) jobs.push(job);
          }
        } catch (err) {
          ctx.note('shine.com', 'unreachable', err.message);
        }
      }
    }
    ctx.log(`  ${module.exports.label}: ${jobs.length} record(s)`);
    return jobs;
  },
};
