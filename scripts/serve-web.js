'use strict';
// Root entry point for Node-based importers; reuse the existing public server.
const { runServe } = require('../tn-live-jobs/src/cli');
const args = process.argv.slice(2);
let port = process.env.PORT || '3000';
let host = process.env.HOST || '0.0.0.0';
for (let i = 0; i < args.length; i++) {
  const [flag, inline] = args[i].split('=', 2);
  if (!['--port', '--host'].includes(flag)) throw new Error(`Unsupported option: ${flag}`);
  const value = inline ?? args[++i];
  if (!value || value.startsWith('--')) throw new Error(`Missing value for ${flag}`);
  if (flag === '--port') port = value;
  else host = value;
}
if (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535) throw new Error('PORT must be between 1 and 65535');
runServe(Number(port), host);
