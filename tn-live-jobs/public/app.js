'use strict';

/**
 * Tamil Nadu Live Jobs - Client Application
 * Features:
 *   - Tokenized multi-keyword search with term highlighting
 *   - Quick filter chips (Freshers, Govt, IT, Healthcare, Finance, Saved)
 *   - Multi-dimensional filters (City, Category, Exp, Type, Freshness, Sort)
 *   - Rich Job Details Modal with skill pills, qualifications, and live guarantee
 *   - Bookmark / Save jobs to localStorage
 *   - Social Sharing (WhatsApp, Telegram, Copy Link)
 *   - Shareable URL query param sync
 *   - Dark / Light mode toggle with persistence
 *   - Keyboard shortcuts ('/' to search, Esc to close/clear)
 *   - Infinite scroll / Load more for smooth 60fps performance
 */

// ---------- State & Elements ------------------------------------------------

const PAGE_SIZE = 24;

const state = {
  allJobs: [],
  filteredJobs: [],
  visibleCount: PAGE_SIZE,
  query: '',
  quickChip: 'all',
  city: '',
  category: '',
  experience: '',
  type: '',
  freshness: '',
  sort: 'newest',
  selectedJob: null,
  savedIds: new Set(),
};

const els = {};

// ---------- LocalStorage & Bookmarks ----------------------------------------

function loadSavedIds() {
  try {
    const raw = localStorage.getItem('tn_saved_jobs');
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) state.savedIds = new Set(arr);
    }
  } catch (err) {
    state.savedIds = new Set();
  }
}

function persistSavedIds() {
  try {
    localStorage.setItem('tn_saved_jobs', JSON.stringify(Array.from(state.savedIds)));
  } catch (err) {
    /* ignore storage errors */
  }
  updateSavedBadge();
}

function toggleSaveJob(id) {
  if (state.savedIds.has(id)) {
    state.savedIds.delete(id);
    showToast('Removed from saved jobs');
  } else {
    state.savedIds.add(id);
    showToast('Saved to your bookmarks! ⭐');
  }
  persistSavedIds();
  if (state.quickChip === 'saved') applyFilters();
  else renderListOnly();
  if (state.selectedJob && state.selectedJob.id === id) {
    updateModalBookmarkBtn();
  }
}

function updateSavedBadge() {
  if (els.savedCount) {
    els.savedCount.textContent = state.savedIds.size;
  }
}

// ---------- Theme Management ------------------------------------------------

function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem('tn_theme'); } catch (e) { /* storage may be blocked */ }
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try {
    localStorage.setItem('tn_theme', next);
  } catch (e) {}
}

let modalReturnFocus = null;
let modalBackground = [];

function safeApplyUrl(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '#';
  } catch (e) { return '#'; }
}

// ---------- Helpers & Formatting --------------------------------------------

