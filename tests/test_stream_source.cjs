const assert=require('node:assert/strict');
const Source=require('../stream-source.js');
const tests=[];const test=(name,fn)=>tests.push({name,fn});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function harness({duration=60,complete=false,generated=8,timeoutMs=10000}={}){
 const requests=[],sessions=new Map(),clients=new Map(),pendingChunks=[],pendingStarts=[],pendingPulses=[],pendingOpens=[],pendingCancels=[];
 let sequence=0,clientSequence=0;const config={holdChunks:false,holdStarts:false,holdPulses:false,badChunk:false,badMetadata:false,stopError:false,holdOpens:false,holdCancels:false,badProtocol:false,badIdentity:false,badCancel:false,startError:null};
 const response=(body,status=200)=>({ok:status>=200&&status<300,status,json:async()=>body});
 function create(body){
  const n=++sequence,id='s'+n,nav='n'+n,count=Math.ceil(duration*8);
  const metadata={id,navigation_id:nav,revision:0,cols:240,rows:135,fps:8,chunk_frames:16,source_start:30,range_start:30,range_end:30+duration,
   state:'running',ready_frames:0,generated_chunks:0,total_frames:null,captions:{timebase:'source',cues:[]}};
  Object.assign(metadata,{control_protocol:'start-fence-v1',control_client_id:body.control_client_id,start_revision:body.start_revision});
  if(config.badMetadata)metadata.rows=999;
  const ready=complete?count:Math.min(generated*16,count);
  sessions.set(id,{metadata,ready,generated:Math.ceil(ready/16),complete,stopped:false});return metadata;
 }
 async function fetchImpl(url,options={}){
  const parsed=new URL(url),body=options.body?JSON.parse(options.body):undefined;
  requests.push({path:parsed.pathname,query:parsed.searchParams,body,options});
  if(parsed.pathname==='/api/control/open'){
   const deliver=()=>{
    const id=(++clientSequence).toString(16).padStart(48,'0');clients.set(id,{cancelled:0});
    return response({control_protocol:config.badProtocol?'legacy':'start-fence-v1',control_client_id:id,control_lease_seconds:60});
   };
   if(config.holdOpens)return new Promise(resolve=>pendingOpens.push(()=>resolve(deliver())));
   return deliver();
  }
  if(parsed.pathname==='/api/control/cancel'){
   const client=clients.get(body.control_client_id);
   if(!client)return response({error:'Gone',code:'control_client_gone'},404);
   client.cancelled=Math.max(client.cancelled,body.cancel_through);
   const deliver=()=>{
    if(config.stopError)return response({error:'Cannot stop worker',code:'cleanup_unconfirmed',fence_recorded:true,cleanup:'unconfirmed'},503);
    for(const s of sessions.values())if(s.metadata.control_client_id===body.control_client_id&&s.metadata.start_revision<=body.cancel_through)s.stopped=true;
    return response(config.badCancel?{fence_recorded:true,cleanup:'unconfirmed'}:{fence_recorded:true,cleanup:'confirmed'});
   };
   if(config.holdCancels)return new Promise(resolve=>pendingCancels.push(()=>resolve(deliver())));
   return deliver();
  }
  if(parsed.pathname==='/api/start'){
   const deliver=()=>{
    if(config.startError)return response({error:config.startError,code:config.startError},config.startError==='control_client_gone'?404:409);
    const client=clients.get(body.control_client_id);
    if(!client)return response({error:'Gone',code:'control_client_gone'},404);
    if(body.start_revision<=client.cancelled)return response({error:'Cancelled',code:'cancelled_start'},409);
    const data=create(body);
    return response(config.badIdentity?{...data,control_client_id:'f'.repeat(48),navigation_id:'foreign'}:data);
   };
   if(config.holdStarts)return new Promise(resolve=>pendingStarts.push(()=>resolve(deliver())));
   return deliver();
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
 return {source,requests,sessions,clients,config,pendingChunks,pendingStarts,pendingPulses,pendingOpens,pendingCancels,fetchImpl};
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
test('Stop while Start is in flight tombstones it before acknowledgement',async()=>{
 const h=harness();h.config.holdStarts=true;const starting=h.source.start();await settle();
 const stopping=h.source.stop();h.pendingStarts.shift()();assert.equal(await starting,null);await stopping;
 assert.equal(h.source.state,'stopped');assert.equal(h.sessions.size,0);assert.equal(h.source.metadata,null);
});
test('a newer Start waits for old Start cleanup and owns only its session',async()=>{
 const h=harness();h.config.holdStarts=true;const old=h.source.start();await settle();const latest=h.source.start();
 h.pendingStarts.shift()();await old;await settle();assert.equal(h.sessions.size,0);assert.equal(h.pendingStarts.length,1);
 h.pendingStarts.shift()();const data=await latest;assert.equal(data.id,'s1');assert.equal(h.source.metadata.id,'s1');await h.source.stop();
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

// R2C: delayed transports intentionally ignore AbortSignal; server fences, not
// browser fetch cancellation, are responsible for preventing late admission.
const deadline=promise=>Promise.race([promise,new Promise((_,reject)=>{
 const timer=setTimeout(()=>reject(Error('Lifecycle did not finish before acknowledgement')),500);
 promise.then(()=>clearTimeout(timer),()=>clearTimeout(timer));
})]);
test('registration precedes Start and increasing revisions reuse one handle',async()=>{
 const h=harness();await h.source.start();await h.source.start();
 const starts=h.requests.filter(r=>r.path==='/api/start');
 assert.equal(h.requests[0].path,'/api/control/open');assert.equal(h.clients.size,1);
 assert.equal(starts[0].body.start_revision,1);assert.equal(starts[1].body.start_revision,2);
 assert.equal(starts[0].body.control_client_id,starts[1].body.control_client_id);await h.source.stop();
});
test('Stop finishes before an unacknowledged Start responds',async()=>{
 const h=harness();h.config.holdStarts=true;const old=h.source.start();await settle();
 assert.equal(h.pendingStarts.length,1);await deadline(h.source.stop());assert.equal(await old,null);
 assert.equal(h.pendingStarts.length,1);assert.equal(h.source.state,'stopped');
 assert.equal(h.requests.filter(r=>r.path==='/api/control/cancel').length,1);
 h.pendingStarts.shift()();await settle();assert.equal(h.sessions.size,0);assert.equal(h.source.metadata,null);
});
test('a new Start fences a blocked old Start without waiting for its response',async()=>{
 const h=harness();h.config.holdStarts=true;const old=h.source.start();await settle();
 const latest=h.source.start();await settle();assert.equal(await old,null);assert.equal(h.pendingStarts.length,2);
 h.pendingStarts.pop()();const metadata=await deadline(latest);assert.equal(metadata.start_revision,2);
 h.pendingStarts.shift()();await settle();assert.equal(h.source.metadata.id,metadata.id);assert.equal(h.sessions.size,1);
 assert.equal(h.sessions.get(metadata.id).stopped,false);await h.source.stop();
});
test('timeout is fenced before a newer Start and delayed old handler cannot replace it',async()=>{
 const h=harness({timeoutMs:20});h.config.holdStarts=true;
 await assert.rejects(h.source.start(),/timed out/);assert(h.requests.some(r=>r.path==='/api/control/cancel'));
 h.config.holdStarts=false;const next=await h.source.start();h.pendingStarts.shift()();await settle();
 assert.equal(h.sessions.size,1);assert.equal(h.source.metadata.id,next.id);assert.equal(h.sessions.get(next.id).stopped,false);await h.source.stop();
});
test('Stop during registration never sends Start even if the registration replies late',async()=>{
 const h=harness();h.config.holdOpens=true;const old=h.source.start();await settle();
 await deadline(h.source.stop());assert.equal(await old,null);h.pendingOpens.shift()();await settle();
 assert.equal(h.requests.filter(r=>r.path==='/api/start').length,0);assert.equal(h.source.metadata,null);
 h.config.holdOpens=false;await h.source.start();assert.equal(h.clients.size,2);await h.source.stop();
});
test('unsupported control protocol is refused without weaker Start fallback',async()=>{
 const h=harness();h.config.badProtocol=true;await assert.rejects(h.source.start(),/Unsupported Start fencing/);
 assert.equal(h.requests.filter(r=>r.path==='/api/start').length,0);await h.source.stop();
});
test('invalid control handle and lease are refused before Start',async()=>{
 for(const mutation of [{control_client_id:'bad'},{control_client_id:123},{control_client_id:['a'.repeat(48)]},{control_lease_seconds:0}]){
  const h=harness();const source=new Source({token:'t',fetchImpl:async(url,options)=>{
   const result=await h.fetchImpl(url,options);if(new URL(url).pathname!=='/api/control/open')return result;
   return {...result,json:async()=>({...await result.json(),...mutation})};
  }});
  await assert.rejects(source.start(),/Unsupported Start fencing/);assert.equal(h.sessions.size,0);await source.stop();
 }
});
test('missing registration endpoint fails closed without sending Start',async()=>{
 const requests=[];const source=new Source({token:'t',fetchImpl:async(url)=>{
  requests.push(new URL(url).pathname);return {ok:false,status:404,json:async()=>({error:'Not found'})};
 }});
 await assert.rejects(source.start(),/Not found/);assert.deepEqual(requests,['/api/control/open']);await source.stop();
});
test('mismatched Start identity is scoped-cancelled without stopping a foreign navigation',async()=>{
 const h=harness();h.config.badIdentity=true;await assert.rejects(h.source.start(),/Invalid fenced Start identity/);
 assert(h.sessions.get('s1').stopped);assert(!h.requests.some(r=>r.path==='/api/navigation/stop'));
 const cancel=h.requests.find(r=>r.path==='/api/control/cancel');
 assert.equal(cancel.body.control_client_id,h.requests.find(r=>r.path==='/api/start').body.control_client_id);await h.source.stop();
});
test('malformed cancellation success retains the obligation and blocks replacement',async()=>{
 const h=harness();await h.source.start();h.config.badCancel=true;
 await assert.rejects(h.source.stop(),/Unconfirmed Start fence cleanup/);
 await assert.rejects(h.source.start(),/Unconfirmed Start fence cleanup/);
 assert.equal(h.requests.filter(r=>r.path==='/api/start').length,1);
 h.config.badCancel=false;await h.source.stop();await h.source.start();await h.source.stop();
});
test('generic cancel 404 is not accepted as proof of cleanup',async()=>{
 const h=harness();let broken=true;
 const source=new Source({token:'t',fetchImpl:async(url,options)=>{
  if(new URL(url).pathname==='/api/control/cancel'&&broken)return {ok:false,status:404,json:async()=>({error:'Missing route'})};
  return h.fetchImpl(url,options);
 }});
 await source.start();await assert.rejects(source.stop(),/Missing route/);await assert.rejects(source.start(),/Missing route/);
 assert.equal(h.requests.filter(r=>r.path==='/api/start').length,1);broken=false;await source.stop();
});
test('a structured gone nonowner handle can be released and a new explicit Start registers afresh',async()=>{
 const h=harness();await h.source.start();h.sessions.get('s1').stopped=true;h.clients.clear();
 await h.source.stop();const next=await h.source.start();assert.notEqual(next.control_client_id,h.sessions.get('s1').metadata.control_client_id);await h.source.stop();
});
test('takeover rejection does not renew or retry without another explicit Start',async()=>{
 const h=harness();h.config.startError='client_superseded';
 await assert.rejects(h.source.start(),error=>error.code==='client_superseded');
 assert.equal(h.requests.filter(r=>r.path==='/api/control/open').length,1);
 assert.equal(h.requests.filter(r=>r.path==='/api/start').length,1);
 h.config.startError=null;await h.source.start();assert.equal(h.clients.size,2);await h.source.stop();
});
test('cancellation timeout blocks a newer worker until explicit cleanup succeeds',async()=>{
 const h=harness({timeoutMs:20});await h.source.start();h.config.holdCancels=true;
 await assert.rejects(h.source.stop(),/timed out/);await assert.rejects(h.source.start(),/timed out/);
 assert.equal(h.requests.filter(r=>r.path==='/api/start').length,1);
 h.config.holdCancels=false;await h.source.stop();const next=await h.source.start();
 for(const deliver of h.pendingCancels.splice(0))deliver();await settle();assert.equal(h.sessions.get(next.id).stopped,false);await h.source.stop();
});
test('cleanup failure details remain attached to a failed Start',async()=>{
 const h=harness();h.config.badMetadata=true;h.config.stopError=true;
 await assert.rejects(h.source.start(),error=>/Invalid M4A/.test(error.message)&&error.cleanupError?.code==='cleanup_unconfirmed');
 assert(h.source._intent);h.config.stopError=false;await h.source.stop();
});
test('rapid queued intents skip superseded work and preserve one active owner',async()=>{
 const h=harness();const a=h.source.start(),b=h.source.start(),c=h.source.stop(),d=h.source.start();
 assert.equal(await a,null);assert.equal(await b,null);await c;const next=await d;
 assert.equal(h.requests.filter(r=>r.path==='/api/start').length,1);assert.equal(h.source.metadata.id,next.id);await h.source.stop();
});
test('revision exhaustion does not send an unsafe-integer Start',async()=>{
 const h=harness();h.source._revision=Number.MAX_SAFE_INTEGER;await assert.rejects(h.source.start(),/revision exhausted/);
 assert.equal(h.requests.filter(r=>r.path==='/api/start').length,0);await h.source.stop();
});


test('a late registration cannot replace the handle of a newer explicit Start',async()=>{
 const h=harness();h.config.holdOpens=true;const old=h.source.start();await settle();await h.source.stop();assert.equal(await old,null);
 h.config.holdOpens=false;const fresh=await h.source.start();h.pendingOpens.shift()();await settle();
 const next=await h.source.start();assert.equal(next.control_client_id,fresh.control_client_id);assert.equal(h.clients.size,2);await h.source.stop();
});
test('a stale Start rejection cannot retire a newer active handle',async()=>{
 const h=harness();h.config.holdStarts=true;const old=h.source.start();await settle();
 const latest=h.source.start();await settle();h.pendingStarts.pop()();const fresh=await latest;assert.equal(await old,null);
 h.config.startError='client_superseded';h.pendingStarts.shift()();await settle();h.config.startError=null;h.config.holdStarts=false;
 const next=await h.source.start();assert.equal(next.control_client_id,fresh.control_client_id);assert.equal(h.clients.size,1);await h.source.stop();
});
test('a current gone-client pulse allows registration only on the next explicit Start',async()=>{
 const h=harness();let gone=false;
 const source=new Source({token:'t',fetchImpl:async(url,options)=>{
  if(gone&&new URL(url).pathname==='/api/pulse')return {ok:false,status:404,json:async()=>({error:'Gone',code:'control_client_gone'})};
  return h.fetchImpl(url,options);
 }});
 const old=await source.start();h.sessions.get(old.id).stopped=true;h.clients.clear();gone=true;
 await assert.rejects(source.poll(),error=>error.code==='control_client_gone');assert.equal(h.requests.filter(r=>r.path==='/api/control/open').length,1);
 gone=false;const fresh=await source.start();assert.notEqual(fresh.control_client_id,old.control_client_id);await source.stop();
});

(async()=>{
 let failed=0;
 for(const {name,fn} of tests){try{await fn();console.log('PASS '+name);}catch(error){failed++;console.error('FAIL '+name+'\n'+error.stack);}}
 if(failed)process.exitCode=1;else console.log(tests.length+' standalone adapter tests passed.');
})();
