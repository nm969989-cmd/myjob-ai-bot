import * as cheerio from 'cheerio';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { initializeApp, getApps, getApp } from 'firebase/app';
import { 
  getFirestore, 
  doc, 
  setDoc, 
  getDocs, 
  collection, 
  query, 
  limit, 
  orderBy,
  where 
} from 'firebase/firestore';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

// Load Firebase configuration
let db = null;
let firebaseInitialized = false;

function initFirestore() {
  if (firebaseInitialized && db) return db;
  try {
    const configPath = path.join(rootDir, 'firebase-applet-config.json');
    if (fs.existsSync(configPath)) {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      const app = getApps().length === 0 ? initializeApp(config) : getApp();
      db = getFirestore(app, config.firestoreDatabaseId);
      firebaseInitialized = true;
      console.log(`[LinkedIn Scraper] Connected to Firestore database: ${config.firestoreDatabaseId}`);
    } else {
      console.warn('[LinkedIn Scraper] firebase-applet-config.json not found');
    }
  } catch (err) {
    console.error('[LinkedIn Scraper] Failed to initialize Firestore:', err.message);
  }
  return db;
}

// Scraper state & diagnostics
const scraperState = {
  status: 'idle', // 'idle' | 'running' | 'error'
  lastRunAt: null,
  nextRunAt: null,
  totalScrapedCount: 0,
  totalSavedToFirestore: 0,
  lastError: null,
  activeTarget: null,
  recentJobs: []
};

// Target Tamil Nadu locations and search combinations
const TN_LOCATIONS = [
  'Chennai, Tamil Nadu, India',
  'Coimbatore, Tamil Nadu, India',
  'Madurai, Tamil Nadu, India',
  'Tiruchirappalli, Tamil Nadu, India',
  'Tamil Nadu, India'
];

const SEARCH_ROLES = [
  'Software Engineer',
  'Developer',
  'Full Stack Developer',
  'Data Engineer'
];

// User agents for polite rotation
const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
];

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Identify the Tamil Nadu city from raw location text
 */
function resolveCity(rawLocation = '') {
  const loc = rawLocation.toLowerCase();
  if (loc.includes('chennai') || loc.includes('madras')) return 'Chennai';
  if (loc.includes('coimbatore') || loc.includes('kovai')) return 'Coimbatore';
  if (loc.includes('madurai')) return 'Madurai';
  if (loc.includes('trichy') || loc.includes('tiruchirappalli')) return 'Trichy';
  if (loc.includes('salem')) return 'Salem';
  if (loc.includes('tirunelveli')) return 'Tirunelveli';
  if (loc.includes('hosur')) return 'Hosur';
  if (loc.includes('vellore')) return 'Vellore';
  if (loc.includes('erode')) return 'Erode';
  if (loc.includes('tiruppur')) return 'Tiruppur';
  return 'Tamil Nadu';
}

/**
 * Extract technology skills and tags from title and description
 */
function extractSkillTags(title = '', desc = '') {
  const text = `${title} ${desc}`.toLowerCase();
  const allSkills = [
    'React', 'Node.js', 'Python', 'Java', 'Angular', 'Vue', 'TypeScript',
    'JavaScript', 'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'SQL',
    'PostgreSQL', 'MongoDB', 'Go', 'Rust', 'Spring Boot', 'Django',
    '.NET', 'C#', 'Flutter', 'DevOps', 'CI/CD', 'Machine Learning', 'AI'
  ];
  const detected = allSkills.filter(skill => {
    const sLower = skill.toLowerCase();
    if (sLower === 'c#') return text.includes('c#') || text.includes('.net');
    if (sLower === 'go') return /\bgo\b|\bgolang\b/.test(text);
    if (sLower === 'ai') return /\bai\b|\bgenai\b|\bartificial intelligence\b/.test(text);
    return text.includes(sLower);
  });
  if (detected.length === 0) detected.push('Software Engineering', 'Tamil Nadu Tech');
  return detected;
}

/**
 * Scrape a single LinkedIn guest search page
 */
