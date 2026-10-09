'use strict';
// docs/ is the source of truth; the independently deployed Node board uses copies.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const files = ['career/core.js', 'career/workspace.js', 'career/workspace.css', 'career/icon-192.png', 'career/icon-512.png', 'manifest.webmanifest', 'offline.html'];
const hash = crypto.createHash('sha256');
for (const file of files) hash.update(fs.readFileSync(path.join(root, 'docs', file)));
const version = hash.digest('hex').slice(0, 12);
const worker = fs.readFileSync(path.join(root, 'docs/sw.js'), 'utf8').replace(/const CACHE = PREFIX \+ '[^']+';/, `const CACHE = PREFIX + '${version}';`);
fs.writeFileSync(path.join(root, 'docs/sw.js'), worker);
for (const file of [...files, 'sw.js']) {
  const target = path.join(root, 'tn-live-jobs/public', file);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(path.join(root, 'docs', file), target);
}
console.log('Synchronized career workspace and offline assets: ' + version);
