'use strict';

/**
 * Small helper functions used by every other file.
 * Keeping them in one place means the scraping rules stay consistent.
 */

const crypto = require('crypto');
const { CITY_ALIASES, CATEGORIES, DEFAULT_CATEGORY } = require('./config');

// ---------- logging ---------------------------------------------------------

function stamp() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19);
}

function log(...args) {
  console.log(`[${stamp()}]`, ...args);
}

function logError(...args) {
  console.error(`[${stamp()}] ERROR`, ...args);
}

// ---------- sleeping --------------------------------------------------------

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Wait a random time between min and max milliseconds (keeps us polite). */
function politeSleep(minMs, maxMs) {
  const ms = Math.floor(minMs + Math.random() * Math.max(0, maxMs - minMs));
  return sleep(ms);
}

// ---------- text helpers ----------------------------------------------------

/** Squash all runs of whitespace into single spaces and trim. */
function tidy(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(/\s+/g, ' ').trim();
}

/** "Software Developer" -> "software-developer" (used to build search URLs). */
function slugifyValue(value) {
  return tidy(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

/** Cut a long string down to `max` characters (used for log lines). */
function clip(value, max) {
  const s = tidy(value);
  return s.length > max ? s.slice(0, max - 1) + '\u2026' : s;
}

/** Remove surrounding quotes and common HTML entities. */
// Note: `&amp;` is decoded LAST so a literal "&amp;lt;" stays "&lt;".
function unescapeEntities(value) {
  return tidy(value)
    .replace(/&nbsp;/g, ' ')
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/^["'\u201c\u2018]+|["'\u201d\u2019]+$/g, '');
}

// ---------- urls and ids ----------------------------------------------------

/** Remove ?query-string and #hash, so the same job keeps the same id. */
function cleanUrl(rawUrl) {
  if (!rawUrl) return '';
  try {
    const u = new URL(String(rawUrl).trim());
    u.search = '';
    u.hash = '';
    u.hostname = u.hostname.toLowerCase().replace(/^www\./, '');
    let out = u.toString();
    // Drop a trailing slash so "site.com/x/" and "site.com/x" are the same job.
    if (out.endsWith('/') && u.pathname !== '/') out = out.slice(0, -1);
    return out;
  } catch (err) {
    return tidy(rawUrl);
  }
}

/** The job id: first 12 characters of the sha1 hash of the cleaned apply URL. */
function jobId(applyUrl) {
  return crypto.createHash('sha1').update(cleanUrl(applyUrl)).digest('hex').slice(0, 12);
}

/**
 * Get the "site name" of a URL, e.g. https://www.freshersworld.com/x -> freshersworld.com
 * We use it for the `source` field and for deciding if a redirect left the site.
 */
const MULTI_PART_SUFFIXES = [
  'co.in', 'co.uk', 'com.au', 'co.jp', 'org.in', 'net.in', 'gov.in', 'ac.in',
  'nic.in', 'res.in', 'edu.in', 'firm.in', 'gen.in', 'ind.in',
];

function registrableDomain(rawUrl) {
  if (!rawUrl) return '';
  try {
    const host = new URL(String(rawUrl)).hostname.toLowerCase().replace(/^www\./, '');
    const parts = host.split('.');
    if (parts.length <= 2) return host;
    const lastTwo = parts.slice(-2).join('.');
    if (MULTI_PART_SUFFIXES.includes(lastTwo) && parts.length >= 3) return parts.slice(-3).join('.');
    return lastTwo;
  } catch (err) {
    return '';
  }
}

// ---------- field guessing from text ---------------------------------------

/** Find the first Tamil Nadu city mentioned in some text. null if none. */
function detectCity(...texts) {
  const haystack = texts.filter(Boolean).join(' ').toLowerCase();
  if (!haystack) return null;
  for (const [city, aliases] of Object.entries(CITY_ALIASES)) {
    for (const alias of aliases) {
      const idx = haystack.indexOf(alias);
      if (idx === -1) continue;
      // Make sure we matched a whole word, not part of a longer word.
      const before = idx === 0 ? ' ' : haystack[idx - 1];
      const after = haystack[idx + alias.length] || ' ';
      if (!/[a-z0-9]/.test(before) && !/[a-z0-9]/.test(after)) return city;
    }
  }
  return null;
}

/** Work out which of our categories a job title belongs to. */
function detectCategory(...texts) {
  const haystack = texts.filter(Boolean).join(' ').toLowerCase();
  if (!haystack) return DEFAULT_CATEGORY;
  for (const category of CATEGORIES) {
    for (const keyword of category.keywords) {
      if (haystack.includes(keyword)) return category.name;
    }
  }
  return DEFAULT_CATEGORY;
}

/** Full-time / Part-time / Internship / Contract, or null when the page is silent. */
function detectEmploymentType(...texts) {
  const haystack = texts.filter(Boolean).join(' ').toLowerCase();
  if (!haystack) return null;
  if (/\bintern(ship)?\b/.test(haystack)) return 'Internship';
  if (/\bpart[\s-]?time\b/.test(haystack)) return 'Part-time';
  if (/\bcontract\b|\bcontractual\b|\btemporary\b|\bpurely temporary\b/.test(haystack)) return 'Contract';
  if (/\bfreelance\b/.test(haystack)) return 'Freelance';
  if (/\bfull[\s-]?time\b/.test(haystack)) return 'Full-time';
  return null;
}

/** Fresher / 0-2 years / 3+ years, or null when the page is silent. */
function detectExperience(...texts) {
  const haystack = texts.filter(Boolean).join(' ').toLowerCase();
  if (!haystack) return null;
  if (/\bfresher|freshers|no experience|entry level\b/.test(haystack)) return 'Fresher';
  const range = /(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*(?:year|yr)/.exec(haystack);
  if (range) return `${range[1]}-${range[2]} years`;
  const single = /(\d{1,2})\+?\s*(?:year|yr)/.exec(haystack);
  if (single) return `${single[1]}+ years`;
  const months = /(\d{1,2})\s*month/.exec(haystack);
  if (months) return `${months[1]} months`;
  return null;
}

/**
 * Read a salary out of a piece of text - but ONLY if the text really states one.
 * Returns the original wording (never a guessed number) or null.
 * This is deliberately strict: no amount on the page means no salary.
 */
function detectSalary(...texts) {
  const patterns = [
    /(?:rs\.?|inr|\u20b9)\s*\d[\d,.]*\s*(?:-|to|\u2013)?\s*(?:rs\.?|inr|\u20b9)?\s*\d*[\d,.]*\s*(?:\/\s*)?(?:per\s+)?(?:month|monthly|annum|year|yr|p\.?a\.?|lpa|lakh|lakhs)?/i,
    /\d[\d,.]*\s*(?:\/\s*)?(?:per\s+)?(?:month|monthly|per\s+annum|p\.?a\.?|lpa)\b/i,
    /\d+(?:\.\d+)?\s*(?:lpa|lakhs?\s+per\s+annum)\b/i,
    /\bstipend\b[^.;\n]{0,40}/i,
    /\bnot disclosed\b/i,
  ];
  for (const raw of texts) {
    const text = tidy(raw);
    if (!text) continue;
    for (const pattern of patterns) {
      const match = pattern.exec(text);
      if (match) return tidy(match[0]).replace(/^[-,;\s]+|[-,;\s]+$/g, '');
    }
  }
  return null;
}

/**
 * Turn a date written on a page into YYYY-MM-DD.
 * Returns null if we cannot be sure - we never invent a date.
 */
function toIsoDate(value) {
  if (!value) return null;
  const text = tidy(value);

  // Already ISO: 2026-09-14
  const iso = /\b(\d{4})-(\d{2})-(\d{2})\b/.exec(text);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;

  // 14/09/2026 or 14-09-2026 or 14.09.2026 (day first, Indian style)
  const dmy = /\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b/.exec(text);
  if (dmy) {
    const day = dmy[1].padStart(2, '0');
    const month = dmy[2].padStart(2, '0');
    return `${dmy[3]}-${month}-${day}`;
  }

  // "14 Sep 2026" / "14 September 2026" / "Sep 14, 2026" / "5th June 2026"
  const monthNames = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  const named = /(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?\s*,?\s*(\d{4})|([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})/i.exec(text);
  if (named) {
    const rawMonth = named[2] || named[4];
    const rawDay = named[1] || named[5] || '1';
    const rawYear = named[3] || named[6];
    const monthIndex = monthNames.findIndex((m) => rawMonth.toLowerCase().startsWith(m));
    if (monthIndex >= 0 && rawYear) {
      const day = String(parseInt(rawDay, 10)).padStart(2, '0');
      return `${rawYear}-${String(monthIndex + 1).padStart(2, '0')}-${day}`;
    }
  }
  return null;
}

/** Get a YYYY-MM-DD date out of a Unix timestamp in seconds or milliseconds. */
function timestampToIsoDate(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return null;
  // Anything above 1e12 is already in milliseconds (1e12 ms = year 2001).
  const ms = n > 1e12 ? n : n * 1000;
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return null;
  if (d.getFullYear() < 2000 || d.getFullYear() > 2100) return null;
  return d.toISOString().slice(0, 10);
}

/**
 * Convert the "how old is this ad" text that job sites show
 * ("Posted: 4 days ago", "2 weeks ago", "Just now") into a real YYYY-MM-DD.
 *
 * This is not guessing: the page really did state the age, we are only doing
 * the arithmetic. If the page says nothing about age we return null.
 */
function relativeDateToIso(text) {
  const value = tidy(text).toLowerCase();
  if (!value) return null;
  if (/just now|today|few seconds|few minutes|right now/.test(value)) {
    return new Date().toISOString().slice(0, 10);
  }
  const match = /(\d+)\s*\+?\s*(minute|hour|day|week|month|year)/.exec(value);
  if (!match) return null;

  const amount = parseInt(match[1], 10);
  const unit = match[2];
  const when = new Date();

  if (unit === 'minute' || unit === 'hour') {
    // Anything under a day is "today" for our purposes.
  } else if (unit === 'day') {
    when.setDate(when.getDate() - amount);
  } else if (unit === 'week') {
    when.setDate(when.getDate() - amount * 7);
  } else if (unit === 'month') {
    when.setMonth(when.getMonth() - amount);
  } else if (unit === 'year') {
    when.setFullYear(when.getFullYear() - amount);
  } else {
    return null;
  }
  if (when.getFullYear() < 2000) return null;
  return when.toISOString().slice(0, 10);
}

/** Undo the extra backslashes used inside JavaScript string literals. */
function unescapeJsonInScript(text) {
  return String(text || '')
    .replace(/\\"/g, '"')
    .replace(/\\\//g, '/')
    .replace(/\\n/g, ' ')
    .replace(/\\u([0-9a-fA-F]{4})/g, (whole, hex) => String.fromCharCode(parseInt(hex, 16)));
}

// ---------- detail enrichment helpers ---------------------------------------

const EDUCATION_PATTERNS = [
  { name: 'B.E / B.Tech', regex: /\b(?:b\.?e|b\.?tech|bachelor of engineering|bachelor of technology)\b/i },
  { name: 'M.E / M.Tech', regex: /\b(?:m\.?e|m\.?tech|master of engineering)\b/i },
  { name: 'MCA / BCA', regex: /\b(?:mca|bca)\b/i },
  { name: 'B.Sc / M.Sc', regex: /\b(?:b\.?sc|m\.?sc)\b/i },
  { name: 'B.Com / M.Com', regex: /\b(?:b\.?com|m\.?com)\b/i },
  { name: 'MBA', regex: /\b(?:mba|pgdm)\b/i },
  { name: 'Diploma', regex: /\b(?:diploma|polytechnic)\b/i },
  { name: 'ITI', regex: /\biti\b/i },
  { name: 'Nursing (B.Sc / GNM)', regex: /\b(?:gnm|b\.?sc\s+nursing|anm)\b/i },
  { name: 'MBBS / Medical', regex: /\b(?:mbbs|bds|bams|bhms)\b/i },
  { name: '10th / 12th Pass', regex: /\b(?:10th|12th|sslc|hsc|plus two|\+2 pass)\b/i },
  { name: 'Any Graduate', regex: /\b(?:any graduate|any degree|graduation|graduate|degree)\b/i },
  { name: 'Post Graduate', regex: /\b(?:post graduate|post graduation|any pg)\b/i },
];

function detectEducation(...texts) {
  const haystack = texts.filter(Boolean).join(' ');
  if (!haystack) return null;
  for (const item of EDUCATION_PATTERNS) {
    if (item.regex.test(haystack)) return item.name;
  }
  return null;
}

const SKILL_PATTERNS = [
  { name: '.NET', regex: /\b(?:\.net|dotnet|dot\s+net|asp\.net)\b/i },
  { name: 'C#', regex: /\b(?:c#|c-sharp)\b/i },
  { name: 'Java', regex: /\bjava\b(?!script)/i },
  { name: 'JavaScript', regex: /\b(?:javascript|js)\b/i },
  { name: 'TypeScript', regex: /\b(?:typescript|ts)\b/i },
  { name: 'Python', regex: /\bpython\b/i },
  { name: 'React', regex: /\breact(?:\.js)?\b/i },
  { name: 'Angular', regex: /\bangular(?:\.js)?\b/i },
  { name: 'Node.js', regex: /\bnode(?:\.js)?\b/i },
  { name: 'SQL', regex: /\b(?:sql|mysql|postgresql)\b/i },
  { name: 'MongoDB', regex: /\bmongodb\b/i },
  { name: 'AWS', regex: /\baws\b/i },
  { name: 'Azure', regex: /\bazure\b/i },
  { name: 'Docker', regex: /\bdocker\b/i },
  { name: 'PHP', regex: /\bphp\b/i },
  { name: 'Flutter', regex: /\bflutter\b/i },
  { name: 'Android', regex: /\bandroid\b/i },
  { name: 'iOS', regex: /\bios\b/i },
  { name: 'HTML/CSS', regex: /\b(?:html|css)\b/i },
  { name: 'Git', regex: /\bgit\b/i },
  { name: 'Spring Boot', regex: /\bspring\s*boot\b/i },
  { name: 'REST API', regex: /\brest(?:ful)?\s*(?:api)?\b/i },
  { name: 'Full Stack', regex: /\bfull\s*stack\b/i },
  { name: 'AI / Machine Learning', regex: /\b(?:ai\b|artificial intelligence|machine learning|deep learning)\b/i },
  { name: 'Testing / QA', regex: /\b(?:tester|testing|qa\b|quality assurance)\b/i },
  { name: 'Data Analysis', regex: /\b(?:data analyst|data analysis|power bi|tableau|analytics)\b/i },
  { name: 'Cloud Computing', regex: /\b(?:cloud\b|gcp|google cloud)\b/i },
  { name: 'Blockchain', regex: /\bblockchain\b/i },
  { name: 'Excel', regex: /\b(?:excel|advanced excel)\b/i },
  { name: 'Tally', regex: /\btally(?:\s*erp)?\b/i },
  { name: 'Accounting', regex: /\b(?:accounting|accountant|accounts|bookkeeping)\b/i },
  { name: 'GST', regex: /\bgst\b/i },
  { name: 'Sales', regex: /\b(?:sales|business development|b2b|b2c)\b/i },
  { name: 'Digital Marketing', regex: /\b(?:digital marketing|seo|sem|social media marketing)\b/i },
  { name: 'Nursing', regex: /\b(?:nursing|nurse|patient care|icu)\b/i },
  { name: 'Customer Support', regex: /\b(?:customer support|customer care|bpo|call center)\b/i },
  { name: 'Data Entry', regex: /\bdata\s*entry\b/i },
  { name: 'Teaching', regex: /\b(?:teaching|teacher|faculty|tutor)\b/i },
  { name: 'AutoCAD', regex: /\bautocad\b/i },
  { name: 'Frontend', regex: /\bfrontend\b/i },
  { name: 'Backend', regex: /\bbackend\b/i }
];

function detectSkills(...texts) {
  const haystack = texts.filter(Boolean).join(' ');
  if (!haystack) return [];
  const found = new Set();
  for (const item of SKILL_PATTERNS) {
    if (item.regex.test(haystack)) {
      found.add(item.name);
      if (found.size >= 8) break;
    }
  }
  return Array.from(found);
}

function detectDeadline(...texts) {
  const haystack = texts.filter(Boolean).join(' ');
  if (!haystack) return null;
  const match = /(?:last\s+date|closing\s+date|apply\s+before|deadline|end\s+date)[^\d\w]{0,10}(\d{1,2}(?:st|nd|rd|th)?\s+[a-z]{3,9}\s+\d{2,4}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2})/i.exec(haystack);
  if (match) {
    const rawDate = match[1];
    return toIsoDate(rawDate) || rawDate;
  }
  return null;
}

function isFresher(experience, ...texts) {
  const expStr = String(experience || '').toLowerCase();
  if (/fresher|0\s*years?|0\s*-\s*[12]|entry\s*level|intern/.test(expStr)) return true;
  const haystack = texts.filter(Boolean).join(' ').toLowerCase();
  return /\bfresher|freshers|entry level|no experience required\b/.test(haystack);
}

function cleanSummary(text, maxChars = 280) {
  if (!text) return '';
  const clean = tidy(text)
    .replace(/(?:cookie|privacy|terms of use|all rights reserved|sign in|log in|subscribe)[^.]*\./gi, '')
    .trim();
  if (clean.length <= maxChars) return clean;
  const cut = clean.slice(0, maxChars);
  const lastSpace = cut.lastIndexOf(' ');
  return cut.slice(0, lastSpace > 60 ? lastSpace : maxChars - 1) + '…';
}

module.exports = {
  log,
  logError,
  sleep,
  politeSleep,
  tidy,
  slugifyValue,
  clip,
  unescapeEntities,
  cleanUrl,
  jobId,
  registrableDomain,
  detectCity,
  detectCategory,
  detectEmploymentType,
  detectExperience,
  detectSalary,
  toIsoDate,
  timestampToIsoDate,
  relativeDateToIso,
  unescapeJsonInScript,
  detectEducation,
  detectSkills,
  detectDeadline,
  isFresher,
  cleanSummary,
};
