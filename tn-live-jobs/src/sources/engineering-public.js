'use strict';
// Bounded public-page reads only. No browser stealth, account endpoints or hidden services.
const cheerio = require('cheerio');
const { makeJob } = require('../scraper');
const { city } = require('../engineering-search');
const AGENT = 'MyJobSearch/1.0';
const CAREERS = [
  { host: 'careers.hcltech.com', name: 'HCLTech', source: 'hcltech.com' },
  { host: 'careers.wipro.com', name: 'Wipro', source: 'wipro.com' },
];
const ATS = [{ id: 'Freshworks', name: 'Freshworks', source: 'freshworks.com' },
  { id: 'BoschGroup', name: 'Robert Bosch India', source: 'bosch.in' },
  { id: 'AveryDennison', name: 'Avery Dennison', source: 'averydennison.com' }];
const ALLOWED = new Set([...CAREERS.map(c => c.host), 'api.smartrecruiters.com', 'jobs.smartrecruiters.com']);
const last = new Map(), robotCache = new Map();
function permittedUrl(value) { try { const u = new URL(value);
  if(u.protocol!=='https:'||u.username||u.password||u.port||!ALLOWED.has(u.hostname))return false;
  if(u.pathname==='/robots.txt')return true;
  if(u.hostname==='api.smartrecruiters.com')return /^\/v1\/companies\/(Freshworks|BoschGroup|AveryDennison)\/postings$/.test(u.pathname);
  if(u.hostname==='jobs.smartrecruiters.com')return /^\/(Freshworks|BoschGroup|AveryDennison)\/[^/]+$/.test(u.pathname);
  return /^\/(search\/|job\/(?:[^/]+\/){0,2}[^/]+\/?)$/.test(u.pathname);
} catch { return false; } }
async function rawRead(url, deadline = Date.now()+20000) {
  if (!permittedUrl(url)) throw Error('URL not in permitted public route allowlist');
  const u = new URL(url), delay = Math.max(0,1500-(Date.now()-(last.get(u.host)||0)));
  if (Date.now()+delay >= deadline) throw Error('source deadline exceeded');
  if (delay) await new Promise(r => setTimeout(r,delay)); last.set(u.host,Date.now());
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(),Math.min(15000,deadline-Date.now()));
  // SSRF audit: u passed the exact HTTPS host/public-route allowlist above.
  // Credentials/ports and redirect following are forbidden; arbitrary URLs fail closed.
  try { const r = await fetch(u,{ redirect:'manual', signal:controller.signal, headers:{'user-agent':AGENT, accept:'text/html,application/json,text/plain'} });
    // No redirects to login, another host, or a blocked route. Caller must review redirects separately.
    if (r.status >= 300 && r.status < 400) return { status:r.status, url, body:'', retry_after:r.headers.get('retry-after'), redirected:true };
    if (Number(r.headers.get('content-length')) > 2000000) throw Error('page too large');
    const reader = r.body.getReader(); const parts=[]; let size=0;
    while (true) { const {value,done} = await reader.read(); if(done) break; size+=value.length; if(size>2000000){await reader.cancel();throw Error('page too large');} parts.push(Buffer.from(value)); }
    return { status:r.status, url, body:Buffer.concat(parts).toString('utf8'), retry_after:r.headers.get('retry-after') };
  } finally { clearTimeout(timer); }
}
// Robots patterns are data, never executable regular expressions. A single-star
// backtracking matcher has bounded polynomial work, unlike constructed RegExp.
function robotsMatch(rule, pathname, budget) {
  const anchored = rule.endsWith('$'), pattern = anchored ? rule.slice(0,-1) : rule;
  let p=0, s=0, star=-1, retry=0;
  while(s < pathname.length) {
    if(--budget.remaining < 0) throw Error('robots policy matching budget exceeded');
    if(p === pattern.length) { if(!anchored) return true; }
    else if(pattern[p] === '*') { star=p++; retry=s; continue; }
    else if(pattern[p] === pathname[s]) { p++; s++; continue; }
    if(star < 0) return false;
    p=star+1; s=++retry;
  }
  while(pattern[p] === '*') p++;
  return p === pattern.length;
}
function robotsAllow(body, pathname) {
  // Fail closed on oversized policies/paths so even polynomial matching is bounded.
  if(body.length > 65536 || pathname.length > 8192) return false;
  const budget={remaining:262144};
  const groups=[]; let agents=[],rules=[],started=false;
  function save(){ if(agents.length) groups.push({agents,rules}); agents=[];rules=[];started=false; }
  for(const line of body.split(/\r?\n/)){ const clean=line.split('#')[0].trim(); const m=clean.match(/^([^:]+):\s*(.*)$/); if(!m)continue;
    const key=m[1].toLowerCase(),value=m[2].trim();
    if(key==='user-agent'){if(started)save();agents.push(value.toLowerCase());}
    else if(key==='allow'||key==='disallow'){started=true;rules.push({allow:key==='allow',path:value});} }
  save();
  // Conservative: honor both our advertised crawler identity and GPTBot exclusions.
  const specific=groups.filter(g=>g.agents.some(a=>a!=='*'&&(AGENT.toLowerCase().includes(a)||a==='gptbot')));
  const applicable=[...specific,...groups.filter(g=>g.agents.includes('*'))];
  for(const g of applicable){ const matched=g.rules.filter(r=>r.path&&robotsMatch(r.path, pathname, budget)).sort((a,b)=>b.path.length-a.path.length||Number(b.allow)-Number(a.allow));
    if(matched.length&&!matched[0].allow)return false; }
  return true;
}
async function publicRead(url,deadline){ if(!permittedUrl(url))throw Error('unapproved public URL'); const u=new URL(url);
  // SmartRecruiters Posting API is a documented public feed; career HTML still requires robots.
  if(u.host!=='api.smartrecruiters.com'){
    if(!robotCache.has(u.host)){const r=await rawRead(`https://${u.host}/robots.txt`,deadline);if(r.status!==200)throw Error('robots policy unavailable; source excluded');robotCache.set(u.host,r.body);}
    if(!robotsAllow(robotCache.get(u.host),u.pathname+u.search))throw Error('robots disallows this route; source excluded'); }
  return rawRead(url,deadline);
}
function parseDetail(html,url,company){ const $=cheerio.load(html); let posting=null;
  function walk(v){if(!v||typeof v!=='object')return;if(Array.isArray(v)){v.forEach(walk);return;}if(v['@type']==='JobPosting')posting=v;if(v['@graph'])walk(v['@graph']);}
  $('script[type="application/ld+json"]').each((_,el)=>{try{walk(JSON.parse($(el).text()));}catch{}});
  const title = posting?.title || $('h1').first().text().trim();
  const body=$('main').text()||$('body').text(); const loc=posting?.jobLocation;
  const locations=(Array.isArray(loc)?loc:[loc]).filter(Boolean).map(l=>[l.address?.addressLocality,l.address?.addressRegion].filter(Boolean).join(', '));
  const locationText=locations.join(' ') || $('[itemprop="addressLocality"]').first().text() || (body.match(/Location\s*:\s*([^\n]{1,120})/i)?.[1] || '');
  const foundCity=city(locationText);
  if(!title||!foundCity||!/(responsibilities|qualifications|job description|apply now)/i.test(body))return null;
  const record = makeJob({title,company:company.name,apply_url:url,city:foundCity,location:locationText,
    description:posting?.description ? cheerio.load(posting.description).text().slice(0,1000) : body.replace(/\s+/g,' ').slice(0,1000),
    posted_at:posting?.datePosted||null,deadline:posting?.validThrough||null,source:company.source,source_type:'company'});
  return record ? { ...record, location: locationText, requisition_id: posting?.identifier?.value || null } : null;
}
async function scrapeCareer(company,ctx){const jobs=[],links=new Set();let pages=0;
  for(const c of ctx.cities){if(pages++>=4||Date.now()>ctx.deadline)break;
    const url=`https://${company.host}/search/?q=&locationsearch=${encodeURIComponent(c)}`;
    const r=await(ctx.read||publicRead)(url,ctx.deadline);if(r.status>=300){ctx.note(company.source,'unreachable',`public search HTTP ${r.status}; no alternate/bypass route`);break;}
    const $=cheerio.load(r.body);$('a[href]').each((_,el)=>{try{const u=new URL($(el).attr('href'),url);if(u.host===company.host&&/^\/job\//.test(u.pathname)&&permittedUrl(u.href))links.add(u.href);}catch{}});
  }
  for(const url of [...links].slice(0,Math.min(ctx.limit,12))){if(Date.now()>ctx.deadline)break;const r=await(ctx.read||publicRead)(url,ctx.deadline);if(r.status!==200)continue;const j=parseDetail(r.body,url,company);if(j)jobs.push(j);}
  ctx.note(company.source,jobs.length?'ok':'no_listings',jobs.length?`${jobs.length} public career records; pending verification`:'No readable public job links; JS/format may be unsupported, not proof of no openings');return jobs;
}
async function scrapeAts(company,ctx){const jobs=[];
  // Documented Posting API: https://developers.smartrecruiters.com/docs/posting-api
  for(let page=0;page<4&&Date.now()<ctx.deadline;page++){
    const url=`https://api.smartrecruiters.com/v1/companies/${company.id}/postings?limit=100&offset=${page*100}`;
    const r=await(ctx.read||publicRead)(url,ctx.deadline);if(r.status!==200)throw Error(`documented feed HTTP ${r.status}`);
    const data=JSON.parse(r.body),list=Array.isArray(data.content)?data.content:[];
    for(const p of list){const loc=[p.location?.city,p.location?.region,p.location?.fullLocation].filter(Boolean).join(' ');const c=city(loc);if(!c||!p.id||!p.name)continue;
      const j=makeJob({title:p.name,company:company.name,apply_url:`https://jobs.smartrecruiters.com/${company.id}/${p.id}`,city:c,
        posted_at:p.releasedDate||null,experience:p.experienceLevel?.label||null,source:company.source,source_type:'company',extra:loc});
      if(j)jobs.push({...j,location:loc,requisition_id:p.id});if(jobs.length>=ctx.limit)break;}
    if(jobs.length>=ctx.limit||list.length<100)break;
  }ctx.note(company.source,jobs.length?'ok':'no_listings',`${jobs.length} feed records; pending verification`);return jobs;
}
module.exports={id:'engineering-public',label:'Bounded official engineering feeds and public HCL/Wipro pages',tier:1,
  permittedUrl,rawRead,publicRead,robotsAllow,parseDetail,CAREERS,ATS,
  async scrape(ctx){const out=[];for(const c of [...CAREERS,...ATS]){if(Date.now()>ctx.deadline)break;try{out.push(...await(c.host?scrapeCareer(c,ctx):scrapeAts(c,ctx)));}catch(e){ctx.note(c.source,'unreachable',e.message);}}
    for(const site of ['cognizant.com','naukri.com','indeed.co.in','workday-cxs'])ctx.note(site,'skipped','No verified permitted automated route; native alerts/manual review instead');return out;}};