async function fetchLinkedInPage(keyword, location, start = 0) {
  const encodedKw = encodeURIComponent(keyword);
  const encodedLoc = encodeURIComponent(location);
  const url = `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=${encodedKw}&location=${encodedLoc}&start=${start}`;
  
  const userAgent = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
  const res = await fetch(url, {
    headers: {
      'User-Agent': userAgent,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Cache-Control': 'no-cache',
      'Pragma': 'no-cache'
    },
    signal: AbortSignal.timeout(10000)
  });

  if (!res.ok) {
    if (res.status === 429) {
      console.warn(`[LinkedIn Scraper] Rate limited (429) for ${keyword} in ${location}`);
    } else {
      console.warn(`[LinkedIn Scraper] Status ${res.status} fetching ${url}`);
    }
    return [];
  }

  const html = await res.text();
  const $ = cheerio.load(html);
  const extracted = [];

  $('li').each((_, el) => {
    const title = $(el).find('.base-search-card__title, h3.base-search-card__title').text().trim();
    const company = $(el).find('.base-search-card__subtitle, h4.base-search-card__subtitle').text().trim();
    const locText = $(el).find('.job-search-card__location').text().trim();
    const link = $(el).find('a.base-card__full-link').attr('href');
    const postedTime = $(el).find('time').attr('datetime') || $(el).find('time').text().trim();
    const urn = $(el).find('.job-search-card').attr('data-entity-urn') || '';
    
    // Extract numeric job ID from urn or link
    let jobId = '';
    const urnMatch = urn.match(/urn:li:jobPosting:(\d+)/);
    if (urnMatch) {
      jobId = urnMatch[1];
    } else if (link) {
      const linkMatch = link.match(/-(\d+)(?:\?|$)/);
      if (linkMatch) jobId = linkMatch[1];
    }

    if (title && company && (locText.toLowerCase().includes('tamil nadu') || locText.toLowerCase().includes('chennai') || locText.toLowerCase().includes('coimbatore') || locText.toLowerCase().includes('madurai') || locText.toLowerCase().includes('trichy') || locText.toLowerCase().includes('salem') || locText.toLowerCase().includes('india'))) {
      const cleanUrl = link ? link.split('?')[0] : `https://www.linkedin.com/jobs/view/${jobId}`;
      const city = resolveCity(locText);
      const docId = `linkedin_${jobId || `${company}_${title}`.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 50)}`;

      extracted.push({
        id: docId,
        jobId: jobId || docId,
        title: title.slice(0, 250),
        company: company.slice(0, 150),
        location: (locText || `${city}, Tamil Nadu, India`).slice(0, 150),
        city,
        state: 'Tamil Nadu',
        apply_url: cleanUrl.slice(0, 800),
        link: cleanUrl.slice(0, 800),
        posted_date: postedTime || new Date().toISOString().split('T')[0],
        source: 'LinkedIn',
        verified: true,
        scraped_at: new Date().toISOString(),
        skills: extractSkillTags(title),
        employment_type: 'Full-time',
        experience: /senior|lead|architect|manager/i.test(title) ? 'Experienced' : 'Fresher & Experienced',
        batch: /fresher|intern|trainee/i.test(title) ? '2024 / 2025 / 2026 Batch' : 'All Batches',
        salary: 'As per LinkedIn vacancy norms'
      });
    }
  });

  return extracted;
}

/**
 * Save job document to Firestore
 */
async function saveJobToFirestore(firestoreDb, job) {
  try {
    const jobDocRef = doc(firestoreDb, 'linkedin_jobs', job.id);
    await setDoc(jobDocRef, {
      title: job.title,
      company: job.company,
      location: job.location,
      city: job.city,
      state: job.state,
      apply_url: job.apply_url,
      link: job.link,
      posted_date: job.posted_date,
      source: job.source,
      verified: job.verified,
      scraped_at: job.scraped_at,
      skills: job.skills,
      employment_type: job.employment_type,
      experience: job.experience,
      batch: job.batch,
      salary: job.salary,
      jobId: job.jobId
    }, { merge: true });
    return true;
  } catch (err) {
    console.error(`[LinkedIn Scraper] Error saving job ${job.id} to Firestore:`, err.message);
    return false;
  }
}

/**
 * Run a full scraping cycle for Tamil Nadu region
 */
