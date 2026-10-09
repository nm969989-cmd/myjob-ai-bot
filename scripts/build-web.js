'use strict';
// Publish the existing static board; building never scrapes or sends applications.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = path.join(root, 'tn-live-jobs/public');
const output = path.join(root, 'dist');
if (!fs.existsSync(path.join(source, 'index.html'))) throw new Error('Missing public job board entry point');
fs.rmSync(output, { recursive: true, force: true });
fs.cpSync(source, output, { recursive: true });
console.log('Public job board built in dist/');
