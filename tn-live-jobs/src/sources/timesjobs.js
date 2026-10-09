'use strict';

/**
 * Tier 2 - TimesJobs
 */

const cheerio = require('cheerio');
const { fetchText, makeJob } = require('../scraper');
const { tidy, registrableDomain, detectCity, detectCategory, detectSkills, detectEducation, detectExperience, cleanSummary } = require('../util');

const BASE = 'https://www.timesjobs.com';

function parseTimesJobs(html) {
  const $ = cheerio.load(html);
  const jobs = [];
  $('article.job-post, .job-card, .srp_joblist li, .job-listing').each((i, el) => {
    const $el = $(el);
    const anchor = $el.find('a[href*="/jobs/"], a[href*="timesjobs"]').first();
    const title = tidy(anchor.text());
    let href = anchor.attr('href');
    const company = tidy($el.find('.company-name, .comp-name, .joblist-compname').first().text());
    const location = tidy($el.find('.location, .joblist-location').first().text());
    const text = tidy($el.text());
    if (!title || !href) return;
    if (!href.startsWith('http')) href = `${BASE}${href}`;
    jobs.push({ title, company, applyUrl: href, location, text });
  });
  return jobs;
}

module.exports = {
  id: 'timesjobs',
  label: 'TimesJobs',
  tier: 2,
  parseTimesJobs,
  async scrape(ctx) {
    const jobs = [];
    const keywords = ['software', 'fresher', 'developer', 'graduate'];
    for (const kw of keywords) {
      for (const city of ctx.cities.slice(0, 10)) {
        if (Date.now() > ctx.deadline) break;
        const url = `https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit&txtKeywords=${encodeURIComponent(kw)}&txtLocation=${encodeURIComponent(city + ', Tamil Nadu')}`;
        try {
          const res = await fetchText(url, { timeout: 20000 });
          if (res.status >= 400) continue;
          for (const e of parseTimesJobs(res.body)) {
            const cityDetected = detectCity(e.location, e.text, e.title) || city;
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
          ctx.note('timesjobs.com', 'unreachable', err.message);
        }
      }
    }
    ctx.log(`  ${module.exports.label}: ${jobs.length} record(s)`);
    return jobs;
  },
};
