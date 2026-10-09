'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const search=require('./src/engineering-search');
const {createRunReader}=require('./src/engineering-cache');
const {writeJsonIfChanged}=require('./src/engineering-io');
const {querySnapshot,batchSnapshot,check}=require('./src/engineering');
const NOW=Date.parse('2026-10-09T00:00:00Z');
const fixture=i=>({title:i%3?'Python Backend Developer':'Data Entry',company:'Fixture',city:'Chennai',
  location:'Chennai',description:'Python SQL computer science',skills:['sql'],experience:'2-5 years',
  source:'fixture',source_type:'company',posted_at:i%2?'2026-10-08':null,
  apply_url:`https://jobs.smartrecruiters.com/Freshworks/${i}`,verified:i%4!==0,
  verify_reason:'live_public_job'});
// Slow independent pre-optimization scoring reference. Retains normalization semantics.
const text=v=>String(v||'').toLowerCase().replace(/[^a-z0-9+#.]+/g,' ').trim().replace(/\s+/g,' ');
const contains=(h,n)=>(` ${text(h)} `).includes(` ${text(n)} `);
function referenceScore(job,profile,now){const p=search.preset(profile);
  const title=text(job.title),hay=[job.title,job.description,...(job.skills||[])].join(' ');
  const aliases=p.roles.flatMap(search.expand).filter(w=>w!=='data');
  if(!aliases.some(w=>contains(title,w)))return {score:-1,reasons:['role_not_matched']};
  const loc=search.city(job.location)||search.city(job.city),km=loc?Math.min(...p.cities.map(c=>search.distance(c,loc))):null;
  if(km===null||km>p.travel_radius_km)return {score:-1,reasons:['location_outside_preset_or_unknown']};
  const reasons=['role_match',km===0?'selected_city':`approx_${km}km_city_centres`];
  let value=50+(km===0?20:Math.max(0,15-km/20));
  if(p.branch&&contains(hay,p.branch)){value+=5;reasons.push('stated_branch_mentioned_not_eligibility_guarantee');}
  const hits=p.skills.filter(s=>contains(hay,s));value+=Math.min(15,hits.length*5);if(hits.length)reasons.push(`skills:${hits.join(',')}`);
  const range=String(job.experience||'').match(/(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)/i);
  if(p.experience_years!==null&&range&&p.experience_years<Number(range[1])){value-=30;reasons.push('experience_below_stated_minimum');}
  else if(p.experience_years===null)reasons.push('experience_unknown_not_eligibility_checked');
  const date=Date.parse(job.posted_at);if(Number.isFinite(date)&&date<=now){value+=Math.max(0,15-(now-date)/(24 * 60 * 60 * 1000));reasons.push('posting_date_known');}else reasons.push('posting_date_unknown');
  const state=search.integrity(job);value+=state==='verified'?15:-15;if(['company','government'].includes(job.source_type))value+=5;
  reasons.push(`evidence:${state}`,`source:${job.source||'unknown'}`);if(!p.configured)reasons.push('default_preset_personal_fit_unknown');
  return {score:Math.round(value),reasons,distance_km:km,distance_basis:'approximate city-centre straight-line distance; not travel time',integrity:state};
}
test('compiled rank equals reference scores, ordering and evidence for large mixed fixture',()=>{
  const profiles=[search.DEFAULT,{...search.DEFAULT,configured:true,branch:'computer science',skills:['python','sql','SQL','c++','!!!'],experience_years:1,travel_radius_km:100},
    {...search.DEFAULT,roles:['mechanical engineer'],cities:['Vellore'],travel_radius_km:300}];
  const jobs=Array.from({length:2000},(_,i)=>({...fixture(i),location:i%5?'Chennai':'Ranipet',http_status:i%17===0?404:null}));
  for(const p of profiles){const expected=search.dedupe(jobs).map(j=>({...j,match:referenceScore(j,p,NOW)}))
    .filter(j=>j.match.score>=0&&!['closed','access_denied'].includes(j.match.integrity)).sort((a,b)=>b.match.score-a.match.score||a.id.localeCompare(b.id));
    assert.deepEqual(search.rank(jobs,p,NOW),expected);}
});
test('batch snapshot equals singles and isolates invalid profile',()=>{
  const data={generated_at:new Date(NOW).toISOString(),jobs:[fixture(1)]},p=[search.DEFAULT,{...search.DEFAULT,roles:['python']}];
  assert.deepEqual(batchSnapshot(data,p,NOW),p.map(v=>querySnapshot(data,v,NOW)));
  const out=batchSnapshot(data,[p[0],{cities:['unknown']},p[1]],NOW);
  assert.ok(out[1].error);assert.deepEqual(out[2],querySnapshot(data,p[1],NOW));
  assert.throws(()=>batchSnapshot(data,Array(5).fill(p[0]),NOW));
});
test('GET cache reuses exact URLs only within horizon, preserves fetch time, rejects blocked routes/deadline',async()=>{
  let now=NOW,calls=0;
  const read=createRunReader(async url=>{calls++;return {status:200,url,body:'abc'};},url=>url.startsWith('https://public.test/'),{clock:()=>now,ttl:100,maxEntries:2,maxBytes:6});
  const a=await read('https://public.test/a',now+1000);now+=50;
  assert.deepEqual(await read('https://public.test/a',now+1000),a);assert.equal(calls,1);
  await assert.rejects(read('https://private.test/a',now+1000),/unapproved/);
  await assert.rejects(read('https://public.test/a',now),/deadline/);
  now+=51;await read('https://public.test/a',now+1000);assert.equal(calls,2);
  await read('https://public.test/b',now+1000);await read('https://public.test/c',now+1000);
  await read('https://public.test/a',now+1000);assert.equal(calls,5);
});
test('failed/redirect/oversize reads never cached; same URL coalesced',async()=>{
  for(const response of [{status:403,body:'denied'},{status:429,body:'retry'},{status:302,body:'',redirected:true},{status:200,body:'large'}]){
    let calls=0;const read=createRunReader(async()=>{calls++;return response;},()=>true,{maxBytes:3});
    await read('same',Date.now()+1000);await read('same',Date.now()+1000);assert.equal(calls,2);
  }
  let calls=0;const read=createRunReader(async()=>{calls++;throw Error('transient');},()=>true);
  await assert.rejects(read('same',Date.now()+1000));await assert.rejects(read('same',Date.now()+1000));assert.equal(calls,2);
  let resolve,network=0;const pending=createRunReader(()=>{network++;return new Promise(r=>{resolve=r;});},()=>true);
  const one=pending('same',Date.now()+1000),two=pending('same',Date.now()+1000);resolve({status:200,body:'ok'});
  assert.deepEqual(await one,await two);assert.equal(network,1);
});
test('cached verification retains original evidence timestamp and same strict checks',async()=>{
  const j=fixture(1),stamp='2026-10-09T00:00:00.000Z';
  const r=await check(j,Date.now()+1000,async()=>({status:200,url:j.apply_url,fetched_at:stamp,body:'<main><h1>Python Backend Developer</h1>Responsibilities: develop. Apply now</main>'}));
  assert.equal(r.verified,true);assert.equal(r.verified_at,stamp);
});
test('identical JSON avoids rewriting and changed JSON atomically replaces without lost records',()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'engineering-io-')),file=path.join(dir,'state.json');
  try{const value={jobs:[fixture(1)]};assert.equal(writeJsonIfChanged(file,value),true);
    const before=fs.statSync(file);assert.equal(writeJsonIfChanged(file,value),false);
    assert.equal(fs.statSync(file).mtimeMs,before.mtimeMs);
    value.jobs.push(fixture(2));assert.equal(writeJsonIfChanged(file,value),true);
    assert.deepEqual(JSON.parse(fs.readFileSync(file,'utf8')),value);assert.deepEqual(fs.readdirSync(dir),['state.json']);
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
