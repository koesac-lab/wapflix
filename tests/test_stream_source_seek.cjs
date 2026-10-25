// 5A.6B prerequisite: /seek contract, ownership and cancellation, controlled HTTP.
const {test}=require('node:test'),assert=require('node:assert/strict');
const Source=require('../stream-source.js');
const {transport,settle}=require('./helpers/fenced_seek_harness.cjs');
function harness(options){const h=transport(options);h.source=new Source({token:'test-only',baseUrl:'http://localhost/',fetchImpl:h.fetchImpl,timeoutMs:h.timeoutMs});return h;}
test('requires ready metadata and finite numeric input before transport',async()=>{
 const h=harness();await assert.rejects(h.source.seek(40),/active stream/);await h.source.start();
 for(const v of [NaN,Infinity,-Infinity,'40',null])await assert.rejects(h.source.seek(v),/finite/);
 assert.equal(h.count('/api/seek'),0);await h.source.stop();
});
test('seek sends source destination, retains navigation, does not Start or cancel',async()=>{
 const h=harness();const initial=await h.source.start();await h.source.poll();const result=await h.source.seek(40.137);
 assert.equal(result.destination,40.125);assert.equal(result.frame,81);assert.equal(result.metadata.source_start,40.125);
 assert.equal(result.metadata.navigation_id,initial.navigation_id);assert.notEqual(result.metadata.id,initial.id);
 assert.deepEqual(h.requests.find(r=>r.path==='/api/seek').body,{navigation_id:initial.navigation_id,revision:1,position:40.137});
 assert.equal(h.count('/api/start'),1);assert.equal(h.count('/api/control/cancel'),0);assert.equal(h.source.retainedChunks,0);
 await h.source.poll({paused:true});assert.equal(h.source.frameAt(40.125).frameIndex,0);
 await h.source.poll({paused:true});const pulses=h.requests.filter(r=>r.path==='/api/pulse');
 assert.equal(pulses.at(-2).body.paused,false);assert.equal(pulses.at(-1).body.paused,true);await h.source.stop();
});
test('clamps bounds to last renderable frame, including fractional range',async()=>{
 const h=harness({start:30.03,end:30.34});await h.source.start();
 assert.equal((await h.source.seek(-100)).destination,30.03);
 assert.equal((await h.source.seek(100)).destination,30.28);await h.source.stop();
});
test('backward seeking uses original range rather than replacement source_start',async()=>{
 const h=harness();await h.source.start();await h.source.seek(70);const r=await h.source.seek(35);
 assert.equal(r.destination,35);assert.equal(r.metadata.revision,2);assert.equal(r.metadata.range_start,30);await h.source.stop();
});
test('concurrent seek fails closed but sequential revisions increase',async()=>{
 const h=harness();await h.source.start();const first=h.source.seek(40);await assert.rejects(h.source.seek(50),/active stream/);
 await first;await h.source.seek(50);assert.deepEqual(h.requests.filter(r=>r.path==='/api/seek').map(r=>r.body.revision),[1,2]);await h.source.stop();
});
for(const kind of ['pulses','chunks'])test('seek invalidates delayed old '+kind,async()=>{
 const h=harness();await h.source.start();h.config[kind==='pulses'?'holdPulses':'holdChunks']=true;
 const old=h.source.poll();await settle();assert.equal(h.pending[kind].length,1);
 const seeking=h.source.seek(40);assert.equal(await old,null);await seeking;h.release(kind);await settle();
 assert.equal(h.source.retainedChunks,0);h.config.holdPulses=false;h.config.holdChunks=false;
 await h.source.poll();assert.equal(h.source.frameAt(40).sourceTime,40);await h.source.stop();
});
test('Stop fences pending seek before delayed publication, without awaiting response',async()=>{
 const h=harness();await h.source.start();h.config.holdSeeks=true;const seeking=h.source.seek(40);await settle();
 await h.source.stop();assert.equal(await seeking,null);assert.equal(h.source.state,'stopped');assert.equal(h.active,null);
 h.release('seeks');await settle();assert.equal(h.active,null);assert.equal(h.source.metadata,null);
});
test('new Start fences pending seek and late reply cannot replace its session',async()=>{
 const h=harness();await h.source.start();h.config.holdSeeks=true;const old=h.source.seek(40);await settle();
 const meta=await h.source.start();assert.equal(await old,null);h.release('seeks');await settle();
 assert.equal(h.source.metadata.id,meta.id);assert.equal(h.active.id,meta.id);await h.source.stop();
});
for(const reason of ['navigation','revision','destination','range'])test('rejects mismatched seek '+reason+' and cleans owner',async()=>{
 const h=harness();await h.source.start();h.config.badSeek=reason;await assert.rejects(h.source.seek(40),/seek identity/);
 assert.equal(h.source.state,'error');assert.equal(h.active,null);assert.equal(h.count('/api/start'),1);await h.source.stop();
});
test('latest 409 surfaces as error with no automatic retry',async()=>{
 const h=harness();await h.source.start();h.config.seekError='stale_seek';await assert.rejects(h.source.seek(40),e=>e.status===409);
 assert.equal(h.source.state,'error');assert.equal(h.count('/api/seek'),1);assert.equal(h.count('/api/start'),1);await h.source.stop();
});
test('timeout cleans owner and late seek cannot publish',async()=>{
 const h=harness({timeoutMs:25});await h.source.start();h.config.holdSeeks=true;
 await assert.rejects(h.source.seek(40),e=>e.name==='TimeoutError');h.release('seeks');await settle();assert.equal(h.active,null);await h.source.stop();
});
test('failed cleanup stays owned and blocks replacement until explicit recovery',async()=>{
 const h=harness();await h.source.start();h.config.seekError='stale_seek';h.config.cancelError=true;
 await assert.rejects(h.source.seek(40),e=>e.cleanupError?.code==='cleanup_unconfirmed');
 await assert.rejects(h.source.start(),/cleanup_unconfirmed/);assert.equal(h.count('/api/start'),1);
 h.config.cancelError=false;h.config.seekError=null;await h.source.stop();await h.source.start();assert.equal(h.count('/api/start'),2);await h.source.stop();
});
test('fractional requests are snapped once by server, not twice by client',async()=>{
 const h=harness({start:30.1,end:90.1});await h.source.start();
 for(const request of [30.2,35.2,40.3,60.8,90.1]){
  const result=await h.source.seek(request),position=h.requests.filter(r=>r.path==='/api/seek').at(-1).body.position;
  assert.equal(result.metadata.source_start,30.1+Math.floor((position-30.1)*8)/8);
  assert.ok(result.destination>=30.1&&result.destination<90.1);
 }
 await h.source.stop();
});
