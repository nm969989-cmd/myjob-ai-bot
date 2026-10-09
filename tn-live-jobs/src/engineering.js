#!/usr/bin/env node
'use strict';
const fs = require('node:fs'), path = require('node:path'), cheerio = require('cheerio');
const search = require('./engineering-search');
const feeds = require('./sources/engineering-public');
const { writeJson } = require('./export');
const { computeDiff } = require('./diff');
const ROOT = path.resolve(__dirname,'..'), DATA = path.join(ROOT,'data');
// Filesystem audit: read callers use two fixed engineering JSON paths below.
// stdin profiles cannot select a path; report path is also a fixed local filename.
// The checkout/data volume must be operator-owned, not writable by remote users.
const INPUT_FILES = new Set([path.join(DATA,'engineering-matches.json'), path.join(DATA,'engineering-retry-queue.json')]);
function read(file,fallback){if(!INPUT_FILES.has(file))throw Error('Unapproved engineering input path');try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch(e){if(e.code==='ENOENT')return fallback;throw e;}}
function jobs(value){return Array.isArray(value)?value:(value.jobs||[]);}
function expired(j,now){const d=Date.parse(j.deadline||j.expires_at);return Number.isFinite(d)&&d<now;}
async function check(job,deadline){const j={...job,verified:false,verified_at:new Date().toISOString(),retry_deferred:false};
  if(expired(j,Date.now()))return {...j,verify_reason:'expired_deadline',integrity:'closed'};
  if(!feeds.permittedUrl(j.apply_url))return {...j,http_status:null,verify_reason:'access_denied',verify_note:'No approved public route; manual review only'};
  try{const r=await feeds.publicRead(j.apply_url,deadline);j.http_status=r.status;j.final_url=r.url;j.retry_after=r.retry_after;
    if(r.status===403)return {...j,verify_reason:'access_denied'};
    if(r.status!==200)return {...j,verify_reason:r.redirected?'redirect_unreviewed':`http_${r.status}`};
    const $=cheerio.load(r.body),heading=$('h1').first().text().trim(),body=$('main').text()||$('body').text();
    const norm=v=>String(v||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
    const match=norm(heading)===norm(j.title),signals=/(responsibilities|qualifications|job description)/i.test(body)&&/apply/i.test(body);
    if(/sign in to (continue|view)|captcha|access denied|verify you are human/i.test(body))return {...j,verify_reason:'access_denied'};
    if(match&&signals){j.verified=true;j.verify_reason='live_public_job';j.page_title=heading;j.verify_note='HTTP 200, matching job heading and responsibility/application signals';}
    else j.verify_reason='no_matching_job_evidence';
  }catch(e){j.verify_reason=/robots|unapproved|allowlist|disallow/i.test(e.message)?'access_denied':'request_failed';j.http_status=null;j.verify_error=e.message.slice(0,160);}
  return j;
}
async function run(){const now=Date.now(),deadline=now+8*60000,notes=[];
  const previous=jobs(read(path.join(DATA,'engineering-matches.json'),{jobs:[]})).slice(0,1000);
  const queue=read(path.join(DATA,'engineering-retry-queue.json'),[]).slice(0,200);
  const old=new Map(previous.map(j=>[search.key(j),j])),queued=new Map(queue.map(q=>[q.key,q]));
  const p=search.preset(), keywords=[...new Set(p.roles.flatMap(search.expand))];
  const found=await feeds.scrape({cities:p.cities,keywords,limit:100,deadline,note:(id,status,detail)=>notes.push({id,status,detail}),log:console.log});
  const all=search.dedupe([...found,...queue.filter(q=>q.due<=now).slice(0,20).map(q=>q.job)]);
  // Source order does not decide who gets the verification budget.
  const collectionPreset={...p, travel_radius_km:300, roles:['software engineer','backend','full-stack','frontend','data engineer','python','devops','mechanical engineer','civil engineer','electrical engineer','electronics engineer']};
  const candidates=search.rank(all,collectionPreset,now).slice(0,100), checked=[];let retryCount=0;
  for(const j of candidates){const q=queued.get(search.key(j)),prior=old.get(search.key(j));
    if(q&&q.due>now){checked.push({...j,...q.job,verified:false,retry_deferred:true});continue;}
    if(q&&retryCount>=20){checked.push({...q.job,verified:false,retry_deferred:true});continue;}
    if(prior?.retry_state==='exhausted_uncertain'){checked.push({...j,...prior,verified:false,retry_deferred:true});continue;}
    if(Date.now()>deadline){checked.push({...j,verified:false,verify_reason:'retry_pending',retry_deferred:true});continue;}
    if(q)retryCount++;
    checked.push({...await check(j,deadline),retry_attempts:q?.attempts||0,retry_first_seen:q?.first_seen||now});
  }
  const combined=search.reconcile(checked,previous,queue,now);
  const ranked=search.rank(combined.jobs,p,now),live=ranked.filter(j=>j.verified===true&&!expired(j,now));
  const diff=computeDiff(ranked,search.dedupe(previous));
  const timestamp=new Date().toISOString(),meta={status:'ok',finished_at:timestamp,started_at:new Date(now).toISOString(),
    duration_seconds:Math.round((Date.now()-now)/1000),trigger:process.env.GITHUB_EVENT_NAME||'engineering local',
    cities:p.cities,keywords,scraped_records:found.length,verified_jobs:live.length,new_jobs:diff.newJobs.length,
    removed_jobs:0,source_status:notes,validate_stats:{live:live.length,uncertain:ranked.length-live.length},
    note:'Missing/transient records retained as uncertain, never labelled closed merely for a failed scrape. Default preset; personal details unknown.'};
  // Additive outputs: do not overwrite the existing bot's jobs, history or website.
  writeJson(path.join(DATA,'engineering-matches.json'),{generated_at:timestamp,preset:p,jobs:combined.jobs.slice(0,1000),source_status:notes,meta});
  writeJson(path.join(DATA,'engineering-retry-queue.json'),combined.queue);
  const publicPayload={generated_at:timestamp,count:live.length,jobs:live,note:'Default engineering preset. Only evidence-verified records.'};
  writeJson(path.join(ROOT,'public/data/engineering-matches.json'),publicPayload);
  fs.writeFileSync(path.join(DATA,'engineering-report.md'),`# Engineering search run\n\nDefault preset: branch/skills/experience unknown; exact selected cities, radius 0 km.\n\n${live.length} evidence-verified matches; ${ranked.length-live.length} uncertain matches; ${combined.queue.length} pending retries.\n\n`+notes.map(n=>`- ${n.id}: ${n.status} — ${n.detail}`).join('\n')+'\n');
  console.log(JSON.stringify({verified:live.length,uncertain:ranked.length-live.length,pending:combined.queue.length}));
}
if(require.main===module){if(process.argv.includes('--query')){let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',c=>{input+=c;if(input.length>1000000)throw Error('query too large');});process.stdin.on('end',()=>{try{const q=JSON.parse(input);const data=read(path.join(DATA,'engineering-matches.json'),null);if(!data)throw Error('No engineering scan; run npm run engineering:refresh first');
  const p=search.preset(q.profile||{});const ranked=search.rank(data.jobs,p);console.log(JSON.stringify({generated_at:data.generated_at,preset:p,jobs:ranked.slice(0,50)}));}catch(e){console.error(e.message);process.exitCode=1;}});}else run().catch(e=>{console.error(e.message);process.exitCode=1;});}
module.exports={run,check,expired};
