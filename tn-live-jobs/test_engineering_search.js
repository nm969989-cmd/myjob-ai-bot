'use strict';
// Offline fixtures only: no remote HTTP, browser, Telegram or production bot dispatch.
const test = require('node:test'), assert = require('node:assert/strict');
const s = require('./src/engineering-search'), feeds = require('./src/sources/engineering-public');
const { check } = require('./src/engineering');
const NOW = Date.parse('2026-10-09T00:00:00Z');
const job = (extra={}) => ({title:'Backend Developer',company:'Example Engineering',city:'Chennai',location:'Chennai',
  apply_url:'https://careers.wipro.com/job/Backend-Developer/123-en_US/',source:'wipro.com',source_type:'company',
  posted_at:null,verified:false,verify_reason:'not_checked',...extra});

test('defaults explicitly leave personal eligibility unknown',()=>{
  const p=s.preset();assert.equal(p.configured,false);assert.equal(p.branch,null);assert.deepEqual(p.skills,[]);
  assert.equal(p.experience_years,null);assert.equal(p.travel_radius_km,0);assert.equal(p.cities.length,4);
  assert.throws(()=>s.preset({travel_radius_km:301}));assert.throws(()=>s.preset({cities:['unknown']}));
});
test('engineering aliases match without treating data entry as data engineering',()=>{
  for(const title of ['Software Developer','Python Developer','Fullstack Engineer','Data Scientist'])assert.ok(s.rank([job({title})]).length);
  assert.equal(s.rank([job({title:'Data Entry Operator'})],{...s.DEFAULT,roles:['data']}).length,0);
  assert.ok(s.rank([job({title:'Data Analyst'})],{...s.DEFAULT,roles:['data']}).length);
});
test('city aliases and radius use explicit location not a collapsed suburb',()=>{
  assert.equal(s.city('Pondicherry'),'Puducherry');assert.equal(s.city('Thiruvannamalai'),'Tiruvannamalai');
  const suburb=job({location:'Chengalpattu',city:'Chennai'});
  assert.equal(s.rank([suburb]).length,0);assert.ok(s.rank([suburb],{...s.DEFAULT,travel_radius_km:100}).length);
  assert.equal(s.score(suburb,{...s.DEFAULT,travel_radius_km:100}).distance_basis.includes('not travel time'),true);
});
test('unknown posting dates are not replaced with scrape dates; fit is explained',()=>{
  const p={...s.DEFAULT,configured:true,branch:'computer science',skills:['python'],experience_years:1};
  const j=job({description:'Computer science, Python',experience:'3-5 years',scraped_at:new Date(NOW).toISOString()});
  const a=s.score(j,p,NOW);assert.ok(a.reasons.includes('posting_date_unknown'));
  assert.ok(a.reasons.includes('experience_below_stated_minimum'));assert.ok(a.reasons.includes('stated_branch_mentioned_not_eligibility_guarantee'));
  assert.ok(s.score(job({...j,posted_at:'2026-10-08'}),p,NOW).score>a.score);
});
test('cross-source dedupe keeps evidence; distinct requisitions are not title-deduped',()=>{
  const a=job({source:'one',apply_url:'https://careers.wipro.com/job/backend/1?utm_source=x'});
  const b=job({source:'two',apply_url:'https://careers.wipro.com/job/backend/1#fragment'});
  const merged=s.dedupe([a,b]);assert.equal(merged.length,1);assert.equal(merged[0].provenance.length,2);
  assert.equal(s.dedupe(merged)[0].provenance.length,2);
  assert.equal(s.dedupe([job({requisition_id:'1'}),job({requisition_id:'2',apply_url:'https://careers.wipro.com/job/backend/2'})]).length,2);
  assert.equal(s.dedupe([job({requisition_id:'1'}),job({requisition_id:'1',source:'other',apply_url:'https://jobs.smartrecruiters.com/Freshworks/1'})]).length,1);
  assert.notEqual(s.canonicalUrl('https://x.test/job?id=1'),s.canonicalUrl('https://x.test/job?id=2'));
});
test('transient failures retry but closed/access-denied records do not',()=>{
  const r=s.reconcile([job({http_status:429,verify_reason:'http_429',retry_after:'7200'})],[],[],NOW);
  assert.equal(r.queue.length,1);assert.equal(r.queue[0].attempts,1);assert.equal(r.queue[0].due,NOW+7200000);
  assert.equal(s.integrity(job({http_status:404})), 'closed');assert.equal(s.integrity(job({http_status:410})), 'closed');
  assert.equal(s.integrity(job({http_status:403})), 'access_denied');assert.equal(s.integrity(job({verify_reason:'expired_deadline'})), 'closed');
  for(const status of [403,404,410])assert.equal(s.reconcile([job({http_status:status})],[],[],NOW).queue.length,0);
});
test('retry budget, deferred due times, missing records and queue capacity are bounded',()=>{
  const j=job({verify_reason:'request_failed'}),first=s.reconcile([j],[],[],NOW);
  const deferred=s.reconcile([],[first.jobs[0]],first.queue,NOW+60000);
  assert.equal(deferred.queue[0].due,first.queue[0].due);assert.equal(deferred.queue[0].attempts,1);
  assert.equal(deferred.jobs[0].verified,false);assert.equal(deferred.jobs[0].integrity,'uncertain');
  const second=s.reconcile([j],[],first.queue,NOW+4000000),third=s.reconcile([j],[],second.queue,NOW+(12 * 1000000));
  assert.equal(third.queue.length,0);assert.equal(third.jobs[0].retry_state,'exhausted_uncertain');
  assert.equal(s.reconcile([j],[],first.queue,NOW+8*(24 * 60 * 60 * 1000)).queue.length,0);
  const many=s.reconcile(Array.from({length:220},(_,i)=>job({verify_reason:'timeout',apply_url:`https://careers.wipro.com/job/test/${i}`})),[],[],NOW);
  assert.equal(many.queue.length,200);assert.equal(many.jobs.filter(j=>j.retry_state==='capacity_deferred_uncertain').length,20);
});
test('source route allowlist and robots fail closed rather than using alternate endpoints',()=>{
  assert.ok(feeds.permittedUrl(job().apply_url));assert.ok(feeds.permittedUrl('https://careers.hcltech.com/job/Full-Stack-Developer/161519-en_US/'));
  for(const url of ['http://careers.wipro.com/job/test','https://careers.wipro.com/services/jobs','https://careers.wipro.com/login',
    'https://u:p@careers.wipro.com/job/test','https://127.0.0.1/job/test','https://api.smartrecruiters.com/v1/internal/postings'])assert.equal(feeds.permittedUrl(url),false);
  assert.equal(feeds.robotsAllow('User-agent: *\nDisallow: /services/\n','/services/jobs'),false);
  assert.equal(feeds.robotsAllow('User-agent: *\nAllow: /\nUser-agent: GPTBot\nDisallow: /\n','/job/test'),false);
  assert.equal(feeds.robotsAllow('User-agent: *\nDisallow: /job/\nAllow: /job/public/\n','/job/public/test'),true);
});
test('JobPosting @graph uses explicit location, never footer mentions',()=>{
  const html='<script type="application/ld+json">'+JSON.stringify({'@graph':[{'@type':'JobPosting',title:'Python Developer',
    jobLocation:{address:{addressLocality:'Chennai'}},identifier:{value:'REQ1'},datePosted:'2026-10-08'}]})+'</script><main><h1>Python Developer</h1>Responsibilities Apply now</main>';
  const j=feeds.parseDetail(html,job().apply_url,{name:'Wipro',source:'wipro.com'});
  assert.equal(j.city,'Chennai');assert.equal(j.requisition_id,'REQ1');assert.equal(j.verified,false);
  assert.equal(feeds.parseDetail('<h1>Developer</h1><main>Responsibilities Apply now</main><footer>Chennai office</footer>',job().apply_url,{name:'Wipro',source:'wipro.com'}),null);
});
test('verification requires matching job evidence; mocked statuses never hit network',async()=>{
  const original=feeds.publicRead;
  try{
    feeds.publicRead=async()=>({status:200,url:job().apply_url,body:'<main><h1>Backend Developer</h1>Job description Responsibilities Apply now</main>'});
    assert.equal((await check(job(),NOW+1)).verified,true);
    feeds.publicRead=async()=>({status:200,url:job().apply_url,body:'<h1>Careers</h1>Apply now'});
    assert.equal((await check(job(),NOW+1)).verified,false);
    for(const status of [403,404,429,503]){feeds.publicRead=async()=>({status,url:job().apply_url,body:''});const j=await check(job(),NOW+1);assert.equal(j.verified,false);assert.equal(j.http_status,status);}
    feeds.publicRead=async()=>{throw Error('network unavailable');};assert.equal((await check(job(),NOW+1)).verify_reason,'request_failed');
    assert.equal((await check(job({deadline:'2000-01-01'}),NOW+1)).verify_reason,'expired_deadline');
  }finally{feeds.publicRead=original;}
});