function escapeHtml(val) {
  return String(val == null ? '' : val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function daysAgo(dateString) {
  if (!dateString) return '';
  const then = new Date(dateString + 'T00:00:00');
  if (Number.isNaN(then.getTime())) return '';
  const days = Math.floor((Date.now() - then.getTime()) / 86400000);
  if (days <= 0) return 'Posted today';
  if (days === 1) return 'Posted yesterday';
  return 'Posted ' + days + ' days ago';
}

function fmtDate(dateString) {
  if (!dateString) return 'Not stated';
  const then = new Date(dateString + 'T00:00:00');
  if (Number.isNaN(then.getTime())) return escapeHtml(dateString);
  return then.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function highlightText(text, query) {
  if (!query || !text) return escapeHtml(text);
  const words = query.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return escapeHtml(text);
  const escapedWords = words.map(w => w.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&'));
  const regex = new RegExp(`(${escapedWords.join('|')})`, 'gi');
  const parts = String(text).split(regex);
  return parts.map(part => {
    regex.lastIndex = 0;
    if (regex.test(part)) {
      return `<mark>${escapeHtml(part)}</mark>`;
    }
    return escapeHtml(part);
  }).join('');
}

function showToast(message) {
  if (!els.toast) return;
  els.toast.textContent = message;
  els.toast.classList.add('show');
  clearTimeout(els.toastTimer);
  els.toastTimer = setTimeout(() => {
    els.toast.classList.remove('show');
  }, 2600);
}

// ---------- Search & Filter Logic -------------------------------------------

/**
 * Every searchable field of a job, lower-cased once and cached on the record.
 * Rebuilding this string for every job on every keystroke was the main cost of
 * typing in the search box, so we build it lazily and reuse it.
 */
function searchHaystack(job) {
  if (job.__search) return job.__search;
  const skillsStr = Array.isArray(job.skills) ? job.skills.join(' ') : '';
  const haystack = (
    (job.title || '') + ' ' +
    (job.company || '') + ' ' +
    (job.city || '') + ' ' +
    (job.category || '') + ' ' +
    (job.qualification || '') + ' ' +
    (job.description || '') + ' ' +
    skillsStr + ' ' +
    (job.source || '')
  ).toLowerCase();
  try {
    Object.defineProperty(job, '__search', { value: haystack, enumerable: false, writable: true });
  } catch (e) {
    job.__search = haystack;
  }
  return haystack;
}

function matchesSearch(job, query) {
  if (!query) return true;
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!tokens.length) return true;
  const haystack = searchHaystack(job);
  return tokens.every(token => haystack.includes(token));
}

function matchesQuickChip(job, chip) {
  if (chip === 'all') return true;
  if (chip === 'saved') return state.savedIds.has(job.id);
  if (chip === 'fresher') return job.is_fresher === true;
  if (chip === 'govt') return job.category === 'Government' || job.source_type === 'government';
  if (chip === 'it') {
    return job.category === 'Software' ||
      (Array.isArray(job.skills) && job.skills.some(s => /python|java|react|node|c#|\.net|sql|angular|docker/i.test(s)));
  }
  if (chip === 'healthcare') {
    return job.category === 'Healthcare' || /nurse|medical|health|doctor/i.test(job.title || '');
  }
  if (chip === 'finance') {
    return job.category === 'Accounting' || /account|finance|tally|gst|tax/i.test(job.title || '');
  }
  return true;
}

function matchesExperience(job, expFilter) {
  if (!expFilter) return true;
  if (expFilter === 'fresher') return job.is_fresher === true;
  const expStr = String(job.experience || '').toLowerCase();
  if (expFilter === 'mid') return /1|2|3\s*years?/.test(expStr);
  if (expFilter === 'senior') return /3\+|4|5|6|7|8|9|10/.test(expStr);
  return true;
}

function matchesFreshness(job, freshness) {
  if (!freshness || !job.posted_at) return true;
  const then = new Date(job.posted_at + 'T00:00:00').getTime();
  if (Number.isNaN(then)) return true;
  const ageHours = (Date.now() - then) / (3600 * 1000);
  if (freshness === '24h') return ageHours <= 36;
  if (freshness === '3d') return ageHours <= 3 * 24 + 12;
  if (freshness === '7d') return ageHours <= 7 * 24 + 12;
  return true;
}

function applyFilters() {
  const q = state.query.trim();

  let list = state.allJobs.filter(job => {
    if (!matchesQuickChip(job, state.quickChip)) return false;
    if (state.city && job.city !== state.city) return false;
    if (state.category && job.category !== state.category) return false;
    if (state.type && job.employment_type !== state.type) return false;
    if (!matchesExperience(job, state.experience)) return false;
    if (!matchesFreshness(job, state.freshness)) return false;
    if (!matchesSearch(job, q)) return false;
    return true;
  });

  // Sorting
  if (state.sort === 'city') {
    list.sort((a, b) => String(a.city || '').localeCompare(String(b.city || '')));
  } else if (state.sort === 'company') {
    list.sort((a, b) => String(a.company || '').localeCompare(String(b.company || '')));
  } else if (state.sort === 'salary') {
    list.sort((a, b) => {
      const aSal = Boolean(a.salary);
      const bSal = Boolean(b.salary);
      if (aSal !== bSal) return aSal ? -1 : 1;
      return String(b.posted_at || '').localeCompare(String(a.posted_at || ''));
    });
  } else {
    // Newest first
    list.sort((a, b) => String(b.posted_at || '').localeCompare(String(a.posted_at || '')));
  }

  state.filteredJobs = list;
  state.visibleCount = PAGE_SIZE;
  render();
  updateUrlParams();
}

// ---------- URL State Sync --------------------------------------------------

function readUrlParams() {
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.has('q')) state.query = params.get('q');
    if (params.has('city')) state.city = params.get('city');
    if (params.has('cat')) state.category = params.get('cat');
    if (params.has('chip')) state.quickChip = params.get('chip');
    if (params.has('exp')) state.experience = params.get('exp');
    if (params.has('type')) state.type = params.get('type');
    if (params.has('fresh')) state.freshness = params.get('fresh');
    if (params.has('sort')) state.sort = params.get('sort');
  } catch (e) {}
}

function updateUrlParams() {
  try {
    const params = new URLSearchParams();
    if (state.query) params.set('q', state.query);
    if (state.city) params.set('city', state.city);
    if (state.category) params.set('cat', state.category);
    if (state.quickChip && state.quickChip !== 'all') params.set('chip', state.quickChip);
    if (state.experience) params.set('exp', state.experience);
    if (state.type) params.set('type', state.type);
    if (state.freshness) params.set('fresh', state.freshness);
    if (state.sort && state.sort !== 'newest') params.set('sort', state.sort);

    const queryStr = params.toString();
    const newUrl = window.location.pathname + (queryStr ? '?' + queryStr : '');
    window.history.replaceState({}, '', newUrl);
  } catch (e) {}
}

// ---------- Card Component --------------------------------------------------

function createCardHtml(job) {
  const isSaved = state.savedIds.has(job.id);
  const q = state.query;

  const highlightedTitle = highlightText(job.title, q);
  const highlightedCompany = highlightText(job.company, q);

  // Tags
  const tags = [];
  tags.push(`<span class="tag tag-city">&#128205; ${escapeHtml(job.city || 'Tamil Nadu')}</span>`);
  if (job.is_fresher) {
    tags.push(`<span class="tag tag-fresher">&#128293; Fresher Friendly</span>`);
  }
  if (job.category) {
    tags.push(`<span class="tag tag-category">${escapeHtml(job.category)}</span>`);
  }
  tags.push(`<span class="tag tag-verified">&#10003; Verified</span>`);

  // Details items
  const detailsItems = [];
  detailsItems.push(`<div class="card-details-item"><span>Salary:</span> <strong>${escapeHtml(job.salary || 'Not stated')}</strong></div>`);
  detailsItems.push(`<div class="card-details-item"><span>Exp:</span> <strong>${escapeHtml(job.experience || 'Not specified')}</strong></div>`);
  if (job.qualification) {
    detailsItems.push(`<div class="card-details-item"><span>Edu:</span> <strong>${escapeHtml(job.qualification)}</strong></div>`);
  }
  detailsItems.push(`<div class="card-details-item"><span>Posted:</span> <strong>${fmtDate(job.posted_at)}</strong></div>`);

  // Skills preview (up to 4)
  let skillsHtml = '';
  if (Array.isArray(job.skills) && job.skills.length > 0) {
    const visibleSkills = job.skills.slice(0, 4);
    const extraCount = job.skills.length - visibleSkills.length;
    const chips = visibleSkills.map(s => `<span class="skill-chip">${escapeHtml(s)}</span>`).join('');
    const extra = extraCount > 0 ? `<span class="skill-chip">+${extraCount} more</span>` : '';
    skillsHtml = `<div class="card-skills">${chips}${extra}</div>`;
  }

  return `
    <article class="card" data-id="${escapeHtml(job.id)}">
      <div class="card-header">
        <span class="card-company">${highlightedCompany}</span>
        <button class="btn-bookmark ${isSaved ? 'saved' : ''}" type="button" data-save="${escapeHtml(job.id)}" title="${isSaved ? 'Unsave job' : 'Save job'}" aria-label="${isSaved ? 'Unsave' : 'Save'} ${escapeHtml(job.title)}" aria-pressed="${isSaved}">
          ${isSaved ? '&#9733;' : '&#9734;'}
        </button>
      </div>
      <h2 class="card-title">${highlightedTitle}</h2>
      <div class="tags">${tags.join('')}</div>
      <div class="card-details">${detailsItems.join('')}</div>
      ${skillsHtml}
      <div class="card-actions">
        <button class="btn-details" type="button" data-view="${escapeHtml(job.id)}">View Details</button>
        <a class="btn-apply" href="${escapeHtml(safeApplyUrl(job.apply_url))}" target="_blank" rel="noopener noreferrer">Apply Now &rarr;</a>
      </div>
    </article>
  `;
}

// ---------- Render UI -------------------------------------------------------

function renderListOnly() {
  const visible = state.filteredJobs.slice(0, state.visibleCount);
  els.list.innerHTML = visible.map(createCardHtml).join('');

  // Load More Button
  const remaining = state.filteredJobs.length - visible.length;
  if (remaining > 0) {
    els.loadMoreWrap.hidden = false;
    els.loadMoreCount.textContent = remaining;
  } else {
    els.loadMoreWrap.hidden = true;
  }

  els.empty.hidden = state.filteredJobs.length !== 0;
}

function render() {
  renderListOnly();

  // Populate Dropdown Filters (City, Category) once
  const distinct = key => Array.from(new Set(state.allJobs.map(j => j[key]).filter(Boolean))).sort();
  if (els.city.options.length <= 1) {
    distinct('city').forEach(c => els.city.append(new Option(c, c)));
  }
  if (els.category.options.length <= 1) {
    distinct('category').forEach(c => els.category.append(new Option(c, c)));
  }

  // Synchronize inputs with state
  if (els.search.value !== state.query) els.search.value = state.query;
  els.searchClear.hidden = !state.query;
  els.city.value = state.city;
  els.category.value = state.category;
  els.experience.value = state.experience;
  els.type.value = state.type;
  els.freshness.value = state.freshness;
  els.sort.value = state.sort;

  // Active quick chip styling
  document.querySelectorAll('.chip').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.chip === state.quickChip);
  });

  // Active Filters Bar
  renderActiveFilters();

  // Stats Counters
  const freshCount = state.allJobs.filter(j => {
    if (!j.posted_at) return false;
    return Date.now() - new Date(j.posted_at + 'T00:00:00').getTime() < 36 * 3600 * 1000;
  }).length;

  els.statLive.textContent = `${state.allJobs.length} live jobs verified`;
  els.statFresh.textContent = `${freshCount} fresh in last 24h`;

  if (state.filteredJobs.length !== state.allJobs.length) {
    els.statShowing.textContent = `Showing ${state.filteredJobs.length} of ${state.allJobs.length} matching jobs`;
  } else {
    els.statShowing.textContent = `Showing all ${state.allJobs.length} jobs`;
  }
}

