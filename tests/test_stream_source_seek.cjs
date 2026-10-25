// 5A.6A: explicit restart-seeking at the adapter boundary.
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
const starts=h=>h.requests.filter(r=>r.path==='/api/start');
const cancels=h=>h.requests.filter(r=>r.path==='/api/control/cancel');

test('seek requires an active ready stream and validates input before requests',async()=>{
 const h=harness();await assert.rejects(h.source.seek(40),/active stream/);
 await h.source.start();
 for(const value of [NaN,Infinity,-Infinity,'40',null])await assert.rejects(h.source.seek(value),/finite source time/);
 assert.equal(starts(h).length,1);assert.equal(h.source.state,'ready');await h.source.stop();
});
test('seek quantises to a frame and restarts the same fenced navigation',async()=>{
 const h=harness();await h.source.start();await h.source.poll();
 const result=await h.source.seek(40.137);
 assert.equal(result.requested,40.137);assert.equal(result.destination,40.125);assert.equal(result.frame,81);
 assert.equal(h.source.metadata.id,result.metadata.id);assert.equal(h.source.state,'ready');
 assert.equal(starts(h).length,2);assert.equal(cancels(h).length,1);
 assert.equal(starts(h)[1].body.control_client_id,starts(h)[0].body.control_client_id);
 assert.equal(starts(h)[1].body.start_revision,2);
 assert(h.sessions.get('s1').stopped);assert(!h.sessions.get('s2').stopped);
 await h.source.poll({sourceTime:40.125});assert(h.source.frameAt(40.125));await h.source.stop();
});
test('seek clamps to configured bounds and never issues an out-of-range pulse',async()=>{
 const h=harness();await h.source.start();
 for(const requested of [10,90,120]){
  const result=await h.source.seek(requested);
  assert.ok(result.destination>=30&&result.destination<=90);
  await h.source.poll({sourceTime:result.destination});
 }
 const pulses=h.requests.filter(r=>r.path==='/api/pulse');
 assert.deepEqual(pulses.map(r=>r.body.frame),[0,480,480]);await h.source.stop();
});
test('seek to the current position still performs an explicit restart',async()=>{
 const h=harness();await h.source.start();await h.source.poll({sourceTime:34});
 const result=await h.source.seek(34);assert.equal(result.destination,34);assert.equal(result.frame,32);
 assert.equal(starts(h).length,2);await h.source.stop();
});
test('a seek invalidates immediately; a second concurrent seek fails closed',async()=>{
 const h=harness();await h.source.start();const seeking=h.source.seek(40);
 await assert.rejects(h.source.seek(50),/Seek requires an active stream/);
 const result=await seeking;assert.equal(result.destination,40);assert.equal(result.frame,80);
 assert.equal(starts(h).length,2);assert.equal(cancels(h).length,1);
 assert(h.sessions.get('s1').stopped);assert(!h.sessions.get('s2').stopped);
 assert.equal(h.source.metadata.id,result.metadata.id);await h.source.poll({sourceTime:40});await h.source.stop();
});
test('sequential seeks each fence the prior session and the latest owns the source',async()=>{
 const h=harness();await h.source.start();
 let prior=await h.source.seek(40);assert.equal(prior.destination,40);
 let latest=await h.source.seek(50);assert.equal(latest.destination,50);
 latest=await h.source.seek(60);assert.equal(latest.destination,60);assert.equal(latest.frame,240);
 assert.equal(starts(h).length,4);assert.equal(cancels(h).length,3);
 assert(h.sessions.get('s1').stopped);assert(h.sessions.get('s2').stopped);assert(h.sessions.get('s3').stopped);
 assert.equal(h.source.metadata.id,latest.metadata.id);await h.source.poll({sourceTime:60});await h.source.stop();
});
test('seek during a pending pulse cancels it and clears old cache/readiness',async()=>{
 const h=harness();await h.source.start();await h.source.poll();h.config.holdPulses=true;
 const polling=h.source.poll({sourceTime:34});await settle();assert.equal(h.pendingPulses.length,1);
 const seeking=h.source.seek(38);h.config.holdPulses=false;assert.equal(await polling,null);
 const result=await seeking;for(let n=0;n<8;n++)await settle();assert.equal(result.destination,38);assert.equal(h.source.retainedChunks,0);
 await h.source.poll({sourceTime:38});for(let n=0;n<8;n++)await settle();assert(h.source.frameAt(38));await h.source.stop();
});
test('seek during pending chunk download fences the old session and discards late chunks',async()=>{
 const h=harness();await h.source.start();h.config.holdChunks=true;
 const polling=h.source.poll();await settle();assert.equal(h.pendingChunks.length,1);
 const seeking=h.source.seek(38);h.config.holdChunks=false;assert.equal(await polling,null);
 const result=await seeking;for(let n=0;n<8;n++)await settle();assert.equal(h.source.retainedChunks,0);assert.equal(result.destination,38);
 await h.source.poll({sourceTime:38});for(let n=0;n<8;n++)await settle();assert(h.source.frameAt(38));await h.source.stop();
});
test('Stop during pending seek tombstones it and prevents late admission',async()=>{
 const h=harness();await h.source.start();h.config.holdStarts=true;const seeking=h.source.seek(50);await settle();
 const stopping=h.source.stop();h.pendingStarts.shift()();assert.equal(await seeking,null);await stopping;
 assert.equal(h.source.state,'stopped');assert.equal(h.source.metadata,null);assert.equal(h.sessions.size,1);
});
test('a pending seek is fenced by Stop before its delayed Start acknowledgement',async()=>{
 const h=harness();await h.source.start();h.config.holdStarts=true;
 const seeking=h.source.seek(40);await settle();assert.equal(h.pendingStarts.length,1);
 const stopping=h.source.stop();h.pendingStarts.shift()();
 assert.equal(await seeking,null);await stopping;
 assert.equal(h.source.state,'stopped');assert.equal(h.source.metadata,null);
 assert(h.sessions.get('s1').stopped);assert.equal(h.sessions.size,1);
});
test('failed seek releases its acquired navigation and preserves explicit-restart semantics',async()=>{
 const h=harness();await h.source.start();h.config.badIdentity=true;
 await assert.rejects(h.source.seek(50),/Invalid fenced Start identity/);
 assert.equal(h.source.state,'error');assert(h.sessions.get('s1').stopped);assert(h.sessions.get('s2').stopped);
 h.config.badIdentity=false;await h.source.stop();const next=await h.source.start();assert.equal(h.source.metadata.id,next.id);await h.source.stop();
});
test('seek failure preserves cleanup details and does not silently retry',async()=>{
 const h=harness();await h.source.start();h.config.stopError=true;
 await assert.rejects(h.source.seek(50),error=>/Cannot stop worker/.test(error.message)&&error.cleanupError?.code==='cleanup_unconfirmed');
 assert.equal(starts(h).length,1);h.config.stopError=false;await h.source.stop();await h.source.start();await h.source.stop();
});
test('seek rejection for a superseded handle does not renew without another explicit action',async()=>{
 const h=harness();await h.source.start();h.config.startError='client_superseded';
 await assert.rejects(h.source.seek(50),error=>error.code==='client_superseded');
 assert.equal(h.requests.filter(r=>r.path==='/api/control/open').length,1);assert.equal(starts(h).length,2);
 h.config.startError=null;await h.source.start();assert.equal(h.clients.size,2);await h.source.stop();
});
test('seek retains caption selector contract and returns source-time metadata',async()=>{
 const h=harness();await h.source.start();const result=await h.source.seek(42);
 assert.equal(result.metadata.captions.timebase,'source');assert.equal(result.metadata.source_start,30);
 await h.source.stop();
});
test('existing Start/Stop/poll/chunk behaviour is unchanged by seek addition',async()=>{
 const h=harness();await h.source.start();await h.source.poll();
 assert.equal(h.source.frameAt(30.125).frameIndex,1);assert.equal(h.source.bufferedUntil(30),38);
 await h.source.stop();assert.equal(h.source.state,'stopped');
});
(async()=>{
 let failed=0;
 for(const {name,fn} of tests){try{await fn();console.log('PASS '+name);}catch(error){failed++;console.error('FAIL '+name+'\n'+error.stack);}}
 if(failed)process.exitCode=1;else console.log(tests.length+' 5A.6A adapter seek tests passed.');
})();
