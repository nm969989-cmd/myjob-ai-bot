'use strict';
// Keep all records and exact JSON format; skip only byte-identical writes.
// Path audit: this is an internal filesystem helper, not an HTTP/chat endpoint.
// Production callers in engineering.js supply fixed engineering output filenames
// under the operator-owned checkout. Tests supply their own mkdtemp directory.
// Atomic temp names must be dynamic; wx prevents clobbering existing temp files.
// Never pass a saved profile, request path or source URL as the file argument.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
function writeJsonIfChanged(file, value) {
  const bytes = JSON.stringify(value,null,2)+'\n';
  try { if(fs.readFileSync(file,'utf8')===bytes) return false; }
  catch(e) { if(e.code!=='ENOENT') throw e; }
  fs.mkdirSync(path.dirname(file),{recursive:true});
  const tmp = `${file}.${process.pid}.${crypto.randomBytes(8).toString('hex')}.tmp`;
  try { fs.writeFileSync(tmp,bytes,{encoding:'utf8',flag:'wx'}); fs.renameSync(tmp,file); }
  finally { try { fs.unlinkSync(tmp); } catch(e) { if(e.code!=='ENOENT') throw e; } }
  return true;
}
module.exports = {writeJsonIfChanged};