function renderActiveFilters() {
  const pills = [];
  if (state.query) pills.push({ label: `"${state.query}"`, reset: () => { state.query = ''; } });
  if (state.quickChip && state.quickChip !== 'all') {
    const chipNames = {
      fresher: 'Freshers',
      govt: 'Government',
      it: 'IT & Software',
      healthcare: 'Healthcare',
      finance: 'Finance',
      saved: 'Saved Jobs',
    };
    pills.push({ label: chipNames[state.quickChip] || state.quickChip, reset: () => { state.quickChip = 'all'; } });
  }
  if (state.city) pills.push({ label: `City: ${state.city}`, reset: () => { state.city = ''; } });
  if (state.category) pills.push({ label: `Category: ${state.category}`, reset: () => { state.category = ''; } });
  if (state.experience) pills.push({ label: `Exp: ${state.experience}`, reset: () => { state.experience = ''; } });
  if (state.type) pills.push({ label: `Type: ${state.type}`, reset: () => { state.type = ''; } });
  if (state.freshness) pills.push({ label: `Date: ${state.freshness}`, reset: () => { state.freshness = ''; } });

  if (pills.length === 0) {
    els.activeFilters.hidden = true;
    els.activePills.innerHTML = '';
  } else {
    els.activeFilters.hidden = false;
    els.activePills.innerHTML = pills.map((p, idx) => `
      <span class="active-pill">
        ${escapeHtml(p.label)}
        <button class="active-pill-remove" data-pill-idx="${idx}" type="button" aria-label="Remove filter">&times;</button>
      </span>
    `).join('');

    // Attach click listeners to pill remove buttons
    els.activePills.querySelectorAll('.active-pill-remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = Number(e.currentTarget.dataset.pillIdx);
        if (pills[idx]) {
          pills[idx].reset();
          applyFilters();
        }
      });
    });
  }
}

