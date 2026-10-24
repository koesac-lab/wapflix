const assert=require('node:assert/strict');
const Source=require('../stream-source.js');
const tests=[];const test=(name,fn)=>tests.push({name,fn});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function harness({duration=60,complete=false,generated=8,timeoutMs=10000}={}){
 const requests=[],sessions=new Map(),pendingChunks=[],pendingStarts=[],pendingPulses=[];
 let sequence=0;const config={holdChunks:false,holdStarts:false,holdPulses:false,badChunk:false,badMetadata:false,stopError:false};
 const response=(body,status=200)=>({ok:status>=200&&status<300,status,json:async()=>body});
 function create(){
  const n=++sequence,id='s'+n,nav='n'+n,count=Math.ceil(duration*8);
  const metadata={id,navigation_id:nav,revision:0,cols:240,rows:135,fps:8,chunk_frames:16,source_start:30,range_start:30,range_end:30+duration,
   state:'running',ready_frames:0,generated_chunks:0,total_frames:null,captions:{timebase:'source',cues:[]}};
  if(config.badMetadata)metadata.rows=999;
  const ready=complete?count:Math.min(generated*16,count);
  sessions.set(id,{metadata,ready,generated:Math.ceil(ready/16),complete,stopped:false});return metadata;
 }
 async function fetchImpl(url,options={}){
  const parsed=new URL(url),body=options.body?JSON.parse(options.body):undefined;
  requests.push({path:parsed.pathname,query:parsed.searchParams,body,options});
  if(parsed.pathname==='/api/start'){
   if(config.holdStarts)return new Promise(resolve=>pendingStarts.push(()=>resolve(response(create()))));
   return response(create());
  }
  if(parsed.pathname==='/api/navigation/stop'){
   if(config.stopError)return response({error:'Cannot stop worker'},503);
   for(const s of sessions.values())if(s.metadata.navigation_id===body.navigation_id)s.stopped=true;
   return response({stopped:true});
  }
  if(parsed.pathname==='/api/pulse'){
   const s=sessions.get(body.id);
   const data={...s.metadata,state:s.stopped?'stopped':s.complete?'complete':'running',ready_frames:s.ready,generated_chunks:s.generated,total_frames:s.complete?s.ready:null,retained_chunks:s.generated};
   if(config.holdPulses)return new Promise(resolve=>pendingPulses.push(()=>resolve(response(data))));
   return response(data);
  }
  if(parsed.pathname==='/api/chunk'){
   const s=sessions.get(parsed.searchParams.get('id')),n=Number(parsed.searchParams.get('n'));
   const deliver=()=>{
    if(n>=s.generated)return response(null,204);
    const frame=config.badChunk?'zz':'80'+'00'.repeat(4049);
    return response({version:1,layout:'lcd-1bit',encoding:'hex-msb',index:n,cols:240,rows:135,fps:8,source_start:30,start_frame:n*16,frames:Array(Math.min(16,s.ready-n*16)).fill(frame)});
   };
   if(config.holdChunks)return new Promise(resolve=>pendingChunks.push(()=>resolve(deliver())));
   return deliver();
  }
  return response({error:'Unexpected path'},404);
 }
 const source=new Source({token:'capability',baseUrl:'http://127.0.0.1:8101/',fetchImpl,timeoutMs});
 return {source,requests,sessions,config,pendingChunks,pendingStarts,pendingPulses};
}

