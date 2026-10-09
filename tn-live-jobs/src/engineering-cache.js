'use strict';
// Run-local GET snapshot reuse. Never cache failures, redirects or private routes.
function createRunReader(read, permitted, options={}) {
  const ttl = options.ttl ?? 10000, maxEntries = options.maxEntries ?? 32,
    maxBytes = options.maxBytes ?? 8000000, clock = options.clock || Date.now;
  if(!(ttl>0)||!Number.isInteger(maxEntries)||maxEntries<1||!(maxBytes>0)) throw Error('Invalid read-cache bounds');
  const entries = new Map(), pending = new Map(); let bytes=0;
  function remove(key) { const value=entries.get(key); if(value) bytes-=value.size; entries.delete(key); }
  return async function(url, deadline) {
    if(!permitted(url)) throw Error('unapproved public URL');
    if(clock()>=deadline) throw Error('source deadline exceeded');
    for(const [key,value] of entries) if(clock()-value.at>=ttl) remove(key);
    const hit=entries.get(url); if(hit) return {...hit.response};
    // Serial production callers; coalesce matching URLs only, no new host concurrency.
    if(pending.has(url)) return {...await pending.get(url)};
    const work=(async()=>{
      const r=await read(url,deadline), at=clock();
      const response={...r,fetched_at:r.fetched_at||new Date(at).toISOString()};
      if(r.status===200&&!r.redirected&&typeof r.body==='string') {
        const size=Buffer.byteLength(r.body,'utf8');
        if(size<=maxBytes) {
          while(entries.size>=maxEntries || bytes+size>maxBytes) remove(entries.keys().next().value);
          entries.set(url,{at,size,response}); bytes+=size;
        }
      }
      return response;
    })();
    pending.set(url,work);
    try { return {...await work}; } finally { pending.delete(url); }
  };
}
module.exports={createRunReader};