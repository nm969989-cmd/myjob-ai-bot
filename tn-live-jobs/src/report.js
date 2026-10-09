'use strict';

/**
 * Builds the run summary. The exact same markdown is written to report.md and
 * appended to $GITHUB_STEP_SUMMARY, so what you see in the Actions run is what
 * is stored in the repository.
 */

const fs = require('fs');
const path = require('path');
const { ensureDir } = require('./export');
const { clip } = require('./util');

function escapeCell(value) {
  if (value === null || value === undefined) return '';
  return String(value).replace(/\|/g, '\\|').replace(/\n/g, ' ');
}

function table(headers, rows) {
  const lines = [
    '| ' + headers.map(escapeCell).join(' | ') + ' |',
    '| ' + headers.map(() => '---').join(' | ') + ' |',
  ];
  for (const row of rows) lines.push('| ' + row.map(escapeCell).join(' | ') + ' |');
  return lines.join('\n');
}

function buildReport(run) {
  const { meta, sites, sourceCounts, foundCounts, validateStats, diff, latest, guard } = run;
  const d = diff || {};
  const newList = d.new || d.newJobs || [];
  const removedList = d.removed || d.removedJobs || [];
  const found = foundCounts || {};
  const parts = [];

  parts.push(`# Tamil Nadu Live Jobs - run summary`);
  parts.push('');
  parts.push(`- **Started:** ${meta.started_at}`);
  parts.push(`- **Finished:** ${meta.finished_at}`);
  parts.push(`- **Duration:** ${meta.duration_seconds} s`);
  parts.push(`- **Trigger:** ${meta.trigger}`);
  parts.push(`- **Search:** keywords = ${meta.keywords.join(', ') || '(none)'} | cities = ${meta.cities.join(', ')}`);
  parts.push(
    `- **Live verified jobs: ${latest.verified}** (kept this run: ${latest.total}, new: ${latest.new}, gone since last run: ${d.removed_count !== undefined ? d.removed_count : removedList.length})`
  );
  parts.push('');

  if (guard && guard.skipped) {
    parts.push(`> :warning: **Safety guard triggered.** ${guard.message}`);
    parts.push('');
  }

  parts.push('## Results per source');
  parts.push('');
  parts.push(
    table(
      ['Source', 'Tier', 'Status', 'Found', 'In this run', 'Note'],
      sites.map((site) => [
        site.label || site.id,
        site.tier,
        site.status === 'ok'
          ? ':white_check_mark: ok'
          : site.status === 'no_listings'
            ? ':grey_question: no listings'
            : `:x: ${site.status}`,
        found[site.id] || 0,
        sourceCounts[site.id] || 0,
        clip(site.detail || '', 110),
      ])
    )
  );
  parts.push('');
  parts.push('_"Found" = usable records this site offered; "In this run" = how many survived the per-run cap._');
  parts.push('');

  parts.push('## Link verification');
  parts.push('');
  parts.push(
    table(
      ['Check', 'Count'],
      [
        ['Links re-opened', validateStats.checked],
        [':white_check_mark: Verified live', validateStats.live],
        ['Government documents verified', validateStats.documents],
        ['Login required (kept, not published)', validateStats.loginRequired],
        ['Page did not look like a job (no_job_signal)', validateStats.noSignal],
        ['Redirected elsewhere', validateStats.redirected],
        ['Dead link (HTTP 4xx/5xx)', validateStats.dead],
        ['Could not be reached', validateStats.unreachable],
      ]
    )
  );
  parts.push('');

  if (newList.length) {
    parts.push(`## New this run (${newList.length})`);
    parts.push('');
    parts.push(
      table(
        ['Title', 'Company', 'City', 'Category', 'Verified', 'Apply'],
        newList.slice(0, 30).map((job) => [
          clip(job.title, 60),
          clip(job.company, 35),
          job.city,
          job.category,
          job.verified ? 'yes' : `no (${job.verify_reason})`,
          job.apply_url,
        ])
      )
    );
    if (newList.length > 30) parts.push(`\n_(showing the first 30 of ${newList.length})_`);
    parts.push('');
  } else {
    parts.push('## New this run');
    parts.push('');
    parts.push('No new jobs this run - the board is unchanged.');
    parts.push('');
  }

  if (removedList.length) {
    parts.push(`## Gone since last run (${removedList.length})`);
    parts.push('');
    parts.push(removedList.slice(0, 20).map((job) => `- ${clip(job.title, 70)} (${clip(job.company, 40)})`).join('\n'));
    parts.push('');
  }

  parts.push('## Data integrity');
  parts.push('');
  parts.push(
    table(
      ['Rule', 'Result'],
      [
        ['Every published job was re-opened and checked', `yes - ${validateStats.checked} links checked`],
        ['Jobs without a real title/company/apply URL dropped', `yes - ${meta.droppedRecords} record(s) dropped while scraping`],
        ['Invented salary / date / URL', 'never - values are only ever read from a fetched page'],
        ['Unverified jobs excluded from the web page', 'yes - public/data/jobs.json holds verified jobs only'],
      ]
    )
  );
  parts.push('');
  parts.push('## Files updated');
  parts.push('');
  parts.push(
    [
      '- `data/jobs.json` - every record from this run (live + rejected)',
      '- `data/jobs.csv` - same rows for Excel',
      '- `data/new-jobs.json` - only the first-time jobs',
      '- `data/history.json` - run-by-run totals',
      '- `data/last-run.json` - metadata for this run',
      '- `public/data/jobs.json` and `public/data/jobs.js` - verified jobs only, used by the web page',
    ].join('\n')
  );
  parts.push('');

  return parts.join('\n');
}

/** Write report.md in the project root. */
function writeReport(rootDir, markdown) {
  const file = path.join(rootDir, 'report.md');
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, markdown + '\n', 'utf8');
  return file;
}

module.exports = { buildReport, writeReport, table };