test('constructor has no network or global timer side effects',async()=>{
 const h=harness();assert.equal(h.requests.length,0);assert.equal(h.source.state,'idle');assert.equal(h.source.frameAt(30),null);
 await assert.rejects(async()=>new Source({fetchImpl:()=>{}}),/token/);
});
test('start, authenticated fetch, frame decoding metadata and stop',async()=>{
 const h=harness(),m=await h.source.start();assert.equal(h.source.state,'ready');assert.equal(m.source_start,30);
 await h.source.poll();const frame=h.source.frameAt(30.125);
 assert.equal(frame.frameIndex,1);assert.equal(frame.sourceTime,30.125);assert.equal(frame.hex.length,8100);
 assert.equal(h.source.bufferedUntil(30),38);assert.equal(h.source.retainedChunks,4);
 assert(h.requests.every(r=>r.options.headers['X-Wapflix-Test']==='capability'));
 await h.source.stop();assert.equal(h.source.state,'stopped');assert.equal(h.source.retainedChunks,0);assert.equal(h.source.frameAt(30),null);
 assert(h.sessions.get('s1').stopped);
});
test('rolling cache never exceeds one previous plus four ahead',async()=>{
 const h=harness();await h.source.start();await h.source.poll();await h.source.poll({sourceTime:34});
 assert.equal(h.source.retainedChunks,5);assert.equal(h.source.frameAt(30),null);assert(h.source.frameAt(34));
 await h.source.poll({sourceTime:38});assert(h.source.retainedChunks<=5);await h.source.stop();
});
test('paused startup prefills, then parks on subsequent pulse',async()=>{
 const h=harness();await h.source.start();await h.source.poll({sourceTime:30,paused:true});
 assert.equal(h.requests.filter(r=>r.path==='/api/pulse').at(-1).body.paused,false);
 await h.source.poll({sourceTime:30,paused:true});assert.equal(h.requests.filter(r=>r.path==='/api/pulse').at(-1).body.paused,true);await h.source.stop();
});
// 5A.2R1: startup readiness belongs to a generation, not retained chunk zero.
test('pause remains honoured after initial chunks are evicted',async()=>{
 const h=harness();
 try{
  await h.source.start();await h.source.poll();await h.source.poll({sourceTime:34});
  assert.equal(h.source.frameAt(30),null,'chunk zero must actually be evicted');
  assert.equal(h.source.retainedChunks,5);
  await h.source.poll({sourceTime:34,paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse').at(-1).body.paused,true);
 }finally{await h.source.stop();}
});
test('readiness survives repeated rolling-window eviction without retaining old frames',async()=>{
 const h=harness();
 try{
  await h.source.start();await h.source.poll();
  for(const sourceTime of [34,36,38,40]){
   await h.source.poll({sourceTime});await h.source.poll({sourceTime,paused:true});
   assert.equal(h.requests.filter(r=>r.path==='/api/pulse').at(-1).body.paused,true);
   assert(h.source.retainedChunks<=5);assert.equal(h.source.frameAt(30),null);
  }
 }finally{await h.source.stop();}
});
test('Stop and Start reset readiness and preserve paused-start prefill',async()=>{
 const h=harness();
 try{
  await h.source.start();await h.source.poll();await h.source.stop();
  const next=await h.source.start();await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse'&&r.body.id===next.id).at(-1).body.paused,false);
  await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse'&&r.body.id===next.id).at(-1).body.paused,true);
 }finally{await h.source.stop();}
});
test('replacement Start resets readiness without requiring an explicit Stop',async()=>{
 const h=harness();
 try{
  await h.source.start();await h.source.poll();await h.source.poll({sourceTime:34});
  const next=await h.source.start();assert(h.sessions.get('s1').stopped);
  await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse'&&r.body.id===next.id).at(-1).body.paused,false);
  await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse'&&r.body.id===next.id).at(-1).body.paused,true);
 }finally{await h.source.stop();}
});
test('a completed one-frame clip becomes ready without a second chunk',async()=>{
 const h=harness({duration:.125,complete:true});
 try{
  await h.source.start();await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse').at(-1).body.paused,false);
  assert.equal(h.source.retainedChunks,1);assert.equal(h.source.frameAt(30.125).frameIndex,0);
  await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse').at(-1).body.paused,true);
 }finally{await h.source.stop();}
});
test('a late chunk from an old generation cannot warm a replacement',async()=>{
 const h=harness();
 try{
  await h.source.start();h.config.holdChunks=true;
  const pending=h.source.poll({paused:true});await settle();assert.equal(h.pendingChunks.length,1);
  const next=await h.source.start();h.config.holdChunks=false;
  h.pendingChunks.shift()();assert.equal(await pending,null);await settle();
  await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse'&&r.body.id===next.id).at(-1).body.paused,false);
  await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse'&&r.body.id===next.id).at(-1).body.paused,true);
 }finally{await h.source.stop();}
});
test('a late status from a warmed generation cannot warm a replacement',async()=>{
 const h=harness();
 try{
  await h.source.start();await h.source.poll();h.config.holdPulses=true;
  const pending=h.source.poll({paused:true});assert.equal(h.pendingPulses.length,1);
  const next=await h.source.start();h.config.holdPulses=false;
  h.pendingPulses.shift()();assert.equal(await pending,null);await settle();
  await h.source.poll({paused:true});
  assert.equal(h.requests.filter(r=>r.path==='/api/pulse'&&r.body.id===next.id).at(-1).body.paused,false);
 }finally{await h.source.stop();}
});

test('concurrent polls coalesce rather than duplicating downloads',async()=>{
 const h=harness();await h.source.start();h.config.holdPulses=true;
 const a=h.source.poll(),b=h.source.poll();assert.equal(a,b);assert.equal(h.pendingPulses.length,1);
 h.pendingPulses.shift()();await a;assert.equal(h.requests.filter(r=>r.path==='/api/pulse').length,1);await h.source.stop();
});
test('late chunk after Stop cannot repopulate the cache',async()=>{
 const h=harness();await h.source.start();h.config.holdChunks=true;const polling=h.source.poll();await settle();
 assert.equal(h.pendingChunks.length,1);await h.source.stop();h.pendingChunks.shift()();assert.equal(await polling,null);
 assert.equal(h.source.retainedChunks,0);assert.equal(h.source.metadata,null);assert.equal(h.source.state,'stopped');
});
test('late status after replacement cannot replace new metadata',async()=>{
 const h=harness();await h.source.start();h.config.holdPulses=true;const polling=h.source.poll();
 h.config.holdPulses=false;const next=await h.source.start();assert.equal(next.id,'s2');h.pendingPulses.shift()();await polling;
 assert.equal(h.source.metadata.id,'s2');assert.equal(h.source.status,null);assert(h.sessions.get('s1').stopped);await h.source.stop();
});
test('Stop while Start is in flight releases the acknowledged navigation',async()=>{
 const h=harness();h.config.holdStarts=true;const starting=h.source.start();await settle();
 const stopping=h.source.stop();h.pendingStarts.shift()();assert.equal(await starting,null);await stopping;
 assert.equal(h.source.state,'stopped');assert(h.sessions.get('s1').stopped);assert.equal(h.source.metadata,null);
});
test('a newer Start waits for old Start cleanup and owns only its session',async()=>{
 const h=harness();h.config.holdStarts=true;const old=h.source.start();await settle();const latest=h.source.start();
 h.pendingStarts.shift()();await old;await settle();assert(h.sessions.get('s1').stopped);assert.equal(h.pendingStarts.length,1);
 h.pendingStarts.shift()();const data=await latest;assert.equal(data.id,'s2');assert.equal(h.source.metadata.id,'s2');await h.source.stop();
});
test('malformed chunks fail visibly and can be explicitly stopped',async()=>{
 const h=harness();await h.source.start();h.config.badChunk=true;await assert.rejects(h.source.poll(),/Invalid LCD chunk/);
 assert.equal(h.source.state,'error');assert(h.source.error);assert.equal(h.source.retainedChunks,0);await h.source.stop();assert(h.sessions.get('s1').stopped);
});
test('invalid start metadata releases its acquired navigation',async()=>{
 const h=harness();h.config.badMetadata=true;await assert.rejects(h.source.start(),/Invalid M4A stream metadata/);
 assert.equal(h.source.state,'error');assert(h.sessions.get('s1').stopped);await h.source.stop();
});
test('failed stop preserves ownership and blocks a new start until cleanup works',async()=>{
 const h=harness();await h.source.start();h.config.stopError=true;await assert.rejects(h.source.stop(),/Cannot stop worker/);
 await assert.rejects(h.source.start(),/Cannot stop worker/);assert.equal(h.requests.filter(r=>r.path==='/api/start').length,1);
 h.config.stopError=false;await h.source.stop();assert(h.sessions.get('s1').stopped);await h.source.start();assert.equal(h.source.metadata.id,'s2');await h.source.stop();
});
test('partial final chunk and end-frame lookup are handled',async()=>{
 const h=harness({duration:2.625,complete:true});await h.source.start();await h.source.poll();
 assert.equal(h.source.status.total_frames,21);assert.equal(h.source.retainedChunks,2);
 assert.equal(h.source.frameAt(32.625).frameIndex,20);assert.equal(h.source.bufferedUntil(30),32.625);await h.source.stop();
});
test('invalid time and paused values do not issue requests',async()=>{
 const h=harness();await h.source.start();const count=h.requests.length;
 await assert.rejects(h.source.poll({sourceTime:NaN}),/Source time/);await assert.rejects(h.source.poll({sourceTime:29}),/Source time/);
 await assert.rejects(h.source.poll({paused:'yes'}),/boolean/);assert.equal(h.requests.length,count);await h.source.stop();
});
test('request timeouts prevent a lost start from wedging the lifecycle queue',async()=>{
 const h=harness({timeoutMs:15});h.config.holdStarts=true;
 await assert.rejects(h.source.start(),/timed out/);assert.equal(h.source.state,'error');
 await h.source.stop();assert.equal(h.source.state,'stopped');
 h.config.holdStarts=false;await h.source.start();assert.equal(h.source.state,'ready');await h.source.stop();
});
test('missing chunks report no frame without skipping a buffer gap',async()=>{
 const h=harness();await h.source.start();h.config.holdChunks=true;const pending=h.source.poll();await settle();
 assert.equal(h.source.frameAt(30),null);assert.equal(h.source.bufferedUntil(30),30);
 await h.source.stop();h.pendingChunks.shift()();await pending;
});
test('browser cross-origin API configuration is refused',async()=>{
 const old=global.location;global.location={href:'http://192.168.1.10:8102/'};
 try{assert.throws(()=>new Source({token:'t',baseUrl:'http://192.168.1.10:8101/',fetchImpl:()=>{}}),/same-origin/);}
 finally{if(old===undefined)delete global.location;else global.location=old;}
});
(async()=>{
 let failed=0;
 for(const {name,fn} of tests){try{await fn();console.log('PASS '+name);}catch(error){failed++;console.error('FAIL '+name+'\n'+error.stack);}}
 if(failed)process.exitCode=1;else console.log(tests.length+' standalone adapter tests passed.');
})();
