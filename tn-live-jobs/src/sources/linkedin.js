'use strict';

/**
 * Tier 2 - LinkedIn public job listings.
 *
 * LinkedIn publishes a guest search endpoint that returns real job cards to
 * a plain HTTP request (no login needed). We read the cards, never the logged
 * in site. If LinkedIn decides to rate-limit us we stop immediately, mark the
 * source blocked, and carry on with the other sources.
 */

const cheerio = require('cheerio');
const { fetchText, makeJob } = require('../scraper');
const { tidy, clip, registrableDomain, detectCity, detectEmploymentType, relativeDateToIso, toIsoDate } = require('../util');

const BASE = 'https://www.linkedin.com';
const SEARCH = `${BASE}/jobs-guest/jobs/api/seeMoreJobPostings/search`;

/** Read the guest-search HTML fragment. */
function parseLinkedInCards(html, fallbackLocation) {
  const jobs = [];
  const $ = cheerio.load(html);
  $('.base-search-card, li').each((index, element) => {
    const card = $(element);
    const link = card.find('a.base-card__full-link').first();
    const href = tidy(link.attr('href') || card.find('a[href*="/jobs/view/"]').first().attr('href'));
    const title = tidy(card.find('.base-search-card__title').first().text());
    const company = tidy(card.find('.base-search-card__subtitle').first().text());
    const location = tidy(card.find('.job-search-card__location').first().text()) || tidy(fallbackLocation);
    const timeTag = card.find('time').first();
    const postedRaw = tidy(timeTag.attr('datetime')) || tidy(timeTag.text());
    if (!href || !title) return;
    jobs.push({
      title,
      company,
      applyUrl: href.split('?')[0],
      location,
      postedAt: toIsoDate(postedRaw) || relativeDateToIso(postedRaw),
    });
  });
  return jobs;
}

module.exports = {
  id: 'linkedin',
  label: 'LinkedIn Jobs (public guest listings)',
  tier: 2,
  parseLinkedInCards,

  async scrape(ctx) {
    const notes = ctx.note;
    const jobs = [];
    let attempts = 0;
    let blocked = 0;

    for (const keyword of ctx.keywords) {
      for (const city of ctx.cities) {
        if (attempts >= ctx.pageLimit) break;
        if (Date.now() > ctx.deadline) break;
        attempts += 1;

        const location = city === 'Tamil Nadu' ? 'Tamil Nadu, India' : `${city}, Tamil Nadu, India`;
        const url = `${SEARCH}?keywords=${encodeURIComponent(keyword)}&location=${encodeURIComponent(location)}&start=0`;

        try {
          const response = await fetchText(url, {
            headers: { referer: `${BASE}/jobs/search`, accept: 'text/html, */*' },
          });
          if (response.status === 429 || response.status === 403) {
            blocked += 1;
            ctx.log('  linkedin started rate-limiting us, stopping this source');
            if (blocked >= 3) break;
            continue;
          }
          if (response.status >= 400) continue;

          for (const card of parseLinkedInCards(response.body, location)) {
            const job = makeJob({
              title: card.title,
              company: card.company,
              apply_url: card.applyUrl,
              source: registrableDomain(BASE),
              source_type: 'job_portal',
              city: detectCity(card.location, card.title) || undefined,
              location: card.location,
              extra: `${card.title} ${card.location}`,
              employment_type: detectEmploymentType(card.location),
              posted_at: card.postedAt,
            });
            if (job) jobs.push(job);
          }
        } catch (error) {
          ctx.log(`  linkedin request failed (${clip(location, 40)}): ${clip(error.message, 100)}`);
        }

        if (jobs.length >= ctx.limit) break;
      }
      if (jobs.length >= ctx.limit) break;
      if (blocked >= 3) break;
    }

    if (jobs.length) notes('linkedin.com', 'ok', `${jobs.length} job(s) from ${attempts} search request(s)`);
    else if (blocked) notes('linkedin.com', 'blocked', `rate-limited / refused on ${blocked} request(s)`);
    else notes('linkedin.com', 'no_listings', 'no job cards came back');
    return jobs;
  },
};
