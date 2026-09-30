'use strict';

/**
 * Tier 2 - Naukri.com
 *
 * Naukri serves a normal page to a real browser but only a "loading" skeleton
 * to plain HTTP clients, so we open it with headless Chromium. If Naukri still
 * refuses to give us the job list we mark it blocked and move on. We never
 * retry more than twice and we never hammer the site.
 */

const cheerio = require('cheerio');
const { makeJob, renderCapture, findJobObjects } = require('../scraper');
const {
  tidy,
  clip,
  slugifyValue,
  registrableDomain,
  detectCity,
  detectSalary,
  detectExperience,
  relativeDateToIso,
} = require('../util');

const BASE = 'https://www.naukri.com';

/** Read the server-rendered job cards if Naukri decided to give us any. */
function parseNaukriDom(html) {
  const jobs = [];
  const $ = cheerio.load(html);
  const cards = $('.srp-jobtuple-wrapper, article.jobTuple, div.cust-job-tuple');
  cards.each((index, element) => {
    const card = $(element);
    const anchor = card.find('a.title, a.jobTitle, h2 > a').first();
    const title = tidy(anchor.text()) || tidy(card.find('a.title').first().text());
    const href = tidy(anchor.attr('href'));
    const company = tidy(card.find('.comp-name, a.comp-name, .companyInfo a').first().text());
    const location = tidy(card.find('.locWdth, .location, .loc-wrap').first().text());
    const salary = tidy(card.find('.sal, .salary').first().text());
    const experience = tidy(card.find('.expwdth, .exp').first().text());
    const postedAgo = tidy(card.find('.job-post-day, .freshness').first().text());
    if (!title || !href) return;
    const job = makeJob({
      title,
      company,
      apply_url: href,
      source: registrableDomain(BASE),
      source_type: 'job_portal',
      city: detectCity(location) || undefined,
      location,
      extra: tidy(card.text()),
      salary: salary || detectSalary(tidy(card.text())),
      experience: detectExperience(experience),
      posted_at: relativeDateToIso(postedAgo),
    });
    if (job) jobs.push(job);
  });
  return jobs;
}

module.exports = {
  id: 'naukri',
  label: 'Naukri.com',
  tier: 2,
  parseNaukriDom,

  async scrape(ctx) {
    const notes = ctx.note;
    const jobs = [];
    let attempts = 0;

    for (const keyword of ctx.keywords) {
      for (const city of ctx.cities) {
        if (attempts >= ctx.pageLimit) break;
        if (Date.now() > ctx.deadline) break;
        attempts += 1;

        const url = `${BASE}/${slugifyValue(keyword)}-jobs-in-${slugifyValue(city)}`;
        try {
          let payload;
          try {
            payload = await renderCapture(await ctx.getContext(), url, {
              urlIncludes: ['jobapi', '/api/', 'job-listings', 'search'],
              settleMs: 6000,
              waitForSelector: '.srp-jobtuple-wrapper, article.jobTuple',
            });
          } catch (browserError) {
            // A missing/corrupt browser download must not sink the whole run.
            ctx.log(`  naukri skipped: browser unavailable (${browserError.message.split('\n')[0]})`);
            notes('naukri.com', 'blocked', 'headless browser unavailable in this environment');
            return jobs;
          }
          const { json, dom } = payload;

          for (const candidate of parseNaukriDom(dom.html)) jobs.push(candidate);
          for (const response of json) {
            for (const candidate of findJobObjects(response.json)) {
              const job = makeJob({
                title: candidate.title,
                company: candidate.company,
                apply_url: candidate.url,
                source: registrableDomain(BASE),
                source_type: 'job_portal',
                city: detectCity(candidate.location) || undefined,
                location: candidate.location,
                extra: `${candidate.title} ${candidate.location}`,
              });
              if (job) jobs.push(job);
            }
          }
        } catch (error) {
          ctx.log(`  naukri page failed (${clip(url, 80)}): ${clip(error.message, 120)}`);
        }

        if (jobs.length >= ctx.limit) break;
      }
      if (jobs.length >= ctx.limit) break;
    }

    if (jobs.length) notes('naukri.com', 'ok', `${jobs.length} job(s) from ${attempts} search page(s)`);
    else notes('naukri.com', 'blocked', 'Naukri returned no job cards to a headless browser either');
    return jobs;
  },
};
