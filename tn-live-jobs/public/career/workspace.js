(function () {
  'use strict';
  const C = window.CareerCore, KEY = 'myjob.career.v1';
  let state = C.initial(), revision = 0, host, options, busy = false, installEvent;
  const $ = id => host.querySelector('#cw-' + id);
  const clone = value => JSON.parse(JSON.stringify(value));
  function notice(message) { $('status').textContent = message; }
  function jobs() {
    const seen = new Set();
    return [...(options.getJobs?.() || [])].map(C.normalize).filter(j => j.url && !seen.has(j.url) && seen.add(j.url));
  }
  async function save(next) {
    if (busy) { notice('A save is already in progress. Please try again when it finishes.'); return false; }
    busy = true;
    try {
      next = C.cleanState(next);
      if (options.server) {
        const response = await fetch('/api/career/state', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ state: next, revision }) });
        if (!response.ok) throw new Error(response.status === 409 ? 'Changed in another session. Copy any unsaved text, then reload before saving.' : 'Save failed. Check your dashboard session and try again.');
        const data = await response.json(); revision = data.revision;
      } else {
        try { localStorage.setItem(KEY, JSON.stringify(next)); }
        catch { notice('Browser storage is unavailable. Export a backup before closing this page.'); state = next; return true; }
      }
      state = next;
      notice(options.server ? 'Saved to your private dashboard.' : 'Saved on this device. Export a backup to move to another device.');
      return true;
    } catch (error) { notice(error.message); return false; }
    finally { busy = false; }
  }
  function backup(filename, value, type = 'application/json') {
    const link = document.createElement('a'), href = URL.createObjectURL(new Blob([value], { type }));
    link.href = href; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(href), 1000);
  }
  function populate() {
    const p = state.preferences, a = state.alerts;
    $('skills').value = p.skills.join(', '); $('cities').value = p.cities.join(', ');
    $('experience').value = p.experience ?? ''; $('salary').value = p.minSalary ?? ''; $('remote').checked = p.remote;
    for (const key of ['enabled', 'followupsEnabled']) $(key).checked = a[key];
    for (const key of ['time', 'timezone', 'quietStart', 'quietEnd', 'minScore', 'maxAgeDays']) $(key).value = a[key];
  }
  function warnings(job) {
    const signals = C.warningSignals(job);
    return signals.length ? `<aside class="cw-risk" aria-label="Listing checks"><strong>Check before applying</strong><ul>${signals.map(s => `<li><strong>${C.escape(s.title)}:</strong> ${C.escape(s.detail)}</li>`).join('')}</ul><p class="cw-muted">Automated clues, not proof of fraud. Verify the employer independently.</p></aside>` : '<p class="cw-muted">No warning patterns detected. This is not an employer verification.</p>';
  }
  function card(job, result, sources = [job]) {
    const fresh = C.freshness(job);
    return `<article class="cw-card"><h3>${C.escape(job.title)}</h3><p>${C.escape(job.company)} · ${C.escape(job.city || 'Location not stated')}</p>
      <span class="cw-pill">${result.score === null ? 'Set preferences to rank' : result.score + '% preference match'}</span>
      <p class="cw-muted">${C.escape(fresh.label)} · Last checked: ${C.escape(fresh.checked || 'not recorded')}</p>
      ${result.reasons.length ? '<ul>' + result.reasons.map(r => '<li>' + C.escape(r) + '</li>').join('') + '</ul>' : ''}
      ${warnings(job)}
      ${sources.length > 1 ? `<details class="cw-sources"><summary>${sources.length} source links · Possible duplicate listings (${sources.filter(source => C.warningSignals(source).length).length} with warning clues)</summary><p class="cw-muted">Same stated role, employer and location. These may be separate openings; compare each source. Tracking remains separate for each link.</p>${sources.map(source => `<section><h4>${C.escape(new URL(source.url).hostname)}</h4><p>${C.escape(source.url)}</p><p class="cw-muted">${C.escape(C.freshness(source).label)} · ${C.escape(source.salary || 'Salary not stated')}</p>${warnings(source)}<div class="cw-toolbar"><a class="cw-link" href="${C.escape(source.url)}" target="_blank" rel="noopener noreferrer">View source</a><button type="button" data-track="${C.escape(source.url)}">${state.applications[source.url] ? 'Tracked' : 'Track application'}</button><button type="button" data-compare="${C.escape(source.url)}">Compare resume</button></div></section>`).join('')}</details>` : ''}
      <div class="cw-toolbar"><a class="cw-link" href="${C.escape(job.url)}" target="_blank" rel="noopener noreferrer">View source</a>
      <button type="button" data-track="${C.escape(job.url)}">${state.applications[job.url] ? 'Tracked' : 'Track application'}</button>
      <button type="button" data-compare="${C.escape(job.url)}">Compare resume</button></div></article>`;
  }
  function renderMatches() {
    const q = $('search').value.toLowerCase(), list = jobs();
    const filtered = list.filter(j => !$('hide-expired').checked || !C.freshness(j).expired)
      .filter(j => !q || [j.title, j.company, j.city, j.description].join(' ').toLowerCase().includes(q));
    const groups = $('group-duplicates').checked ? C.groupJobs(filtered) : filtered.map(job => ({ job, sources: [job] }));
    const ranked = groups.map(group => ({ ...group, result: C.match(group.job, state.preferences) }))
      .sort((a, b) => (b.result.score ?? 0) - (a.result.score ?? 0) || Number(C.freshness(a.job).stale) - Number(C.freshness(b.job).stale) || a.job.title.localeCompare(b.job.title));
    const shown = Number($('matches').dataset.limit || 12);
    $('matches').innerHTML = ranked.slice(0, shown).map(({ job, result, sources }) => card(job, result, sources)).join('') || '<p>No matching opportunities in the loaded feed. Your tracker is still available below.</p>';
    $('match-count').textContent = `${ranked.length} cards from ${filtered.length} matching source links · Showing ${Math.min(shown, ranked.length)}. Scores reflect stated information, not hiring likelihood.`;
    $('more').hidden = ranked.length <= shown;
  }
  function renderTracker() {
    const selected = $('tracker-filter').value;
    const parts = new Intl.DateTimeFormat('en', {timeZone: state.alerts.timezone, year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(new Date());
    const part = type => parts.find(p => p.type === type).value;
    const today = `${part('year')}-${part('month')}-${part('day')}`;
    const entries = Object.entries(state.applications).filter(([, a]) => !selected || a.status === selected).sort(([, a], [, b]) => (a.followUp || '9999').localeCompare(b.followUp || '9999'));
    $('tracker').innerHTML = entries.map(([key, a]) => `<form class="cw-card" data-application="${C.escape(key)}"><h3>${C.escape(a.job.title)}</h3><p>${C.escape(a.job.company)}</p>
      ${a.followUp && a.followUp <= today && a.status !== 'Rejected' ? '<p class="cw-warning">Follow-up due: ' + C.escape(a.followUp) + '</p>' : ''}
      ${warnings(a.job)}
      <p class="cw-muted">${C.escape(C.freshness(a.job).label)} · Saved independently of the feed.</p>
      <label>Status<select name="status" aria-label="Status for ${C.escape(a.job.title)}">${C.STATUSES.map(s => `<option ${a.status === s ? 'selected' : ''}>${s}</option>`).join('')}</select></label>
      <label>Notes<textarea name="notes" maxlength="5000" rows="3">${C.escape(a.notes)}</textarea></label>
      <label>Follow-up date<input name="followUp" type="date" value="${C.escape(a.followUp)}"></label>
      <div class="cw-toolbar"><button type="submit">Save changes</button><button type="button" data-calendar="${C.escape(key)}" ${a.followUp ? '' : 'disabled'}>Add reminder to calendar</button>
      <a class="cw-link" href="${C.escape(a.job.url)}" target="_blank" rel="noopener noreferrer">Job link</a></div></form>`).join('') || '<p>No applications in this stage. Track an opportunity above to get started.</p>';
    $('tracker-count').textContent = C.STATUSES.map(s => `${s}: ${Object.values(state.applications).filter(a => a.status === s).length}`).join(' · ');
  }
  async function track(value) {
    const job = jobs().find(j => j.url === C.url(value) || j.id === value);
    if (!job) { notice('This opportunity has no valid application link.'); return; }
    if (state.applications[job.url]) { notice('Already in your application tracker.'); return; }
    const next = clone(state);
    next.applications[job.url] = { job, status: 'Saved', notes: '', followUp: '', updatedAt: new Date().toISOString() };
    if (await save(next)) { renderMatches(); renderTracker(); }
  }
  async function syncBookmarks() {
    if (options.server || !options.getSavedJobs) return;
    const next = clone(state); let added = false;
    for (const raw of options.getSavedJobs()) {
      const job = C.normalize(raw);
      if (job.url && !next.applications[job.url]) {
        next.applications[job.url] = {job, status:'Saved', notes:'', followUp:'', updatedAt:new Date().toISOString()};
        added = true;
      }
    }
    if (added && await save(next)) renderTracker();
  }
  function compare() {
    const result = C.compareResume($('resume').value, $('description').value, state.preferences.skills);
    $('comparison').innerHTML = `<h3>${result.score === null ? 'No recognized skills in this description' : result.score + '% keyword coverage'}</h3>
      <p>Found in both: ${C.escape(result.matched.join(', ') || 'None')}</p><p>Not found in resume: ${C.escape(result.missing.join(', ') || 'None')}</p>
      <ul>${result.suggestions.map(s => '<li>' + C.escape(s) + '</li>').join('')}</ul><p class="cw-muted">Keyword comparison cannot verify proficiency. Never add experience or qualifications you do not have. Resume text stays in this tab and is not uploaded or saved.</p>`;
  }
  function calendar(key) {
    const a = state.applications[key]; if (!a?.followUp) return;
    const escapeIcs = v => v.replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');
    const day = a.followUp.replaceAll('-', '');
    const data = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//MyJob//Career Workspace//EN', 'BEGIN:VEVENT', 'UID:' + crypto.randomUUID() + '@myjob', 'DTSTAMP:' + new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z/, 'Z'), 'DTSTART;VALUE=DATE:' + day, 'SUMMARY:' + escapeIcs('Follow up: ' + a.job.title).slice(0, 200), 'DESCRIPTION:' + escapeIcs(a.job.company + '\n' + a.job.url), 'END:VEVENT', 'END:VCALENDAR', ''].join('\r\n');
    backup('job-follow-up.ics', data, 'text/calendar');
  }
  async function health() {
    $('health').textContent = 'Checking status…';
    if (!options.server) {
      const list = jobs(), checked = list.map(j => C.date(j.verifiedAt)).filter(Boolean).sort((a, b) => b - a)[0];
      $('health').textContent = `${navigator.onLine ? 'Device online' : 'Device offline'} · ${list.length} jobs loaded · Latest recorded link check: ${checked ? checked.toLocaleString() : 'unavailable'}. Provider checks and notification history are available in the private dashboard.`;
      return;
    }
    try {
      const response = await fetch('/api/career/health'); if (!response.ok) throw new Error('Dashboard session unavailable.');
      const data = await response.json();
      $('health').innerHTML = data.checks.map(c => `<article class="cw-card"><h3>${C.escape(c.name)}: ${C.escape(c.status)}</h3><p>${C.escape(c.detail)}</p></article>`).join('');
    } catch (e) { $('health').textContent = e.message; }
  }
  async function mount(config) {
    if (host) return;
    options = config;
    host = document.createElement('section'); host.className = 'career-workspace'; host.setAttribute('aria-label', 'Career workspace');
    (config.anchor || document.querySelector('header') || document.body.firstElementChild).after(host);
    host.innerHTML = `<details ${config.offline ? 'open' : ''}><summary>My career workspace <span class="cw-pill">Matches · Applications · Resume</span></summary>
      <p class="cw-muted">${config.server ? 'Private dashboard: preferences and applications are stored on your server.' : 'Your preferences and applications stay on this device. Saved bookmarks are copied into the tracker for offline access; removing a bookmark keeps its application history. Export a backup to move to your private dashboard or another device.'}</p>
      <p id="cw-status" class="cw-status" role="status" aria-live="polite"></p>
      <div class="cw-toolbar"><button type="button" id="cw-export">Export backup</button><label>Import backup<input id="cw-import" type="file" accept="application/json,.json"></label><button type="button" id="cw-install" hidden>Install app</button></div>
      <p id="cw-install-help" class="cw-muted"></p>
      <form id="cw-preferences"><h2>Personalize your matches</h2><div class="cw-grid">
        <label>Skills (comma separated)<input id="cw-skills" maxlength="2000" placeholder="Python, SQL, React"></label><label>Preferred cities (comma separated)<input id="cw-cities" maxlength="1000" placeholder="Chennai, Vellore, Puducherry"></label>
        <label>Years of experience<input id="cw-experience" type="number" min="0" max="60" step="0.5" placeholder="Not specified"></label><label>Minimum annual salary (LPA)<input id="cw-salary" type="number" min="0" max="1000" step="0.1" placeholder="Not specified"></label></div>
        <label><input id="cw-remote" type="checkbox">Prefer remote work</label><button type="submit">Save preferences</button></form>
      <section class="cw-section"><h2>Recommended opportunities</h2><label>Search loaded jobs<input id="cw-search" type="search" placeholder="Role, employer or city"></label><label><input id="cw-hide-expired" type="checkbox" checked>Hide confirmed expired listings</label><label><input id="cw-group-duplicates" type="checkbox" checked>Group possible duplicates</label>
      <p id="cw-match-count" class="cw-muted"></p><div id="cw-matches" class="cw-grid"></div><button id="cw-more" type="button">Show more recommendations</button></section>
      <section class="cw-section"><h2>Application tracker</h2><p id="cw-tracker-count" class="cw-muted"></p><label>Filter stage<select id="cw-tracker-filter"><option value="">All stages</option>${C.STATUSES.map(s => '<option>' + s + '</option>').join('')}</select></label><div id="cw-tracker" class="cw-grid"></div></section>
      <form id="cw-resume-form" class="cw-section"><h2>Resume-to-job comparison</h2><div class="cw-grid"><label>Resume text<textarea id="cw-resume" rows="6" maxlength="40000" required></textarea></label><label>Job description<textarea id="cw-description" rows="6" maxlength="40000" required></textarea></label></div><button type="submit">Compare skills</button><div id="cw-comparison" aria-live="polite"></div></form>
      <form id="cw-alerts" class="cw-section"><h2>Daily career digest and follow-ups</h2><p class="cw-muted">${config.server ? 'Delivered by this running bot to its authorized Telegram chat. These controls apply to career digests and tracker reminders; existing radar/channel campaigns have their own settings.' : 'Save these settings here, then export/import this backup into your authenticated dashboard to activate Telegram delivery. On this device, due follow-ups appear in the tracker; calendar reminders work offline.'}</p>
      <label><input id="cw-enabled" type="checkbox">Enable daily matched-job digest</label><label><input id="cw-followupsEnabled" type="checkbox">Enable Telegram follow-up reminders</label>
      <div class="cw-grid"><label>Digest time<input id="cw-time" type="time" required></label><label>Timezone<input id="cw-timezone" required placeholder="Asia/Kolkata"></label><label>Quiet hours start<input id="cw-quietStart" type="time" required></label><label>Quiet hours end<input id="cw-quietEnd" type="time" required></label><label>Minimum match score (0–100)<input id="cw-minScore" type="number" min="0" max="100" required></label><label>Maximum listing age (days)<input id="cw-maxAgeDays" type="number" min="1" max="90" required></label></div>
      <p class="cw-muted">Equal quiet-hour times disable quiet hours. A digest due during quiet hours waits until they end. No alerts are sent for confirmed expired or undated/unverified listings.</p><button type="submit">Save alert settings</button></form>
      <section class="cw-section"><h2>Integration and feed health</h2><button id="cw-check-health" type="button">Refresh status</button>${config.server ? '<button id="cw-ai-check" type="button">Check AI connections (uses provider quota)</button>' : ''}<div id="cw-health" class="cw-grid"></div></section></details>`;
    try {
      if (config.server) { const response = await fetch('/api/career/state'); if (!response.ok) throw new Error('Could not load server workspace. Reload after signing in.'); const data = await response.json(); state = C.cleanState(data.state); revision = data.revision; }
      else { const raw = localStorage.getItem(KEY); if (raw) state = C.cleanState(JSON.parse(raw)); }
    } catch (e) { notice(e.message + (config.server ? '' : ' Export a backup before closing if storage is unavailable.')); if (config.server) { host.querySelectorAll('button,input,textarea,select').forEach(e => { e.disabled = true; }); return; } }
    await syncBookmarks();
    populate(); renderMatches(); renderTracker(); health();
    $('preferences').addEventListener('submit', async event => { event.preventDefault(); const next = clone(state); next.preferences = { skills: C.terms($('skills').value), cities: C.terms($('cities').value), experience: $('experience').value === '' ? null : Number($('experience').value), minSalary: $('salary').value === '' ? null : Number($('salary').value), remote: $('remote').checked }; if (await save(next)) renderMatches(); });
    $('alerts').addEventListener('submit', async event => { event.preventDefault(); const next = clone(state); for (const k of ['time', 'timezone', 'quietStart', 'quietEnd']) next.alerts[k] = $(k).value; for (const k of ['enabled', 'followupsEnabled']) next.alerts[k] = $(k).checked; for (const k of ['minScore', 'maxAgeDays']) next.alerts[k] = Number($(k).value); await save(next); });
    $('tracker').addEventListener('submit', async event => { event.preventDefault(); const form = event.target, key = form.dataset.application; if (!key) return; const next = clone(state); Object.assign(next.applications[key], { status: form.elements.status.value, notes: form.elements.notes.value, followUp: form.elements.followUp.value, updatedAt: new Date().toISOString() }); if (await save(next)) renderTracker(); });
    host.addEventListener('click', event => { const target = event.target.closest('button'); if (!target) return; if (target.dataset.track) track(target.dataset.track); if (target.dataset.calendar) calendar(target.dataset.calendar); if (target.dataset.compare) { const j = jobs().find(j => j.url === target.dataset.compare); if (j) { $('description').value = [j.title, j.description, j.skills.join(', ')].join('\n'); $('resume').focus(); } } });
    $('search').addEventListener('input', renderMatches); $('hide-expired').addEventListener('change', renderMatches); $('tracker-filter').addEventListener('change', renderTracker); $('group-duplicates').addEventListener('change', renderMatches);
    $('more').addEventListener('click', () => { $('matches').dataset.limit = Number($('matches').dataset.limit || 12) + 12; renderMatches(); });
    $('resume-form').addEventListener('submit', event => { event.preventDefault(); compare(); });
    $('export').addEventListener('click', () => backup('myjob-career-backup.json', JSON.stringify(state, null, 2)));
    $('import').addEventListener('change', async () => { try { const file = $('import').files[0]; if (!file) return; if (file.size > 2000000) throw new Error('Backup must be smaller than 2 MB.'); const imported = C.cleanState(JSON.parse(await file.text())); imported.applications = { ...state.applications, ...imported.applications }; if (await save(imported)) { populate(); renderMatches(); renderTracker(); notice('Imported preferences and merged applications by job URL.'); } } catch (e) { notice(e.message); } finally { $('import').value = ''; } });
    $('check-health').addEventListener('click', health);
    if (config.server) $('ai-check').addEventListener('click', async () => {
      $('ai-check').disabled = true;
      try { const r = await fetch('/api/health_check'); if (!r.ok) throw new Error('Could not run provider checks.'); await health(); }
      catch (error) { notice(error.message); }
      finally { $('ai-check').disabled = false; }
    });
    window.addEventListener('online', health); window.addEventListener('offline', health);
    window.addEventListener('career:jobs', () => { renderMatches(); syncBookmarks(); });
    if (installEvent) $('install').hidden = false;
    $('install').addEventListener('click', async () => { if (!installEvent) return; await installEvent.prompt(); installEvent = null; $('install').hidden = true; });
    if (!config.server) $('install-help').textContent = 'Install from your browser menu (Add to Home Screen on iPhone). Offline access is ready after the app downloads once; saved applications remain on this device.';
    if (config.pwa && 'serviceWorker' in navigator) { navigator.serviceWorker.register('./sw.js').then(() => navigator.serviceWorker.ready).then(() => { $('install-help').textContent += ' Offline shell ready.'; }).catch(() => { $('install-help').textContent = 'Offline setup failed. Reload online to retry; device storage and backup export still work.'; }); }
  }
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installEvent = event; if (host) $('install').hidden = false; });
  window.CareerWorkspace = { mount, track, syncBookmarks, refresh: () => { if (host) renderMatches(); } };
})();
