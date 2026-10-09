'use strict';

/**
 * All the tunable settings for the whole project live in this one file.
 * If you want to search different cities or add job categories, edit here.
 */

// Search the four preferred cities before broader Tamil Nadu coverage.
const PRIORITY_CITIES = ['Tiruvannamalai', 'Vellore', 'Puducherry', 'Chennai'];
const CITIES = [
  ...PRIORITY_CITIES,
  'Coimbatore',
  'Madurai',
  'Trichy',
  'Salem',
  'Tirunelveli',
  'Erode',
  'Thanjavur',
  'Tiruppur',
  'Kanchipuram',
  'Villupuram',
  'Cuddalore',
  'Dindigul',
  'Karur',
  'Namakkal',
  'Perambalur',
  'Ariyalur',
  'Nagapattinam',
  'Thiruvarur',
  'Mayiladuthurai',
  'Tenkasi',
  'Chengalpattu',
  'Kallakurichi',
  'Ranipet',
  'Tirupattur',
  'Tiruvallur',
  'Ramanathapuram',
  'Sivaganga',
  'Virudhunagar',
  'Thoothukudi',
  'Kanyakumari',
  'Nilgiris',
  'Dharmapuri',
  'Krishnagiri',
  'Pudukkottai',
  'Theni',
  'Tamil Nadu',
];

// When we read a page, how do we know which city it is talking about?
// Each city maps to the different spellings that appear on real web pages.
const CITY_ALIASES = {
  Tiruvannamalai: ['tiruvannamalai', 'thiruvannamalai', 'thiruannamalai', 'tiruvanamalai'],
  Vellore: ['vellore'],
  Puducherry: ['puducherry', 'pondicherry', 'pondi'],
  Chennai: ['chennai', 'madras', 'chengalpattu', 'sriperumbudur', 'guindy', 'ambattur', 'omr'],
  Coimbatore: ['coimbatore', 'kovai'],
  Madurai: ['madurai'],
  Trichy: ['trichy', 'tiruchirappalli', 'tiruchirapalli', 'thiruchirappalli'],
  Salem: ['salem'],
  Tirunelveli: ['tirunelveli', 'thirunelveli', 'nellai'],
  Erode: ['erode'],
  Thanjavur: ['thanjavur', 'tanjore'],
  Tiruppur: ['tiruppur', 'tirupur'],
  Kanchipuram: ['kanchipuram', 'kancheepuram', 'kanjeevaram'],
  Villupuram: ['villupuram', 'vizhuppuram'],
  Cuddalore: ['cuddalore', 'kadalur'],
  Dindigul: ['dindigul'],
  Karur: ['karur'],
  Namakkal: ['namakkal'],
  Perambalur: ['perambalur'],
  Ariyalur: ['ariyalur'],
  Nagapattinam: ['nagapattinam', 'nagapatnam'],
  Thiruvarur: ['thiruvarur', 'thiruvvarur', 'thiruvaroor'],
  Mayiladuthurai: ['mayiladuthurai', 'mayiladthurai', 'mayavaram'],
  Tenkasi: ['tenkasi'],
  Chengalpattu: ['chengalpattu', 'chengalpet'],
  Kallakurichi: ['kallakurichi', 'kallakkurichi'],
  Ranipet: ['ranipet', 'ranipettai'],
  Tirupattur: ['tirupattur', 'tirupathur'],
  Tiruvallur: ['tiruvallur', 'thiruvallur'],
  Ramanathapuram: ['ramanathapuram', 'ramnad'],
  Sivaganga: ['sivaganga', 'sivagangai'],
  Virudhunagar: ['virudhunagar'],
  Thoothukudi: ['thoothukudi', 'tuticorin'],
  Kanyakumari: ['kanyakumari', 'nagercoil', 'cape comorin'],
  Nilgiris: ['nilgiris', 'the nilgiris', 'ooty', 'udagamandalam'],
  Dharmapuri: ['dharmapuri'],
  Krishnagiri: ['krishnagiri'],
  Pudukkottai: ['pudukkottai', 'pudukottai'],
  Theni: ['theni', 'thenkasi', 'periyakulam', 'bodinayakanur'],
  'Tamil Nadu': ['tamil nadu', 'tamilnadu', 'across tamil nadu'],
};

function canonicalCity(value) {
  const text = String(value || '').trim().toLowerCase();
  return Object.entries(CITY_ALIASES).find(([city, aliases]) => city.toLowerCase() === text || aliases.includes(text))?.[0] || value;
}

function cityLocation(value) {
  const city = canonicalCity(value);
  if (city === 'Puducherry') return 'Puducherry, India';
  return city === 'Tamil Nadu' ? 'Tamil Nadu, India' : `${city}, Tamil Nadu, India`;
}

/**
 * Job categories for a fresher, in priority order.
 * The FIRST category whose keyword appears in a job title wins,
 * so put the most specific categories first.
 */