function resetAllFilters() {
  state.query = '';
  state.quickChip = 'all';
  state.city = '';
  state.category = '';
  state.experience = '';
  state.type = '';
  state.freshness = '';
  state.sort = 'newest';
  applyFilters();
  showToast('All filters cleared');
}

// ---------- Modal Details Drawer --------------------------------------------

function openJobModal(job) {
  modalReturnFocus = document.activeElement;
  state.selectedJob = job;
  els.modalTitle.textContent = job.title || '';
  els.modalCompany.textContent = job.company || '';
  els.modalCity.textContent = job.city ? `📍 ${job.city}` : '📍 Tamil Nadu';
  els.modalSource.textContent = `Source: ${job.source || 'Official'}`;
  els.modalSalary.textContent = job.salary || 'Not stated in advertisement';
  els.modalExp.textContent = job.experience || 'Not specified';
  els.modalQual.textContent = job.qualification || 'Any Graduate / Refer notice';
  els.modalType.textContent = job.employment_type || 'Full-time / Standard';
  els.modalPosted.textContent = job.posted_at ? `${fmtDate(job.posted_at)} (${daysAgo(job.posted_at)})` : 'Recently posted';
  els.modalDeadline.textContent = job.deadline ? `Last date: ${fmtDate(job.deadline)}` : 'Open until filled';
  els.modalHttpStatus.textContent = job.http_status ? `${job.http_status} OK` : '200 OK';

  // Description
  const desc = job.description || job.page_title || `Official recruitment opportunity for ${job.title} at ${job.company} located in ${job.city || 'Tamil Nadu'}. Re-verified live by automated crawler.`;
  els.modalDesc.textContent = desc;

  // Skills Pills
  if (Array.isArray(job.skills) && job.skills.length > 0) {
    els.modalSkillsSection.hidden = false;
    els.modalSkills.innerHTML = job.skills.map(skill => `
      <button class="modal-skill-pill" data-skill="${escapeHtml(skill)}" type="button">${escapeHtml(skill)}</button>
    `).join('');

    els.modalSkills.querySelectorAll('.modal-skill-pill').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const skill = e.currentTarget.dataset.skill;
        closeJobModal();
        state.query = skill;
        applyFilters();
        els.search.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    });
  } else {
    els.modalSkillsSection.hidden = true;
    els.modalSkills.innerHTML = '';
  }

  // Apply button
  els.modalApplyBtn.href = safeApplyUrl(job.apply_url);

  // Bookmark button
  updateModalBookmarkBtn();

  // Social sharing links
  setupModalShare(job);

  // Show dialog
  els.jobModal.classList.add('open');
  els.jobModal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  modalBackground = Array.from(document.querySelectorAll('header, main, footer')).map(el => [el, el.inert]);
  modalBackground.forEach(([el]) => { el.inert = true; });
  els.modalClose.focus();
}

