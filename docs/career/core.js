/* Shared deterministic career logic. No network or browser storage. */
(function (root) {
  'use strict';
  const STATUSES = ['Saved', 'Applied', 'Interview', 'Offer', 'Rejected'];
  const SKILLS = ['Python', 'JavaScript', 'TypeScript', 'Java', 'C++', 'C#', '.NET', 'React', 'Angular', 'Vue', 'Node.js', 'SQL', 'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'HTML', 'CSS', 'Git', 'Docker', 'Kubernetes', 'AWS', 'Azure', 'GCP', 'Linux', 'Excel', 'Power BI', 'Tableau', 'Pandas', 'NumPy', 'TensorFlow', 'PyTorch', 'FastAPI', 'Django', 'Flask', 'Spring', 'REST', 'GraphQL', 'Figma', 'Testing', 'Communication', 'Accounting', 'Tally', 'Nursing'];
  const text = value => typeof value === 'string' ? value.trim() : '';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  function url(value) {
    try {
      const u = new URL(value);
      if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password) return '';
      u.hash = '';
      [...u.searchParams.keys()].forEach(k => { if (/^(utm_|fbclid$|gclid$|trk$)/i.test(k)) u.searchParams.delete(k); });
      u.searchParams.sort();
      u.pathname = u.pathname.replace(/\/$/, '') || '/';
      return u.href;
    } catch { return ''; }
  }
  function terms(value) {
    return [...new Set((Array.isArray(value) ? value : text(value).split(/[,\n]/)).map(text).filter(Boolean))].slice(0, 50);
  }
  function contains(haystack, needle) {
    const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp('(^|[^a-z0-9])' + escaped + '(?=$|[^a-z0-9])', 'i').test(haystack);
  }
  function date(value) {
    if (!/^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(text(value))) return null;
    const day = value.slice(0, 10);
    const calendar = new Date(day + 'T00:00:00Z');
    if (!Number.isFinite(calendar.getTime()) || calendar.toISOString().slice(0, 10) !== day) return null;
    const result = new Date(value.length === 10 ? value + 'T23:59:59Z' : value);
    return Number.isFinite(result.getTime()) ? result : null;
  }
  function normalize(raw) {
    const job = raw && typeof raw === 'object' ? raw : {};
    return {
      id: text(String(job.id ?? '')), url: url(job.url || job.apply_url || job.link || job.raw_link),
      title: text(job.title || job.role).slice(0, 300) || 'Untitled opportunity',
      company: text(job.company).slice(0, 200) || 'Company not stated',
      city: text(job.city || job.location).slice(0, 200),
      description: text(job.description || job.summary).slice(0, 10000), skills: terms(job.skills),
      salary: text(job.salary || job.package).slice(0, 200), experience: text(job.experience).slice(0, 200),
      verifiedAt: text(job.verifiedAt || job.verified_at || job.source_checked_at),
      postedAt: text(job.postedAt || job.posted_at || job.date_posted),
      deadline: text(job.deadline || job.expires_at || job.walkin_date || job.event_date),
      checkStatus: job.checkStatus || (job.verified === true ? 'success' : job.verified === false ? 'failed' : 'unknown'),
      closed: job.closed === true || ['expired', 'http_404', 'http_410', 'closed'].includes(job.verify_reason),
    };
  }
  function freshness(raw, now = new Date()) {
    const j = normalize(raw), end = date(j.deadline), checked = date(j.verifiedAt), posted = date(j.postedAt);
    if (j.closed || (end && end < now)) return { expired: true, label: 'Expired / closed', checked: j.verifiedAt };
    if (j.checkStatus === 'failed') return {expired:false, stale:true, label:'Last availability check failed', checked:j.verifiedAt};
    if (checked && checked <= now) return { expired: false, stale: now - checked > 7 * 86400000, label: now - checked > 7 * 86400000 ? 'Check is over 7 days old' : 'Link checked recently', checked: j.verifiedAt };
    return { expired: false, stale: !posted || now - posted > 30 * 86400000, label: posted && now - posted > 30 * 86400000 ? 'Older listing • verify availability' : 'Availability not checked', checked: '' };
  }
  function salaryLpa(value) {
    if (!/\b(lpa|lakhs?|lacs?)\b/i.test(value)) return null;
    const match = String(value).match(/(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(?:lpa|lakhs?|lacs?)/i);
    return match ? Number(match[1]) : null;
  }
  function cityName(value) { return String(value).toLowerCase().replace(/pondicherry/g, 'puducherry').replace(/th?iruv?annamalai|thiruannamalai/g, 'tiruvannamalai'); }
  function match(raw, preferences = {}) {
    const j = normalize(raw), reasons = [], missing = [];
    const haystack = [j.title, j.description, ...j.skills].join(' ');
    let earned = 0, possible = 0;
    const skills = terms(preferences.skills), cities = terms(preferences.cities);
    if (skills.length) {
      possible += 50;
      const matches = skills.filter(s => contains(haystack, s));
      earned += 50 * matches.length / skills.length;
      reasons.push(matches.length ? 'Skills found: ' + matches.join(', ') : 'No preferred skills stated');
      missing.push(...skills.filter(s => !matches.includes(s)));
    }
    if (cities.length) {
      possible += 20;
      const city = cities.find(c => contains(cityName(j.city), cityName(c)));
      if (city) { earned += 20; reasons.push('Preferred location: ' + city); }
      else reasons.push(j.city ? 'Outside preferred locations' : 'Location not stated');
    }
    if (preferences.remote) { possible += 10; if (/\bremote\b/i.test(j.city + ' ' + j.description)) { earned += 10; reasons.push('Remote work mentioned'); } else reasons.push('Remote work not stated'); }
    if (preferences.experience !== null && preferences.experience !== undefined && preferences.experience !== '') {
      possible += 15;
      const years = j.experience.match(/\d+(?:\.\d+)?/);
      if (years && Number(years[0]) <= Number(preferences.experience)) { earned += 15; reasons.push('Meets stated minimum experience'); }
      else reasons.push(years ? 'Minimum experience exceeds preference' : 'Experience not stated');
    }
    if (Number(preferences.minSalary) > 0) {
      possible += 15;
      const salary = salaryLpa(j.salary);
      if (salary !== null && salary >= Number(preferences.minSalary)) { earned += 15; reasons.push('Stated salary meets minimum'); }
      else reasons.push(salary === null ? 'Comparable annual salary not stated' : 'Stated salary below minimum');
    }
    return { score: possible ? Math.round(earned / possible * 100) : null, reasons, missing };
  }
  function compareResume(resume, description, skills = []) {
    const requested = terms([...SKILLS, ...terms(skills)]).filter(s => contains(description, s));
    const matched = requested.filter(s => contains(resume, s));
    const missing = requested.filter(s => !matched.includes(s));
    return { matched, missing, score: requested.length ? Math.round(matched.length / requested.length * 100) : null,
      suggestions: matched.map(s => `If accurate, add a concrete example of your ${s} work and its outcome.`).concat(missing.map(s => `The role mentions ${s}. Add it only if you have relevant experience; otherwise treat it as a learning goal.`)) };
  }
  function initial() { return { version: 1, preferences: { skills: [], cities: [], experience: null, minSalary: null, remote: false }, applications: {}, alerts: { enabled: false, followupsEnabled: false, time: '09:00', timezone: 'Asia/Kolkata', quietStart: '22:00', quietEnd: '08:00', minScore: 30, maxAgeDays: 30 } }; }
  function cleanState(raw) {
    if (!raw || raw.version !== 1 || !raw.applications || typeof raw.applications !== 'object' || Array.isArray(raw.applications)) throw new Error('Unsupported workspace backup. Choose a version 1 export.');
    const state = initial(), p = raw.preferences || {}, a = raw.alerts || {};
    state.preferences = { skills: terms(p.skills), cities: terms(p.cities), experience: p.experience === null || p.experience === '' || p.experience === undefined ? null : Number(p.experience), minSalary: p.minSalary === null || p.minSalary === '' || p.minSalary === undefined ? null : Number(p.minSalary), remote: p.remote === true };
    for (const [key, max] of [['experience', 60], ['minSalary', 1000]]) { const v = state.preferences[key]; if (v !== null && (!Number.isFinite(v) || v < 0 || v > max)) throw new Error('Invalid preference: ' + key); }
    if (Object.keys(raw.applications || {}).length > 1000) throw new Error('Maximum 1,000 tracked applications.');
    for (const entry of Object.values(raw.applications || {})) {
      if (!entry || !STATUSES.includes(entry.status)) throw new Error('Invalid application status.');
      const job = normalize(entry.job);
      if (!job.url) throw new Error('Application needs an HTTP(S) job URL.');
      if (entry.followUp && (!/^\d{4}-\d{2}-\d{2}$/.test(entry.followUp) || !date(entry.followUp))) throw new Error('Invalid follow-up date.');
      state.applications[job.url] = { job, status: entry.status, notes: text(entry.notes).slice(0, 5000), followUp: text(entry.followUp), updatedAt: text(entry.updatedAt) };
    }
    for (const k of ['time', 'quietStart', 'quietEnd']) { if (a[k] !== undefined && !/^([01]\d|2[0-3]):[0-5]\d$/.test(a[k])) throw new Error('Invalid alert time.'); }
    if (a.timezone) { try { new Intl.DateTimeFormat('en', { timeZone: a.timezone }); } catch { throw new Error('Use an IANA timezone, such as Asia/Kolkata.'); } }
    state.alerts = { ...state.alerts, ...Object.fromEntries(Object.keys(state.alerts).filter(k => a[k] !== undefined).map(k => [k, a[k]])) };
    for (const [key, min, max] of [['minScore', 0, 100], ['maxAgeDays', 1, 90]]) { if (!Number.isInteger(Number(state.alerts[key])) || Number(state.alerts[key]) < min || Number(state.alerts[key]) > max) throw new Error('Invalid alert threshold.'); state.alerts[key] = Number(state.alerts[key]); }
    state.alerts.enabled = a.enabled === true; state.alerts.followupsEnabled = a.followupsEnabled === true;
    return state;
  }
  const api = { STATUSES, SKILLS, escape, url, terms, date, normalize, freshness, match, compareResume, initial, cleanState };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.CareerCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
