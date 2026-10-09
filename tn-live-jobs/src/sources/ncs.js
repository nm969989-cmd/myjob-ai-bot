'use strict';

const cheerio = require('cheerio');
const { fetchText, makeJob } = require('../scraper');
const { tidy, registrableDomain, detectCity, detectCategory, detectSkills, detectEducation, detectExperience, cleanSummary } = require('../util');

const BASE = 'https://www.ncs.gov.in';

function parseNcs(html) {
  const $ = cheerio.load(html);
  const jobs = [];
  $('table tr, .job-list li').each((i, el) => {
    const $el = $(el);
    const anchor = $el.find('a[href]').first();
    const title = tidy(anchor.text());
    let href = anchor.attr('href');
    const text = tidy($el.text());
    if (!title || !href || title.length < 12) return;
    if (!href.startsWith('http')) href = new URL(href, BASE).toString();
    jobs.push({ title, applyUrl: href, text });
  });
  return jobs;
}

module.exports = {
  id: 'ncs',
  label: 'National Career Service (NCS)',
  tier: 2,
  async scrape(ctx) {
    const jobs = [];
    try {
      const res = await fetchText(`${BASE}/Pages/JobSeeker/JobVacancySearch.aspx`, { timeout: 20000 });
      if (res.status < 400) {
        for (const e of parseNcs(res.body)) {
          const cityDetected = detectCity(e.text, e.title) || 'Tamil Nadu';
          const job = makeJob({
            title: e.title,
            company: 'National Career Service',
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
            source_type: 'government',
            extra: `${e.title} ${e.text}`,
          });
          if (job) jobs.push(job);
        }
      }
    } catch (err) {
      ctx.note('ncs.gov.in', 'unreachable', err.message);
    }
    ctx.log(`  ${module.exports.label}: ${jobs.length} record(s)`);
    return jobs;
  },
};
