'use strict';

/**
 * Loads every source module and decides which ones run this time.
 *
 * Sources are grouped in tiers exactly as the project brief asks:
 *   Tier 1 - official / legal, always tried.
 *   Tier 2 - marketplaces, tried but never hammered; blocked ones are dropped.
 *   Tier 3 - optional extras, only when ENABLE_TIER3=true.
 */

const { ENABLE_TIER3 } = require('../config');

const govtTn = require('./govt-tn');
const companyCareers = require('./company-careers');
const techAts = require('./tech-ats');
const naukri = require('./naukri');
const apna = require('./apna');
const indeed = require('./indeed');
const linkedin = require('./linkedin');
const internshala = require('./internshala');

/** Every source we know about, in priority order. */
const ALL_SOURCES = [govtTn, companyCareers, techAts, naukri, apna, indeed, linkedin, internshala];

/** The sources that will actually run in this process. */
function loadSources() {
  return ALL_SOURCES.filter((source) => source.tier !== 3 || ENABLE_TIER3);
}

/**
 * Which tier each individual website belongs to. Used for the run report, so
 * the table can show why a site was or was not tried.
 */
const SITE_TIERS = {
  'tn.gov.in': 1,
  'tnpsc.gov.in': 1,
  'tnvelaivaaippu.gov.in': 1,
  'employment.tn.gov.in': 1,
  'protnnetc.tn.gov.in': 1,
  'mrb.tn.gov.in': 1,
  'madurai.nic.in': 1,
  'salem.nic.in': 1,
  'tirunelveli.nic.in': 1,
  'coimbatore.nic.in': 1,
  'freshersworld.com': 1,
  'zohocorp.com': 1,
  'freshworks.com': 1,
  'bosch.in': 1,
  'averydennison.com': 1,
  'tcs.com': 1,
  'infosys.com': 1,
  'wipro.com': 1,
  'hcltech.com': 1,
  'cognizant.com': 1,
  'naukri.com': 2,
  'apna.co': 2,
  'indeed.co.in': 2,
  'linkedin.com': 2,
  'internshala.com': 3,
};

function tierForSite(id) {
  return SITE_TIERS[id] || 1;
}

module.exports = {
  ALL_SOURCES,
  loadSources,
  SITE_TIERS,
  tierForSite,
  govtTn,
  companyCareers,
  techAts,
  naukri,
  apna,
  indeed,
  linkedin,
  internshala,
};