const CATEGORIES = [
  {
    name: 'Government',
    keywords: [
      'tnpsc', 'tamil nadu public service', 'government', 'govt', 'tamil nadu government',
      'railway', 'postal', 'ssc', 'bank po', 'ibps', 'constable', 'police', 'fireman',
      'tangedco', 'metrowater', 'recruitment board', 'trb', 'village administrative',
    ],
  },
  {
    name: 'Software',
    keywords: [
      'software developer', 'software engineer', 'software tester', 'software trainee',
      'full stack', 'fullstack', 'front end', 'frontend', 'back end', 'backend',
      'java developer', 'java engineer', 'python developer', 'python engineer',
      'web developer', 'web designer', 'android developer', 'ios developer',
      'php developer', 'dot net', 'dotnet', '.net developer', 'react developer',
      'node developer', 'nodejs', 'qa engineer', 'quality assurance engineer',
      'test engineer', 'automation engineer', 'trainee engineer', 'graduate engineer trainee',
      'developer', 'programmer', 'devops', 'cloud engineer', 'data engineer',
      'support engineer', 'technical support engineer', 'application engineer',
      'software', 'sde', 'engineer trainee',
    ],
  },
  {
    name: 'Data & Analytics',
    keywords: [
      'data analyst', 'business analyst', 'data scientist', 'data science',
      'analytics', 'analyst', 'power bi', 'tableau', 'sql developer', 'mis executive',
    ],
  },
  {
    name: 'Healthcare',
    keywords: [
      'nurse', 'staff nurse', 'nursing', 'pharmacist', 'pharmacy', 'lab technician',
      'laboratory technician', 'lab technologist', 'radiographer', 'physiotherapist',
      'dental', 'medical officer', 'hospital', 'dialysis technician', 'ot technician',
    ],
  },
  {
    name: 'Teaching',
    keywords: [
      'teacher', 'lecturer', 'professor', 'assistant professor', 'tutor', 'faculty',
      'teaching', 'academic', 'pg teacher', 'primary teacher',
    ],
  },
  {
    name: 'Accounting & Finance',
    keywords: [
      'accountant', 'accounts', 'accounting', 'audit', 'auditor', 'finance',
      'billing', 'tally', 'gst', 'taxation', 'book keeping', 'bookkeeping',
    ],
  },
  {
    name: 'Sales & Marketing',
    keywords: [
      'sales executive', 'sales officer', 'sales', 'telecaller', 'tele caller',
      'business development', 'marketing', 'field executive', 'relationship manager',
      'customer care', 'customer support', 'bpo', 'voice process', 'inside sales',
    ],
  },
  {
    name: 'Engineering & Manufacturing',
    keywords: [
      'mechanical engineer', 'civil engineer', 'electrical engineer', 'electronics engineer',
      'production engineer', 'manufacturing', 'quality engineer', 'design engineer',
      'technician', 'machine operator', 'production', 'maintenance engineer',
      'graduate apprentice', 'apprentice',
    ],
  },
  {
    name: 'Back Office & Admin',
    keywords: [
      'data entry', 'back office', 'backoffice', 'admin', 'administration',
      'receptionist', 'office assistant', 'documentation', 'front office',
      'computer operator', 'clerk', 'store keeper', 'warehouse',
    ],
  },
];

const DEFAULT_CATEGORY = 'Other';

/**
 * The keywords we search for on each source, taken from the categories above.
 * Kept short on purpose, because every keyword means one page fetch.
 */
const SEARCH_KEYWORDS = [
  'software developer',
  'fresher',
  'data analyst',
  'accountant',
  'nurse',
  'teacher',
  'sales executive',
  'data entry',
];

// ---- Limits and politeness -------------------------------------------------

/** Never take more than this many jobs from one single source module per run. */
const MAX_JOBS_PER_SOURCE = 150;

/** Never look at more than this many listing pages per source per run. */
const MAX_PAGES_PER_SOURCE = 4;

/** Wait a random 1.5-3.5 seconds between requests (as required). */
const MIN_DELAY_MS = 1500;
const MAX_DELAY_MS = 3500;

/** A single plain HTTP request may not take longer than this. */
const HTTP_TIMEOUT_MS = 30000;

/** A Playwright page load may not take longer than this. */
const RENDER_TIMEOUT_MS = 45000;

/** "Never retry more than twice" -> at most 2 attempts in total. */
const MAX_ATTEMPTS = 2;

/** Tier 3 sources only run when you explicitly ask for them. */
const ENABLE_TIER3 = process.env.ENABLE_TIER3 === 'true';

module.exports = {
  PRIORITY_CITIES,
  canonicalCity,
  cityLocation,
  CITIES,
  CITY_ALIASES,
  CATEGORIES,
  DEFAULT_CATEGORY,
  SEARCH_KEYWORDS,
  MAX_JOBS_PER_SOURCE,
  MAX_PAGES_PER_SOURCE,
  MIN_DELAY_MS,
  MAX_DELAY_MS,
  HTTP_TIMEOUT_MS,
  RENDER_TIMEOUT_MS,
  MAX_ATTEMPTS,
  ENABLE_TIER3,
};