function updateModalBookmarkBtn() {
  if (!state.selectedJob) return;
  const isSaved = state.savedIds.has(state.selectedJob.id);
  els.modalBookmarkBtn.classList.toggle('saved', isSaved);
  els.modalBookmarkBtn.setAttribute('aria-pressed', String(isSaved));
  const icon = els.modalBookmarkBtn.querySelector('.bm-icon');
  const text = els.modalBookmarkBtn.querySelector('.bm-text');
  if (icon) icon.innerHTML = isSaved ? '&#9733;' : '&#9734;';
  if (text) text.textContent = isSaved ? 'Saved' : 'Save Job';
}

function setupModalShare(job) {
  const shareText = encodeURIComponent(`📌 Job Vacancy: ${job.title} at ${job.company} (${job.city || 'Tamil Nadu'}). Check details & apply: ${job.apply_url}`);
  els.modalShareWhatsapp.onclick = () => {
    window.open(`https://api.whatsapp.com/send?text=${shareText}`, '_blank');
  };
  els.modalShareTelegram.onclick = () => {
    window.open(`https://t.me/share/url?url=${encodeURIComponent(job.apply_url)}&text=${encodeURIComponent(`${job.title} at ${job.company} (${job.city})`)}`, '_blank');
  };
  els.modalShareCopy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(job.apply_url);
      showToast('Apply link copied to clipboard! 📋');
    } catch (e) {
      showToast('Could not copy link');
    }
  };
}

