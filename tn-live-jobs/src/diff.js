'use strict';

/**
 * DELTA (NEW JOB) DETECTION
 *
 * Because a job's id is a hash of its apply URL, the same advert keeps the same
 * id on every run. That makes it easy to answer three questions:
 *   - which jobs are NEW?      (id was not in the previous data/jobs.json)
 *   - which jobs are GONE?     (id was there before, not live any more)
 *   - which jobs are STILL UP? (id in both)
 */

const fs = require('fs');
const path = require('path');
const { log } = require('./util');

/** Read a { jobs: [...] } file. Returns [] when the file is missing or broken. */
function readJobFile(filePath) {
  try {
    if (!fs.existsSync(filePath)) return [];
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (Array.isArray(parsed)) return parsed;
    if (parsed && Array.isArray(parsed.jobs)) return parsed.jobs;
    return [];
  } catch (error) {
    log(`  could not read ${path.basename(filePath)} (${error.message}); treating it as empty`);
    return [];
  }
}

/** Read any small JSON file, returning `fallback` when it is missing/broken. */
function readJsonSafe(filePath, fallback) {
  try {
    if (!fs.existsSync(filePath)) return fallback;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (error) {
    return fallback;
  }
}

/**
 * Compare this run's jobs with the previous run's jobs.
 * `previous` should already be filtered to the jobs that were live last time.
 */
function computeDiff(currentJobs, previousJobs) {
  const previousIds = new Set(previousJobs.map((job) => job.id));
  const currentIds = new Set(currentJobs.map((job) => job.id));

  const newJobs = currentJobs.filter((job) => !previousIds.has(job.id));
  const keptJobs = currentJobs.filter((job) => previousIds.has(job.id));
  const removedJobs = previousJobs.filter((job) => !currentIds.has(job.id));

  return { newJobs, keptJobs, removedJobs };
}

/** Add one row to the run history used for the trending sparkline. */
function appendHistory(existingHistory, timestamp, totals) {
  const history = Object.assign({}, existingHistory || {});
  history[timestamp] = { total: totals.total, new: totals.new, verified: totals.verified };
  // Keep the last 500 runs so the file never grows without limit.
  const keys = Object.keys(history).sort();
  if (keys.length > 500) {
    for (const key of keys.slice(0, keys.length - 500)) delete history[key];
  }
  return history;
}

module.exports = {
  readJobFile,
  readJsonSafe,
  computeDiff,
  appendHistory,
};