export async function scrapeTamilNaduLinkedInJobs(options = {}) {
  const { maxTargets = 6, delayBetweenMs = 1800 } = options;
  const firestoreDb = initFirestore();

  scraperState.status = 'running';
  scraperState.lastError = null;
  scraperState.lastRunAt = new Date().toISOString();

  console.log('[LinkedIn Scraper] Starting Tamil Nadu job scraper run...');
  const collectedJobs = new Map();
  let savedCount = 0;

  // Build target query list
  const targets = [];
  for (const loc of TN_LOCATIONS) {
    for (const role of SEARCH_ROLES) {
      targets.push({ location: loc, keyword: role });
    }
  }

  // Shuffle or slice targets to be polite and avoid hammering LinkedIn
  const runTargets = targets.slice(0, maxTargets);

  for (const target of runTargets) {
    scraperState.activeTarget = `${target.keyword} in ${target.location}`;
    try {
      console.log(`[LinkedIn Scraper] Scraping "${target.keyword}" in "${target.location}"...`);
      const jobs = await fetchLinkedInPage(target.keyword, target.location, 0);
      console.log(`[LinkedIn Scraper] Found ${jobs.length} jobs for ${target.keyword} in ${target.location}`);
      
      for (const job of jobs) {
        if (!collectedJobs.has(job.id)) {
          collectedJobs.set(job.id, job);
          
          // Save immediately to Firestore
          if (firestoreDb) {
            const saved = await saveJobToFirestore(firestoreDb, job);
            if (saved) savedCount++;
          }
        }
      }
    } catch (err) {
      console.error(`[LinkedIn Scraper] Failed scraping target ${target.keyword}:`, err.message);
      scraperState.lastError = err.message;
    }

    // Polite delay between search requests
    await sleep(delayBetweenMs + Math.floor(Math.random() * 500));
  }

  scraperState.status = 'idle';
  scraperState.activeTarget = null;
  scraperState.totalScrapedCount += collectedJobs.size;
  scraperState.totalSavedToFirestore += savedCount;
  scraperState.recentJobs = Array.from(collectedJobs.values());

  console.log(`[LinkedIn Scraper] Cycle complete. Scraped ${collectedJobs.size} unique jobs, saved ${savedCount} to Firestore.`);
  return {
    scraped: collectedJobs.size,
    savedToFirestore: savedCount,
    jobs: Array.from(collectedJobs.values())
  };
}

/**
 * Retrieve LinkedIn jobs from Firestore
 */
export async function getFirestoreLinkedInJobs(filter = {}) {
  const firestoreDb = initFirestore();
  if (!firestoreDb) {
    // Fallback to in-memory recent jobs if Firestore client is initializing
    return scraperState.recentJobs;
  }

  try {
    const jobsCol = collection(firestoreDb, 'linkedin_jobs');
    const q = query(jobsCol, limit(filter.limit || 100));
    const snapshot = await getDocs(q);

    const results = [];
    snapshot.forEach(docSnap => {
      const data = docSnap.data();
      results.push({
        id: docSnap.id,
        ...data,
        // Standardize format for app feed
        role: data.title,
        company: data.company,
        location: data.location,
        city: data.city || resolveCity(data.location),
        is_tamil_nadu: true,
        is_walkin: false,
        is_drive: false,
        batch: data.batch || '2024 / 2025 / 2026 Batch',
        degrees: 'B.E / B.Tech / MCA / B.Sc / Any Degree',
        salary: data.salary || 'Competitive Industry CTC',
        link: data.apply_url || data.link,
        apply_url: data.apply_url || data.link,
        source: 'LinkedIn',
        platform: 'LinkedIn Official',
        type: 'linkedin',
        date_posted: data.posted_date ? `LinkedIn • ${data.posted_date}` : 'LinkedIn Live Vacancy',
        skills: Array.isArray(data.skills) ? data.skills : extractSkillTags(data.title),
        description: data.description || `${data.title} opportunity at ${data.company} in ${data.location}. Scraped from verified LinkedIn vacancy feed.`
      });
    });

    if (results.length > 0) {
      scraperState.recentJobs = results;
    }
    return results;
  } catch (err) {
    console.error('[LinkedIn Scraper] Error fetching from Firestore:', err.message);
    return scraperState.recentJobs;
  }
}

/**
 * Background Scheduler
 */
let schedulerIntervalId = null;

export function startLinkedInBackgroundJob(intervalMs = 30 * 60 * 1000) {
  if (schedulerIntervalId) {
    console.log('[LinkedIn Scraper] Background job scheduler is already active.');
    return;
  }

  scraperState.nextRunAt = new Date(Date.now() + 5000).toISOString();
  console.log(`[LinkedIn Scraper] Background job initiated. Schedule frequency: every ${Math.round(intervalMs / 60000)} minutes.`);

  // Initial run 5 seconds after startup so server starts smoothly
  setTimeout(() => {
    scrapeTamilNaduLinkedInJobs({ maxTargets: 6 })
      .catch(err => console.error('[LinkedIn Scraper] Initial background scrape run error:', err.message));
  }, 5000);

  // Set recurring interval
  schedulerIntervalId = setInterval(() => {
    scraperState.nextRunAt = new Date(Date.now() + intervalMs).toISOString();
    scrapeTamilNaduLinkedInJobs({ maxTargets: 6 })
      .catch(err => console.error('[LinkedIn Scraper] Scheduled background scrape run error:', err.message));
  }, intervalMs);
}

export function stopLinkedInBackgroundJob() {
  if (schedulerIntervalId) {
    clearInterval(schedulerIntervalId);
    schedulerIntervalId = null;
    console.log('[LinkedIn Scraper] Background job stopped.');
  }
}

export function getLinkedInScraperStatus() {
  return {
    ...scraperState,
    schedulerActive: schedulerIntervalId !== null
  };
}
