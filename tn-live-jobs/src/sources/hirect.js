'use strict';

const cheerio = require('cheerio');
const { fetchText, makeJob } = require('../scraper');
const { tidy, registrableDomain, detectCity, detectCategory, detectSkills, detectEducation, detectExperience, cleanSummary } = require('../util');

const BASE = 'https://www.hirect.in';

function parseHirect(html) {
  const $ = cheerio.load(html);
  const jobs = [];
  $('div.job-card, a[href*="/job/"]').each((i, el) => {
    const $el = $(el).closest('div') || $(el);
    const anchor = $(el).is('a') ? $(el) : $el.find('a[href*="/job/"]').first();
    const title = tidy(anchor.text());
    let href = anchor.attr('href');
    const company = tidy($el.find('.company-name, .comp').first().text());
    const location = tidy($el.find('.location').first().text());
    const text = tidy($el.text());
    if (!title || !href) return;
    if (!href.startsWith('http')) href = `${BASE}${href}`;
    jobs.push({ title, company, applyUrl: href, location, text });
  });
  return jobs;
}

module.exports = {
  id: 'hirect',
  label: 'Hirect.in',
  tier: 2,
  async scrape(ctx) {
    const jobs = [];
    const keywords = ['software', 'fresher'];
    for (const kw of keywords) {
      for (const city of ctx.cities.slice(0, 6)) {
        if (Date.now() > ctx.deadline) break;
        const url = `https://www.hirect.in/search?q=${encodeURIComponent(kw)}&loc=${encodeURIComponent(city + ', Tamil Nadu')}`;
        try {
          const res = await fetchText(url, { timeout: 20000 });
          if (res.status >= 400) continue;
          for (const e of parseHirect(res.body)) {
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
          ctx.note('hirect.in', 'unreachable', err.message);
        }
      }
    }
    ctx.log(`  ${module.exports.label}: ${jobs.length} record(s)`);
    return jobs;
  },
};
