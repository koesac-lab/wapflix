// Combined R2C tests: real fetch against the Python fenced/control-only server.
const assert=require('node:assert/strict');
const Source=require('../stream-source.js');
const base=process.env.WAPFLIX_TEST_BASE,token=process.env.WAPFLIX_TEST_TOKEN;
const scenario=process.argv[2];
if(!base||!token)throw Error('Run through test_stream_source_http.py');
const nativeFetch=global.fetch.bind(global);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const raw=(path,body)=>nativeFetch(new URL(path,base),{method:'POST',headers:{'X-Wapflix-Test':token,'Content-Type':'application/json'},body:JSON.stringify(body)});
const sourceFor=fetchImpl=>new Source({token,baseUrl:base,fetchImpl});
async function step(phase,action){
 try{return await action();}
 catch(error){throw new Error('Combined '+scenario+' ['+phase+']: '+error.message,{cause:error});}
}
async function playable(source){
 const end=Date.now()+10000;
 while(Date.now()<end){await source.poll({paused:true});if(source.frameAt(source.metadata.source_start))return;await sleep(30);}
 throw Error('No generated frame arrived');
}
async function normal(){
 const requests=[];
 const source=sourceFor((url,options)=>{requests.push({url,options});return nativeFetch(url,options);});
 try{
  const meta=await source.start();assert.equal(meta.control_protocol,'start-fence-v1');
  await playable(source);assert(source.frameAt(meta.source_start));assert(source.retainedChunks<=5);
  await source.stop();assert.equal(source.state,'stopped');assert.equal(source.metadata,null);
  const result=await raw('/api/pulse',{id:meta.id,frame:0,paused:false});assert([404,409].includes(result.status));
  assert(requests.every(r=>r.options.headers['X-Wapflix-Test']===token));
 }finally{await source.stop();}
}
async function delayed(mode){
 let release,entered,lateStatus,oldMeta;
 const barrier=new Promise(resolve=>{release=resolve;});
 const started=new Promise(resolve=>{entered=resolve;});
 let finishWire;const wire=new Promise(resolve=>{finishWire=resolve;});
 let first=true;
 const source=sourceFor(async(url,options)=>{
  if(new URL(url).pathname==='/api/start'&&first){
   first=false;
   try{
    if(mode==='ack'){
     const response=await nativeFetch(url,options);oldMeta=await response.clone().json();entered();
     await barrier;lateStatus=response.status;return response;
    }
    entered();await barrier;
    // Deliberately ignore abort to model work that arrives after the client
    // deadline. The real HTTP server must reject it using its tombstone.
    const response=await nativeFetch(url,{...options,signal:undefined});lateStatus=response.status;return response;
   }finally{finishWire();}
  }
  return nativeFetch(url,options);
 });
 // Only the deliberately stalled old Start gets the injected deadline. _api
 // installs its timer synchronously, so restore the normal budget immediately.
 // Registration, fence cleanup, recovery and polls retain production defaults.
 if(mode==='timeout'){
  const request=source._api.bind(source);let inject=true;
  source._api=(path,...args)=>{
   if(path!=='/api/start'||!inject)return request(path,...args);
   inject=false;const budget=source._timeoutMs;source._timeoutMs=2000;
   try{return request(path,...args);}
   finally{source._timeoutMs=budget;}
  };
 }
 let primaryError;
 try{
  const old=source.start();
  const settled=old.then(value=>({value}),error=>({error}));
  await step('initial Start reaches transport barrier',()=>Promise.race([started,settled.then(result=>{
   if(result.error)throw result.error;
   throw Error('Initial Start finished without reaching its transport barrier');
  })]));
  if(mode==='timeout'){
   const result=await step('old Start deadline and scoped cleanup',()=>settled);assert.equal(result.error?.name,'TimeoutError');
   if(result.error.cleanupError)throw new Error('Old Start fence cleanup failed: '+result.error.cleanupError.message,{cause:result.error.cleanupError});
  }else{
   await step('Stop before acknowledgement',()=>source.stop());assert.equal((await settled).value,null);
   if(mode==='ack'){
    const ended=await raw('/api/pulse',{id:oldMeta.id,frame:0,paused:false});assert([404,409].includes(ended.status));
   }
  }
  const fresh=await step('recovery Start',()=>source.start());release();await step('late HTTP dispatch',()=>wire);
  assert.equal(lateStatus,mode==='ack'?200:409);
  assert.equal(source.metadata.id,fresh.id);
  await step('recovery poll/chunk',()=>playable(source));await step('recovery Stop',()=>source.stop());
 }catch(error){primaryError=error;throw error;}
 finally{
  release();
  try{await step('final cleanup',()=>source.stop());}
  catch(error){if(!primaryError)throw error;console.error('Additional cleanup failure: '+error.message);}
  if(!first)await wire;
 }
}
async function controlOnly(){
 const source=sourceFor(nativeFetch);
 try{
  await assert.rejects(source.start(),error=>error.status===409&&error.code==='fenced_admission_unavailable');
  assert.equal(source.state,'error');assert.equal(source.metadata,null);
 }finally{await source.stop();}
}
(async()=>{
 if(scenario==='normal')await normal();
 else if(['dispatch','timeout','ack'].includes(scenario))await delayed(scenario);
 else if(scenario==='control-only')await controlOnly();
 else throw Error('Unknown scenario');
 console.log('PASS combined adapter/server '+scenario);
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
