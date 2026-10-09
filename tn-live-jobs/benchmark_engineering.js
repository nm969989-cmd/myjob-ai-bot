'use strict';
// Offline benchmark against the audited pre-optimization fixture (PR8 f8b00ca).
// No CLI-controlled module is executed; equivalence assertions remain mandatory.
const assert=require('node:assert/strict');
const {performance}=require('node:perf_hooks');
if(process.argv[2])throw Error('Baseline is fixed: omit the former baseline-path argument');
const before=require('./fixtures/engineering-baseline.cjs'),after=require('./src/engineering-search');
const now=Date.parse('2026-10-09T00:00:00Z');
const profile={...before.DEFAULT,configured:true,branch:'computer science',skills:['python','sql','react','aws'],experience_years:1,travel_radius_km:100};
const sizes=(process.env.BENCH_SIZES||'1000,10000').split(',').map(Number);
function time(fn){if(global.gc)global.gc();const start=performance.now();fn();return performance.now()-start;}
const median=v=>v.sort((a,b)=>a-b)[Math.floor(v.length/2)];
console.log(JSON.stringify({node:process.version,platform:process.platform,gc:!!global.gc,runs:5,scope:'offline rank CPU; not source coverage, network or Telegram latency'}));
for(const n of sizes){if(!Number.isInteger(n)||n<1||n>50000)throw Error('BENCH_SIZES must be 1-50000');
  const jobs=Array.from({length:n},(_,i)=>({title:i%4?'Python Backend Developer':'Data Engineer',company:'Fixture',city:'Chennai',location:'Chennai',
    description:'Python SQL React AWS computer science engineer',skills:['python','sql'],experience:'2-5 years',
    apply_url:`https://example.test/jobs/${i}?utm_source=fixture`,source:'fixture',source_type:'company',
    posted_at:'2026-10-08',verified:i%3!==0,verify_reason:'live_public_job'}));
  assert.deepEqual(after.rank(jobs,profile,now),before.rank(jobs,profile,now));
  before.rank(jobs,profile,now);after.rank(jobs,profile,now); // warmup both
  const a=[],b=[];for(let i=0;i<5;i++){if(i%2){b.push(time(()=>after.rank(jobs,profile,now)));a.push(time(()=>before.rank(jobs,profile,now)));}
    else{a.push(time(()=>before.rank(jobs,profile,now)));b.push(time(()=>after.rank(jobs,profile,now)));}}
  console.log(JSON.stringify({records:n,equivalent:true,before_ms:median(a),after_ms:median(b),rss_bytes:process.memoryUsage().rss}));
}
