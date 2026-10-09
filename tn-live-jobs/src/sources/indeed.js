'use strict';

/**
 * Tier 2 - indeed.co.in
 *
 * Indeed answers every automated request with HTTP 403 (Cloudflare bot check).
 * We try exactly once per search, record the block, and stop. We do not retry
 * and we do not try to defeat the bot protection - that would not be polite
 * and it would not be stable in CI either.
 */

const cheerio = require('cheerio');
const { fetchText, makeJob } = require('../scraper');
const { tidy, clip, registrableDomain, detectCity, relativeDateToIso } = require('../util');

const { cityLocation, planSearches } = require('../config');
const BASE = 'https://in.indeed.com';
const MAX_TRIES = 4;

/** Best-effort reader for Indeed's server-rendered cards. */
function parseIndeed(html, fallbackLocation) {
  const jobs = [];
  const $ = cheerio.load(html);
  $('a.jcs-JobTitle, a[id^="job_"], h2.jobTitle > a').each((index, element) => {
    const anchor = $(element);
    const href = tidy(anchor.attr('href'));
    const title = tidy(anchor.text());
    if (!href || !title) return;
    const card = anchor.closest('div.job_seen_beacon, li, div.slider_container');
    const company = tidy(card.find('[data-testid="company-name"], .companyName').first().text());
    const location = tidy(card.find('[data-testid="text-location"], .companyLocation').first().text()) || fallbackLocation;
    const posted = tidy(card.find('[data-testid="myJobsStateDate"], .date').first().text());
    const absolute = href.startsWith('http') ? href : `${BASE}${href}`;
    jobs.push({ title, company, location, applyUrl: absolute.split('?')[0], postedAt: relativeDateToIso(posted) });
  });
  return jobs;
}

module.exports = {
  id: 'indeed',
  label: 'Indeed India',
  tier: 2,
  parseIndeed,

  async scrape(ctx) {
    const notes = ctx.note;
    const jobs = [];
    let blocked = 0;
    let attempts = 0;

    const plan = planSearches(ctx.keywords, ctx.cities, Math.min(ctx.pageLimit, MAX_TRIES));

    for (const { keyword, city } of plan) {
      if (Date.now() > ctx.deadline) break;
      attempts += 1;

      const location = cityLocation(city);
      const url = `${BASE}/jobs?q=${encodeURIComponent(keyword)}&l=${encodeURIComponent(location)}`;
      try {
        const response = await fetchText(url, { attempts: 1, headers: { referer: `${BASE}/` } });
        if (
          response.status === 403 ||
          response.status === 429 ||
          /captcha|cf-chl|just a moment/i.test(response.body)
        ) {
          blocked += 1;
          continue;
        }
        if (response.status >= 400) continue;

        for (const card of parseIndeed(response.body, location)) {
          const job = makeJob({
            title: card.title,
            company: card.company,
            apply_url: card.applyUrl,
            source: registrableDomain(BASE),
            source_type: 'job_portal',
            city: detectCity(card.location, card.title) || undefined,
            location: card.location,
            extra: `${card.title} ${card.location}`,
            posted_at: card.postedAt,
          });
          if (job) jobs.push(job);
        }
      } catch (error) {
        blocked += 1;
        ctx.log(`  indeed request failed: ${clip(error.message, 100)}`);
      }
      if (jobs.length >= ctx.limit) break;
    }

    if (jobs.length) notes('indeed.co.in', 'ok', `${jobs.length} job(s) from ${attempts} search page(s)`);
    else {
      notes(
        'indeed.co.in',
        'blocked',
        `bot protection answered HTTP 403 on ${blocked || attempts} request(s); source disabled`
      );
    }
    return jobs;
  },
};
