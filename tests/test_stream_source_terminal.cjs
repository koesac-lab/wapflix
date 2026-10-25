// Narrow regression for explicit terminal reason propagation in the real adapter.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const Source=require('../stream-source.js');
const m={id:'s',navigation_id:'n',cols:8,rows:1,fps:8,chunk_frames:16,source_start:30,range_start:30,range_end:90};
function seeded(){const s=new Source({token:'test-only',fetchImpl:async()=>{throw Error('unused');}});s._metadata=m;s._state='ready';return s;}
test('explicit error status preserves a conversion-specific code',async()=>{
  const s=seeded();s._api=async()=>({state:'error',error:'Conversion failed; check server terminal.'});
  await assert.rejects(s.poll(),e=>e.code==='conversion_failed'&&/Conversion failed/.test(e.message));assert.equal(s.state,'error');
});
test('missing conversion detail still supplies structured conversion failure',async()=>{
  const s=seeded();s._api=async()=>({state:'error'});await assert.rejects(s.poll(),e=>e.code==='conversion_failed');
});
test('stopped status remains unknown, never invented expiry',async()=>{
  const s=seeded();s._api=async()=>({state:'stopped'});await assert.rejects(s.poll(),e=>e.code===undefined&&!/expired/i.test(e.message));
});
test('HTTP structured code passes through unchanged',async()=>{
  const s=seeded();const error=Object.assign(Error('not found'),{status:404,code:'session_not_found'});s._api=async()=>{throw error;};
  await assert.rejects(s.poll(),e=>e===error);assert.equal(s.error,error);
});
test('verified control expiry passes through but is not inferred from other statuses',async()=>{
  const s=seeded();const error=Object.assign(Error('verified'),{code:'client_expired'});s._api=async()=>{throw error;};
  await assert.rejects(s.poll(),e=>e.code==='client_expired');
});
test('transport timeout remains its original error',async()=>{
  const s=seeded();const error=Object.assign(Error('deadline'),{name:'TimeoutError'});s._api=async()=>{throw error;};await assert.rejects(s.poll(),e=>e===error);
});
test('stale error-status response after invalidation cannot set a new terminal reason',async()=>{
  const s=seeded();let resolve;s._api=()=>new Promise(r=>resolve=r);const pending=s.poll();s._invalidate('stopped');
  resolve({state:'error',error:'old conversion'});assert.equal(await pending,null);assert.equal(s.state,'stopped');assert.equal(s.error,null);
});
test('normal running status remains valid without terminal classification',async()=>{
  const s=seeded();s._api=async()=>({...m,state:'running',ready_frames:0,generated_chunks:0,total_frames:null});
  const status=await s.poll();assert.equal(status.state,'running');assert.equal(s.state,'ready');assert.equal(s.error,null);
});
