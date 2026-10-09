'use strict';
// Pure search/integrity functions. Never turn a failed check into a closed job.
const crypto = require('node:crypto');
const DEFAULT = Object.freeze({ configured: false, branch: null, skills: [], experience_years: null,
  travel_radius_km: 0, cities: ['Tiruvannamalai', 'Vellore', 'Puducherry', 'Chennai'],
  roles: ['software engineer', 'developer', 'backend', 'full-stack', 'data engineer', 'python'] });
const GROUPS = [
  ['software engineer', 'software developer', 'sde', 'developer', 'programmer'],
  ['backend', 'back end', 'backend developer', 'server side'],
  ['full stack', 'fullstack', 'full-stack'], ['frontend', 'front end', 'react', 'angular'],
  ['data', 'data engineer', 'data engineering', 'etl', 'data scientist', 'data analyst'],
  ['python', 'django', 'flask', 'fastapi'], ['devops', 'cloud engineer', 'site reliability', 'sre'],
  ['mechanical engineer', 'mechanical'], ['civil engineer', 'civil'],
  ['electrical engineer', 'electrical'], ['electronics engineer', 'electronics'],
];
const CITIES = { Tiruvannamalai: [12.2253, 79.0747, ['tiruvannamalai', 'thiruvannamalai', 'tiruvanamalai']],
  Vellore: [12.9165, 79.1325, ['vellore']], Puducherry: [11.9416, 79.8083, ['puducherry', 'pondicherry']],
  Chennai: [13.0827, 80.2707, ['chennai', 'madras']], Chengalpattu: [12.6819, 79.9888, ['chengalpattu']],
  Sriperumbudur: [12.9675, 79.9410, ['sriperumbudur']], Ranipet: [12.9276, 79.3330, ['ranipet']],
  Tirupattur: [12.4950, 78.5678, ['tirupattur', 'tirupathur']] };