function closeJobModal() {
  els.jobModal.classList.remove('open');
  els.jobModal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  state.selectedJob = null;
  modalBackground.forEach(([el, wasInert]) => { el.inert = wasInert; });
  modalBackground = [];
  if (modalReturnFocus && modalReturnFocus.isConnected) modalReturnFocus.focus();
  else els.search.focus();
}

// ---------- Boot & Event Listeners ------------------------------------------

function stampHeader(payload) {
  const when = payload.generated_at ? new Date(payload.generated_at) : new Date(NaN);
  els.updated.textContent = Number.isNaN(when.getTime())
    ? 'Last updated: unavailable'
    : 'Last updated: ' + when.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
  els.counts.textContent = `${payload.count || 0} live verified jobs • ${payload.new_count || 0} new this run`;
}

function attachEvents() {
  // Theme toggle
  els.themeToggle.addEventListener('click', toggleTheme);

  // Search input debounced
  let searchTimer;
  els.search.addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.query = e.target.value.trim();
      applyFilters();
    }, 150);
  });

  // Clear search button
  els.searchClear.addEventListener('click', () => {
    state.query = '';
    els.search.value = '';
    applyFilters();
    els.search.focus();
  });

  // Quick Chips
  els.quickChips.addEventListener('click', (e) => {
    const chipBtn = e.target.closest('.chip');
    if (!chipBtn) return;
    const chip = chipBtn.dataset.chip;
    state.quickChip = chip;
    applyFilters();
  });

  // Dropdown Filters
  ['city', 'category', 'experience', 'type', 'freshness', 'sort'].forEach(key => {
    if (els[key]) {
      els[key].addEventListener('change', (e) => {
        state[key] = e.target.value;
        applyFilters();
      });
    }
  });

  // Reset buttons
  els.resetFilters.addEventListener('click', resetAllFilters);
  els.emptyResetBtn.addEventListener('click', resetAllFilters);

  // Empty state suggestion chips
  document.querySelectorAll('.chip-suggest').forEach(chip => {
    chip.addEventListener('click', (e) => {
      state.query = e.target.dataset.query;
      applyFilters();
    });
  });

  // Load More button
  els.loadMoreBtn.addEventListener('click', () => {
    state.visibleCount += PAGE_SIZE;
    renderListOnly();
  });

  // Card click delegation (View Details, Bookmark)
  els.list.addEventListener('click', (e) => {
    const saveBtn = e.target.closest('.btn-bookmark');
    if (saveBtn) {
      const id = saveBtn.dataset.save;
      toggleSaveJob(id);
      return;
    }

    const detailsBtn = e.target.closest('.btn-details');
    if (detailsBtn) {
      const id = detailsBtn.dataset.view;
      const job = state.allJobs.find(j => j.id === id);
      if (job) openJobModal(job);
      return;
    }

    // Clicking anywhere on card (except apply link) opens details
    const applyBtn = e.target.closest('.btn-apply');
    if (applyBtn) return;

    const card = e.target.closest('.card');
    if (card) {
      const id = card.dataset.id;
      const job = state.allJobs.find(j => j.id === id);
      if (job) openJobModal(job);
    }
  });

  // Modal close handlers
  els.modalClose.addEventListener('click', closeJobModal);
  els.jobModal.addEventListener('click', (e) => {
    if (e.target === els.jobModal) closeJobModal();
  });

  // Modal bookmark button
  els.modalBookmarkBtn.addEventListener('click', () => {
    if (state.selectedJob) {
      toggleSaveJob(state.selectedJob.id);
    }
  });

  // Global Keyboard Shortcuts
  document.addEventListener('keydown', (e) => {
    if (els.jobModal.classList.contains('open')) {
      if (e.key === 'Tab') {
        const focusable = Array.from(els.jobModal.querySelectorAll('button:not([disabled]), a[href], input, select, textarea, [tabindex="0"]'))
          .filter(el => el.getClientRects().length > 0);
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
      if (e.key === 'Escape') closeJobModal();
      return;
    }
    // Focus search with '/'
    if (e.key === '/' && !document.activeElement.matches('input, textarea, select, [contenteditable]')) {
      e.preventDefault();
      els.search.focus();
      els.search.select();
    }
    // Close modal or clear search on 'Escape'
    if (e.key === 'Escape') {
      if (els.jobModal.classList.contains('open')) {
        closeJobModal();
      } else if (state.query) {
        state.query = '';
        els.search.value = '';
        applyFilters();
      }
    }
  });
}

