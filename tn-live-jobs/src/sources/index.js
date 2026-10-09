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
const govtTnExtended = require('./govt-tn-extended');
const greenhouse = require('./greenhouse');
const lever = require('./lever');
const timesjobs = require('./timesjobs');
const monsterindia = require('./monsterindia');
const shine = require('./shine');
const cutshort = require('./cutshort');
const wellfound = require('./wellfound');
const hirect = require('./hirect');
const jobhai = require('./jobhai');
const ncs = require('./ncs');
const internshala = require('./internshala');

/** Every source we know about, in priority order. */
const ALL_SOURCES = [govtTn, govtTnExtended, greenhouse, lever, companyCareers, techAts, naukri, apna, indeed, linkedin, timesjobs, monsterindia, shine, cutshort, wellfound, hirect, jobhai, ncs, internshala];

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
  'pudukkottai.nic.in': 1,
  'theni.nic.in': 1,
  'timesjobs.com': 2,
  'monsterindia.com': 2,
  'shine.com': 2,
  'cutshort.io': 2,
  'wellfound.com': 2,
  'hirect.in': 2,
  'jobhai.com': 2,
  'ncs.gov.in': 2,
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
  govtTnExtended,
  timesjobs,
  monsterindia,
  shine,
  cutshort,
  wellfound,
  hirect,
  jobhai,
  ncs,
  greenhouse,
  lever,
  companyCareers,
  techAts,
  naukri,
  apna,
  indeed,
  linkedin,
  internshala,
  'trb.tn.gov.in': 1,
  'tnusrb.tn.gov.in': 1,
  'tangedco.gov.in': 1,
  'twadboard.tn.gov.in': 1,
  'revenue.tn.gov.in': 1,
  'pwd.tn.gov.in': 1,
  'tnpolice.gov.in': 1,
  'tnfrs.tn.gov.in': 1,
  'prisons.tn.gov.in': 1,
  'forests.tn.gov.in': 1,
  'fisheries.tn.gov.in': 1,
  'agri.tn.gov.in': 1,
  'horticulture.tn.gov.in': 1,
  'animalhusbandry.tn.gov.in': 1,
  'aavinmilk.com': 1,
  'cooperation.tn.gov.in': 1,
  'tansidco.tn.gov.in': 1,
  'tniic.tn.gov.in': 1,
  'sipcot.tn.gov.in': 1,
  'tidco.tn.gov.in': 1,
  'chennaimetrorail.org': 1,
  'chennaicorporation.gov.in': 1,
  'ccmc.gov.in': 1,
  'maduraicorporation.gov.in': 1,
  'trichycorporation.gov.in': 1,
  'salemcorporation.gov.in': 1,
  'tirunelvelicorporation.gov.in': 1,
  'tiruppurcorporation.gov.in': 1,
  'erodecorporation.gov.in': 1,
  'thanjavurcorporation.gov.in': 1,
};