const text = v => String(v || '').toLowerCase().replace(/[^a-z0-9+#.]+/g, ' ').trim().replace(/\s+/g, ' ');
function contains(hay, needle) { return (` ${text(hay)} `).includes(` ${text(needle)} `); }
function expand(role) { const n = text(role); return [...new Set([n, ...GROUPS.filter(g => g.some(w => text(w) === n)).flat().map(text)])].filter(Boolean); }
function city(value) { const n = text(value); return Object.keys(CITIES).find(k => CITIES[k][2].some(a => contains(n, a))) || null; }
function distance(a, b) { if (!CITIES[a] || !CITIES[b]) return null;
  const [lat1, lon1] = CITIES[a], [lat2, lon2] = CITIES[b], r = Math.PI / 180;
  const v = Math.sin((lat2-lat1)*r/2)**2 + Math.cos(lat1*r)*Math.cos(lat2*r)*Math.sin((lon2-lon1)*r/2)**2;
  return Math.round(6371 * 2 * Math.atan2(Math.sqrt(v), Math.sqrt(1-v))); }
function preset(input = {}) { const p = { ...DEFAULT, ...input };
  if (!Array.isArray(p.cities) || !p.cities.length || p.cities.some(c => !city(c))) throw Error('Use a supported city');
  p.cities = [...new Set(p.cities.map(city))];
  if (!Array.isArray(p.roles) || !p.roles.length || p.roles.length > 12) throw Error('Use 1-12 roles');
  if (!Array.isArray(p.skills) || p.skills.length > 30) throw Error('Use at most 30 skills');
  p.roles = p.roles.map(v => String(v).trim().slice(0,80)); if(p.roles.some(v=>!v))throw Error('Role must not be empty');
  p.skills = p.skills.map(v => String(v).trim().slice(0,40)).filter(Boolean);
  if (!Number.isFinite(p.travel_radius_km) || p.travel_radius_km < 0 || p.travel_radius_km > 300) throw Error('Radius must be 0-300 km');
  if (p.experience_years !== null && (!Number.isFinite(p.experience_years) || p.experience_years < 0 || p.experience_years > 50)) throw Error('Experience must be unknown or 0-50');
  return p; }
function canonicalUrl(value) { try { const u = new URL(value); if (!['https:','http:'].includes(u.protocol)) return '';
  u.hash = ''; for (const k of [...u.searchParams.keys()]) if (/^(utm_|gclid|fbclid|ref$|source$|tracking)/i.test(k)) u.searchParams.delete(k);
  u.searchParams.sort(); u.pathname = u.pathname.replace(/\/$/,''); return u.toString(); } catch { return ''; } }
function key(job) { const url = canonicalUrl(job.apply_url);
  // Requisition ids are merged only within the same employer, never title alone.
  const req = job.requisition_id || job.job_reference;
  return req && text(job.company) ? `req:${text(job.company)}:${String(req).trim().toLowerCase()}` : `url:${url || job.id}`; }
function provenance(j) { return { source: j.source || 'unknown', url: j.apply_url, verified: j.verified === true,
  checked_at: j.verified_at || null, reason: j.verify_reason || 'not_checked' }; }
function dedupe(jobs) { const map = new Map(), urls = new Map();
  for (const original of jobs) { if (!original || !canonicalUrl(original.apply_url)) continue;
    const url = canonicalUrl(original.apply_url), k = urls.get(url) || key(original); urls.set(url,k);
    const j = { ...original, id: crypto.createHash('sha256').update(k).digest('hex').slice(0,24) };
    const old = map.get(k), evidence = [...(old?.provenance || []), ...(original.provenance || []), provenance(j)];
    const best = !old || (j.verified === true && old.verified !== true) ? j : old;
    map.set(k, { ...best, provenance: [...new Map(evidence.map(e => [`${e.source}|${e.url}`,e])).values()] }); }
  return [...map.values()]; }
function integrity(j) { if (j.verify_reason === 'expired_deadline' || [404,410].includes(j.http_status)) return 'closed';
  if (j.verify_reason === 'access_denied' || j.http_status === 403) return 'access_denied';
  if (j.verified === true) return 'verified';
  return 'uncertain'; }
function transient(j) { return j.verified !== true && (j.http_status === 429 || j.http_status === 408 || j.http_status >= 500 ||
  ['request_failed','source_unreachable','timeout','retry_pending'].includes(j.verify_reason)); }
function retryAfter(value, now) { const seconds = Number(value); if (String(value || '').trim() && Number.isFinite(seconds) && seconds >= 0) return now + seconds*1000;
  const date = Date.parse(value); return Number.isFinite(date) ? Math.max(now,date) : now; }
function reconcile(current, previous = [], queue = [], now = Date.now()) {
  const oldQ = new Map(queue.map(e => [e.key,e])); const combined = dedupe(current); const seen = new Set(combined.map(key));
  // Missing from a scrape is not evidence of closure; retain as uncertain, not public live.
  for (const old of previous) if (!seen.has(key(old)) && integrity(old)!=='closed') {
    combined.push({ ...old, verified: false, retry_deferred: true,
      verify_reason: integrity(old)==='access_denied'?'access_denied':'not_seen_this_run', integrity: 'uncertain' }); }
  const next = [];
  for (const j of combined) { j.integrity = integrity(j); const q = oldQ.get(key(j));
    if (['closed','access_denied'].includes(j.integrity) || (!transient(j) && j.verify_reason !== 'not_seen_this_run')) continue;
    const before = q?.attempts ?? j.retry_attempts ?? 0;
    const attempts = j.retry_deferred ? before : before + (j.verify_reason === 'not_seen_this_run' ? 0 : 1);
    const first = q?.first_seen ?? j.retry_first_seen ?? now;
    j.retry_attempts = attempts; j.retry_first_seen = first;
    if (attempts >= 3 || now-first > 7*86400000) { j.retry_state = 'exhausted_uncertain'; continue; }
    const backoff = Math.min(24*3600000, 3600000 * 2**Math.max(0,attempts-1));
    const due = j.retry_deferred && q ? q.due : Math.max(now+backoff,retryAfter(j.retry_after,now));
    j.retry_state = 'pending'; j.retry_due = new Date(due).toISOString();
    next.push({ key: key(j), job: { ...j, verified: false }, attempts, first_seen: first, due }); }
  const bounded = next.sort((a,b) => a.due-b.due).slice(0,200), queuedKeys = new Set(bounded.map(q=>q.key));
  for(const j of combined) if(j.retry_state==='pending'&&!queuedKeys.has(key(j))) { j.retry_state='capacity_deferred_uncertain'; delete j.retry_due; }
  return { jobs: combined, queue: bounded }; }
function compileProfile(profile) {
  const p = preset(profile), aliases = p.roles.flatMap(expand).filter(w => w !== 'data');
  const distances = new Map(Object.keys(CITIES).map(c => [c, Math.min(...p.cities.map(origin => distance(origin,c)))]));
  return { p, aliases: aliases.map(w => ` ${text(w)} `), branch: p.branch ? ` ${text(p.branch)} ` : null,
    skills: p.skills.map(s => ({ original:s, needle:` ${text(s)} ` })), distances };
}
function scoreCompiled(job, compiled, now) { const { p, aliases, distances } = compiled;
  const title = ` ${text(job.title)} `, hay = ` ${text([job.title, job.description, ...(job.skills || [])].join(' '))} `;
  const roleMatch = aliases.some(w => title.includes(w));
  if (!roleMatch) return { score: -1, reasons: ['role_not_matched'] };
  // Prefer original location evidence to a legacy canonical city that collapsed suburbs.
  const location = city(job.location) || city(job.city); const km = location ? distances.get(location) : null;
  if (km === null || km > p.travel_radius_km) return { score: -1, reasons: ['location_outside_preset_or_unknown'] };
  const reasons = ['role_match', km === 0 ? 'selected_city' : `approx_${km}km_city_centres`];
  let value = 50 + (km === 0 ? 20 : Math.max(0,15-km/20));
  if(compiled.branch && hay.includes(compiled.branch)) { value += 5; reasons.push('stated_branch_mentioned_not_eligibility_guarantee'); }
  const hits = compiled.skills.filter(s => hay.includes(s.needle)).map(s => s.original); value += Math.min(15,hits.length*5); if (hits.length) reasons.push(`skills:${hits.join(',')}`);
  const range = String(job.experience || '').match(/(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)/i);
  if (p.experience_years !== null && range && p.experience_years < Number(range[1])) { value -= 30; reasons.push('experience_below_stated_minimum'); }
  else if (p.experience_years === null) reasons.push('experience_unknown_not_eligibility_checked');
  // No fallback to scraped_at: an unknown posting date must stay unknown.
  const date = Date.parse(job.posted_at); if (Number.isFinite(date) && date <= now) { value += Math.max(0,15-(now-date)/86400000); reasons.push('posting_date_known'); }
  else reasons.push('posting_date_unknown');
  const state = integrity(job); value += state === 'verified' ? 15 : -15;
  if (job.source_type === 'company' || job.source_type === 'government') value += 5;
  reasons.push(`evidence:${state}`, `source:${job.source || 'unknown'}`);
  if (!p.configured) reasons.push('default_preset_personal_fit_unknown');
  return { score: Math.round(value), reasons, distance_km: km, distance_basis: 'approximate city-centre straight-line distance; not travel time', integrity: state }; }
function score(job, profile, now = Date.now()) { return scoreCompiled(job,compileProfile(profile),now); }
function rank(jobs, profile = DEFAULT, now = Date.now()) {
  const unique = dedupe(jobs); if(!unique.length) return [];
  const compiled = compileProfile(profile);
  return unique.map(j => ({ ...j, match: scoreCompiled(j,compiled,now) }))
    .filter(j => j.match.score >= 0 && !['closed','access_denied'].includes(j.match.integrity))
    .sort((a,b) => b.match.score-a.match.score || a.id.localeCompare(b.id)); }
module.exports = { DEFAULT, GROUPS, CITIES, preset, expand, city, distance, canonicalUrl, key, dedupe, integrity, transient, retryAfter, reconcile, score, rank };