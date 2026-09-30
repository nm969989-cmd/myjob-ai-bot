'use strict';

/**
 * Tier 3 - Internshala (optional).
 *
 * This source only runs when you ask for it (ENABLE_TIER3=true) and when the
 * Tier 1 / Tier 2 sources are working normally. Internshala's job pages are
 * plain server-rendered HTML, so no browser is needed.
 */

const cheerio = require('cheerio');
const { fetchText, makeJob } = require('../scraper');
const {
  tidy,
  slugifyValue,
  registrableDomain,
  detectCity,
  detectSalary,
  relativeDateToIso,
} = require('../util');

const BASE = 'https://internshala.com';

/** Read the job cards from an Internshala city listing page. */
function parseInternshala(html) {
  const jobs = [];
  const $ = cheerio.load(html);
  $('.individual_internship').each((index, element) => {
    const card = $(element);
    const anchor = card.find('.job-internship-name a, #job_title').first();
    const title = tidy(anchor.text());
    const href = tidy(anchor.attr('href'));
    const company = tidy(card.find('.company-name').first().text());
    const location = tidy(card.find('.locations, #location_names, .location_link').first().text());
    const cardText = tidy(card.text());
    const kind = tidy(card.attr('employment_type')).toLowerCase();

    if (!title || !href) return;
    if (!/^https?:\/\//i.test(href) && !href.startsWith('/')) return;

    const agoMatch = /(\d+\s*(?:minute|hour|day|week|month)s?\s*ago)/i.exec(cardText);

    jobs.push({
      title,
      company,
      applyUrl: href.startsWith('http') ? href : `${BASE}${href}`,
      location,
      cardText,
      employmentType: kind === 'internship' ? 'Internship' : kind === 'job' ? 'Full-time' : null,
      postedAt: relativeDateToIso(agoMatch ? agoMatch[1] : ''),
    });
  });
  return jobs;
}

module.exports = {
  id: 'internshala',
  label: 'Internshala (optional Tier 3)',
  tier: 3,
  parseInternshala,

  async scrape(ctx) {
    const notes = ctx.note;
    const jobs = [];
    let attempts = 0;

    for (const keyword of ctx.keywords) {
      for (const city of ctx.cities) {
        // Internshala has city pages but no "whole state" page.
        if (city === 'Tamil Nadu') continue;
        if (attempts >= Math.min(ctx.pageLimit, 20)) break;
        if (Date.now() > ctx.deadline) break;
        attempts += 1;

        const url = `${BASE}/jobs/${slugifyValue(keyword)}-jobs-in-${slugifyValue(city)}/`;
        try {
          const response = await fetchText(url);
          if (response.status >= 400) continue;
          for (const card of parseInternshala(response.body)) {
            const job = makeJob({
              title: card.title,
              company: card.company,
              apply_url: card.applyUrl,
              source: registrableDomain(BASE),
              source_type: 'job_portal',
              city: detectCity(card.location, card.title) || undefined,
              location: card.location,
              extra: card.cardText,
              salary: detectSalary(card.cardText),
              employment_type: card.employmentType || undefined,
              posted_at: card.postedAt,
            });
            if (job) jobs.push(job);
          }
        } catch (error) {
          ctx.log(`  internshala page failed (${slugifyValue(keyword)}/${slugifyValue(city)})`);
        }
        if (jobs.length >= ctx.limit) break;
      }
      if (jobs.length >= ctx.limit) break;
    }

    notes('internshala.com', jobs.length ? 'ok' : 'no_listings', `${jobs.length} job(s) from ${attempts} page(s)`);
    return jobs;
  },
};