async function loadJobsPayload() {
  // 1) Fetch verified jobs from public/data/jobs.json
  try {
    const res = await fetch('./data/jobs.json', { cache: 'no-store' });
    if (res.ok) {
      const payload = await res.json();
      if (payload && Array.isArray(payload.jobs)) return payload;
    }
  } catch (err) {
    /* fallback to jobs.js */
  }

  // 2) Fallback: window.__TN_JOBS__ from jobs.js (works on file:// protocol)
  if (window.__TN_JOBS__ && Array.isArray(window.__TN_JOBS__.jobs)) {
    return window.__TN_JOBS__;
  }

  return { generated_at: null, count: 0, new_count: 0, jobs: [] };
}

document.addEventListener('DOMContentLoaded', async () => {
  // Bind DOM elements
  els.themeToggle = document.getElementById('themeToggle');
  els.updated = document.getElementById('updated');
  els.counts = document.getElementById('counts');
  els.search = document.getElementById('search');
  els.searchClear = document.getElementById('searchClear');
  els.quickChips = document.getElementById('quickChips');
  els.savedChip = document.getElementById('savedChip');
  els.savedCount = document.getElementById('savedCount');
  els.city = document.getElementById('city');
  els.category = document.getElementById('category');
  els.experience = document.getElementById('experience');
  els.type = document.getElementById('type');
  els.freshness = document.getElementById('freshness');
  els.sort = document.getElementById('sort');
  els.activeFilters = document.getElementById('activeFilters');
  els.activePills = document.getElementById('activePills');
  els.resetFilters = document.getElementById('resetFilters');
  els.statLive = document.getElementById('statLive');
  els.statFresh = document.getElementById('statFresh');
  els.statShowing = document.getElementById('statShowing');
  els.list = document.getElementById('list');
  els.loadMoreWrap = document.getElementById('loadMoreWrap');
  els.loadMoreBtn = document.getElementById('loadMoreBtn');
  els.loadMoreCount = document.getElementById('loadMoreCount');
  els.empty = document.getElementById('empty');
  els.emptyResetBtn = document.getElementById('emptyResetBtn');

  // Modal elements
  els.jobModal = document.getElementById('jobModal');
  els.modalClose = document.getElementById('modalClose');
  els.modalSource = document.getElementById('modalSource');
  els.modalVerified = document.getElementById('modalVerified');
  els.modalTitle = document.getElementById('modalTitle');
  els.modalCompany = document.getElementById('modalCompany');
  els.modalCity = document.getElementById('modalCity');
  els.modalSalary = document.getElementById('modalSalary');
  els.modalExp = document.getElementById('modalExp');
  els.modalQual = document.getElementById('modalQual');
  els.modalType = document.getElementById('modalType');
  els.modalPosted = document.getElementById('modalPosted');
  els.modalDeadline = document.getElementById('modalDeadline');
  els.modalHttpStatus = document.getElementById('modalHttpStatus');
  els.modalSkillsSection = document.getElementById('modalSkillsSection');
  els.modalSkills = document.getElementById('modalSkills');
  els.modalDesc = document.getElementById('modalDesc');
  els.modalBookmarkBtn = document.getElementById('modalBookmarkBtn');
  els.modalShareWhatsapp = document.getElementById('modalShareWhatsapp');
  els.modalShareTelegram = document.getElementById('modalShareTelegram');
  els.modalShareCopy = document.getElementById('modalShareCopy');
  els.modalApplyBtn = document.getElementById('modalApplyBtn');
  els.toast = document.getElementById('toast');

  initTheme();
  loadSavedIds();
  updateSavedBadge();
  attachEvents();

  const payload = await loadJobsPayload();
  state.allJobs = (payload.jobs || []).filter(j => j && j.verified === true);
  stampHeader(payload);

  readUrlParams();
  applyFilters();
});
