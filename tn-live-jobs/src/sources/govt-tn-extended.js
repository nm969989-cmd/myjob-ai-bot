'use strict';

/**
 * Tier 1 - Extended Tamil Nadu government portals and boards.
 */

const cheerio = require('cheerio');
const { fetchText, makeJob, markDomainDead } = require('../scraper');
const { tidy, registrableDomain, detectCity, detectEmploymentType } = require('../util');

const COMPANY = 'Government of Tamil Nadu';

const GOV_INCLUDE = /recruitment|vacanc|advertisement|applications? (?:are )?invited|invited for|engagement of|appointment to the post|fellowship|apprentice|contract (?:post|basis)|direct recruitment|notification/i;
const GOV_EXCLUDE = /answer key|question paper|result|merit list|cut ?off|hall ticket|admit card|instructions to|checklist|syllabus|counselling schedule|verification of certificates|model question/i;

function clipTitle(value) {
  const text = tidy(value);
  if (text.length <= 180) return text;
  const cut = text.slice(0, 180);
  const lastSpace = cut.lastIndexOf(' ');
  return cut.slice(0, lastSpace > 60 ? lastSpace : 179) + '\u2026';
}

function govJobFromLink({ title, href, baseUrl, extraText, sourceType }) {
  const cleanTitle = clipTitle(title);
  if (!cleanTitle || !href) return null;
  let absolute;
  try {
    absolute = new URL(href, baseUrl).toString();
  } catch (error) {
    return null;
  }
  if (!/^https?:\/\//i.test(absolute)) return null;

  const haystack = `${cleanTitle} ${tidy(extraText)}`;
  return makeJob({
    title: cleanTitle,
    company: COMPANY,
    city: detectCity(haystack) || 'Tamil Nadu',
    apply_url: absolute,
    source: registrableDomain(baseUrl),
    source_type: sourceType || 'government',
    category: 'Government',
    extra: haystack,
    employment_type: detectEmploymentType(haystack),
  });
}

function collectGovLinks(html, baseUrl, options) {
  const opts = options || {};
  const minText = opts.minText || 18;
  const jobs = [];
  const seen = new Set();
  const $ = cheerio.load(html);

  const consider = (caption, href, contextText) => {
    if (!caption || !href || href === '#' || href.startsWith('javascript')) return;
    if (caption.length < minText) return;
    if (!GOV_INCLUDE.test(caption) || GOV_EXCLUDE.test(caption)) return;
    const job = govJobFromLink({ title: caption, href, baseUrl, extraText: contextText });
    if (!job || seen.has(job.id)) return;
    seen.add(job.id);
    jobs.push(job);
  };

  $('tr, li').each((index, block) => {
    const $block = $(block);
    const contextText = tidy($block.text());
    $block.find('a[href]').each((i, anchor) => consider(tidy($(anchor).text()), $(anchor).attr('href'), contextText));
  });

  if (jobs.length === 0) {
    $('a[href]').each((index, anchor) => {
      const caption = tidy($(anchor).text());
      consider(caption, $(anchor).attr('href'), caption);
    });
  }

  return jobs;
}

async function probePortal(baseUrl, siteId, notes, minText = 18, timeout = 15000) {
  try {
    const response = await fetchText(baseUrl, { attempts: 1, timeout });
    if (response.status >= 400) throw new Error(`HTTP ${response.status}`);
    const jobs = collectGovLinks(response.body, baseUrl, { minText });
    notes(siteId, jobs.length ? 'ok' : 'no_listings', `${jobs.length} listing(s)`);
    return jobs;
  } catch (error) {
    try { markDomainDead(baseUrl, error.message); } catch (e) {}
    notes(siteId, 'unreachable', error.message);
    return [];
  }
}

const EXTENDED_PORTALS = [
  { url: 'https://www.trb.tn.gov.in/', id: 'trb.tn.gov.in', minText: 20 },
  { url: 'https://tnusrb.tn.gov.in/', id: 'tnusrb.tn.gov.in', minText: 20 },
  { url: 'https://www.tangedco.gov.in/', id: 'tangedco.gov.in', minText: 18 },
  { url: 'https://twadboard.tn.gov.in/', id: 'twadboard.tn.gov.in', minText: 18 },
  { url: 'https://www.revenue.tn.gov.in/', id: 'revenue.tn.gov.in', minText: 18 },
  { url: 'https://www.pwd.tn.gov.in/', id: 'pwd.tn.gov.in', minText: 18 },
  { url: 'https://tnpolice.gov.in/', id: 'tnpolice.gov.in', minText: 18 },
  { url: 'https://www.tnfrs.tn.gov.in/', id: 'tnfrs.tn.gov.in', minText: 18 },
  { url: 'https://prisons.tn.gov.in/', id: 'prisons.tn.gov.in', minText: 18 },
  { url: 'https://www.forests.tn.gov.in/', id: 'forests.tn.gov.in', minText: 18 },
  { url: 'https://www.fisheries.tn.gov.in/', id: 'fisheries.tn.gov.in', minText: 18 },
  { url: 'https://www.agri.tn.gov.in/', id: 'agri.tn.gov.in', minText: 18 },
  { url: 'https://www.horticulture.tn.gov.in/', id: 'horticulture.tn.gov.in', minText: 18 },
  { url: 'https://www.animalhusbandry.tn.gov.in/', id: 'animalhusbandry.tn.gov.in', minText: 18 },
  { url: 'https://aavinmilk.com/', id: 'aavinmilk.com', minText: 18 },
  { url: 'https://cooperation.tn.gov.in/', id: 'cooperation.tn.gov.in', minText: 18 },
  { url: 'https://www.tansidco.tn.gov.in/', id: 'tansidco.tn.gov.in', minText: 18 },
  { url: 'https://tniic.tn.gov.in/', id: 'tniic.tn.gov.in', minText: 18 },
  { url: 'https://www.sipcot.tn.gov.in/', id: 'sipcot.tn.gov.in', minText: 18 },
  { url: 'https://www.tidco.tn.gov.in/', id: 'tidco.tn.gov.in', minText: 18 },
  { url: 'https://chennaimetrorail.org/', id: 'chennaimetrorail.org', minText: 18 },
  { url: 'https://chennaicorporation.gov.in/', id: 'chennaicorporation.gov.in', minText: 18 },
  { url: 'https://www.ccmc.gov.in/', id: 'ccmc.gov.in', minText: 18 },
  { url: 'https://maduraicorporation.gov.in/', id: 'maduraicorporation.gov.in', minText: 18 },
  { url: 'https://trichycorporation.gov.in/', id: 'trichycorporation.gov.in', minText: 18 },
  { url: 'https://salemcorporation.gov.in/', id: 'salemcorporation.gov.in', minText: 18 },
  { url: 'https://tirunelvelicorporation.gov.in/', id: 'tirunelvelicorporation.gov.in', minText: 18 },
  { url: 'https://tiruppurcorporation.gov.in/', id: 'tiruppurcorporation.gov.in', minText: 18 },
  { url: 'https://erodecorporation.gov.in/', id: 'erodecorporation.gov.in', minText: 18 },
  { url: 'https://thanjavurcorporation.gov.in/', id: 'thanjavurcorporation.gov.in', minText: 18 },
];

module.exports = {
  id: 'govt-tn-extended',
  label: 'Tamil Nadu government portals (extended)',
  tier: 1,
  COMPANY,
  collectGovLinks,

  async scrape(ctx) {
    const notes = ctx.note;
    const jobs = [];
    for (const p of EXTENDED_PORTALS) {
      const res = await probePortal(p.url, p.id, notes, p.minText);
      jobs.push(...res);
    }
    ctx.log(`  ${module.exports.label}: ${jobs.length} record(s)`);
    return jobs;
  },
};
