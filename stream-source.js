/* 5A.2: standalone transport adapter. No DOM, rendering, background polling or auto-start. */
(function(root){
'use strict';
class WapflixStreamSource {
 constructor({token,baseUrl='/',fetchImpl,timeoutMs=10000}={}){
  if(typeof token!=='string'||!token)throw Error('A server capability token is required');
  const page=root.location?.href,base=new URL(baseUrl,page||'http://localhost/');
  if(!['http:','https:'].includes(base.protocol)||base.username||base.password||base.pathname!=='/'||base.search||base.hash)throw Error('Use an HTTP(S) API origin without a path');
  if(page&&base.origin!==new URL(page).origin)throw Error('The handset and API must be same-origin');
  this._fetch=fetchImpl||root.fetch?.bind(root);
  if(typeof this._fetch!=='function')throw Error('fetch is required');
  if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>120000)throw Error('timeoutMs must be 1..120000');
  this._timeoutMs=timeoutMs;this._token=token;this._origin=base.origin;this._generation=0;this._queue=Promise.resolve();
  this._owned=null;this._metadata=null;this._status=null;this._pending=null;this._chunks=new Map();
  this._state='idle';this._error=null;
  this._warmed=false; // Latched for this stream generation, independent of cache eviction.
 }
 get state(){return this._state;}
 get error(){return this._error;}
 get metadata(){return this._metadata;}
 get status(){return this._status;}
 get retainedChunks(){return this._chunks.size;}
 _invalidate(state){
  ++this._generation;if(this._pending)this._pending.controller.abort();this._pending=null;
  this._metadata=null;this._status=null;this._chunks.clear();this._state=state;this._error=null;
  this._warmed=false;
  return this._generation;
 }
 _enqueue(action){
  const operation=this._queue.then(action);this._queue=operation.catch(()=>{});return operation;
 }
 async _api(path,body,signal){
  const aborted=()=>{const error=Error('Request aborted');error.name='AbortError';return error;};
  if(signal?.aborted)throw aborted();
  const controller=new AbortController();let timer,onAbort;
  const cancelled=new Promise((resolve,reject)=>{
   onAbort=()=>{controller.abort();reject(aborted());};
   signal?.addEventListener('abort',onAbort,{once:true});
  });
  const deadline=new Promise((resolve,reject)=>{
   timer=setTimeout(()=>{controller.abort();const error=Error('Streaming API request timed out');error.name='TimeoutError';reject(error);},this._timeoutMs);
  });
  const options={headers:{'X-Wapflix-Test':this._token},credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal};
  if(body!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const operation=(async()=>{
   const response=await this._fetch(new URL(path,this._origin).href,options);
   if(!response.ok){
    let message=`HTTP ${response.status}`;
    try{message=(await response.json()).error||message;}catch{}
    const error=Error(message);error.status=response.status;throw error;
   }
   return response.status===204?null:await response.json();
  })();
  try{return await Promise.race([operation,deadline,cancelled]);}
  finally{clearTimeout(timer);signal?.removeEventListener('abort',onAbort);}
 }
 async _releaseOwned(){
  const owned=this._owned;if(!owned)return;
  try{await this._api('/api/navigation/stop',{navigation_id:owned.navigation_id});}
  catch(error){if(error.status!==404&&error.status!==410)throw error;}
  if(this._owned===owned)this._owned=null;
 }
 _validateMetadata(data){
  const int=n=>Number.isInteger(n)&&n>0;
  if(!data||typeof data.id!=='string'||!data.id||typeof data.navigation_id!=='string'||!data.navigation_id||
   !int(data.cols)||data.cols>240||data.cols%8||!int(data.rows)||data.rows>200||!int(data.fps)||data.fps>24||
   !int(data.chunk_frames)||data.chunk_frames>data.fps*10||!Number.isFinite(data.source_start)||
   !Number.isFinite(data.range_start)||!Number.isFinite(data.range_end)||data.range_start<0||
   data.range_end<=data.source_start||data.source_start<data.range_start)throw Error('Invalid M4A stream metadata');
  return Object.freeze({...data});
 }
 start(){
  const g=this._invalidate('starting');
  return this._enqueue(async()=>{
   let newOwner=false;
   try{
    await this._releaseOwned();if(g!==this._generation)return null;
    // Start is intentionally not aborted: its acknowledged navigation can be
    // released even if Stop/new Start happened while the request was pending.
    const data=await this._api('/api/start',{});
    if(typeof data?.navigation_id==='string'&&data.navigation_id){this._owned={navigation_id:data.navigation_id};newOwner=true;}
    if(g!==this._generation){newOwner=false;await this._releaseOwned();return null;}
    this._metadata=this._validateMetadata(data);this._state='ready';return this._metadata;
   }catch(error){
    if(newOwner){try{await this._releaseOwned();}catch(cleanup){error.cleanupError=cleanup;}}
    if(g!==this._generation)return null;
    this._state='error';this._error=error;throw error;
   }
  });
 }
 stop(){
  const g=this._invalidate('stopping');
  return this._enqueue(async()=>{
   try{await this._releaseOwned();if(g===this._generation)this._state='stopped';return true;}
   catch(error){if(g===this._generation){this._state='error';this._error=error;}throw error;}
  });
 }
 _current(g,id){return g===this._generation&&this._metadata?.id===id;}
 _frameIndex(sourceTime){
  const m=this._metadata;
  if(!Number.isFinite(sourceTime)||sourceTime<m.source_start-1e-7||sourceTime>m.range_end+1e-7)throw RangeError('Source time is outside this stream');
  return Math.max(0,Math.floor((sourceTime-m.source_start)*m.fps+1e-7));
 }
 _validateStatus(data,m){
  const integer=n=>Number.isInteger(n)&&n>=0;
  const limit=Math.ceil((m.range_end-m.source_start)*m.fps);
  if(!data||data.id!==m.id||data.cols!==m.cols||data.rows!==m.rows||data.fps!==m.fps||data.chunk_frames!==m.chunk_frames||
   data.source_start!==m.source_start||!['running','complete'].includes(data.state)||
   !integer(data.ready_frames)||data.ready_frames>limit||!integer(data.generated_chunks)||
   data.generated_chunks!==Math.ceil(data.ready_frames/m.chunk_frames)||
   (data.state==='complete'&&(!Number.isInteger(data.total_frames)||data.total_frames<1||data.total_frames!==data.ready_frames)))throw Error('Invalid stream status');
 }
 _validateChunk(chunk,n,m){
  const size=Math.ceil(m.cols*m.rows/8)*2;
  if(!chunk||chunk.version!==1||chunk.layout!=='lcd-1bit'||chunk.encoding!=='hex-msb'||chunk.index!==n||
   chunk.cols!==m.cols||chunk.rows!==m.rows||chunk.fps!==m.fps||chunk.source_start!==m.source_start||
   chunk.start_frame!==n*m.chunk_frames||!Array.isArray(chunk.frames)||!chunk.frames.length||chunk.frames.length>m.chunk_frames||
   chunk.frames.some(f=>typeof f!=='string'||f.length!==size||!/^[0-9a-f]+$/i.test(f)))throw Error('Invalid LCD chunk');
  return Object.freeze({...chunk,frames:Object.freeze([...chunk.frames])});
 }
 poll({sourceTime=this._metadata?.source_start,paused=false}={}){
  if(!this._metadata||this._state!=='ready')return Promise.resolve(null);
  if(typeof paused!=='boolean')return Promise.reject(TypeError('paused must be boolean'));
  let frame;try{frame=this._frameIndex(sourceTime);}catch(error){return Promise.reject(error);}
  if(this._pending?.generation===this._generation)return this._pending.promise;
  const m=this._metadata,g=this._generation,ticket={generation:g,controller:new AbortController(),promise:null};
  this._pending=ticket;
  ticket.promise=(async()=>{
   try{
    const data=await this._api('/api/pulse',{id:m.id,frame,paused:paused&&this._warmed},ticket.controller.signal);
    if(!this._current(g,m.id))return null;
    if(['error','stopped'].includes(data?.state))throw Error(data.error||'Session stopped or expired');
    this._validateStatus(data,m);this._status=Object.freeze({...data});
    const position=data.total_frames!==null&&data.total_frames!==undefined?Math.min(frame,data.total_frames-1):frame;
    const base=Math.floor(position/m.chunk_frames);
    for(const n of this._chunks.keys())if(n<base-1||n>=base+4)this._chunks.delete(n);
    for(let n=base;n<Math.min(base+4,data.generated_chunks);n++){
     if(this._chunks.has(n))continue;
     const chunk=await this._api('/api/chunk?id='+encodeURIComponent(m.id)+'&n='+n,undefined,ticket.controller.signal);
     if(!this._current(g,m.id))return null;
     if(chunk!==null)this._chunks.set(n,this._validateChunk(chunk,n,m));
    }
    // Only validated, current-generation data may establish startup readiness.
    if(this._chunks.has(0)&&(this._chunks.has(1)||data.state==='complete'))this._warmed=true;
    return this._status;
   }catch(error){
    if(!this._current(g,m.id))return null;
    this._state='error';this._error=error;throw error;
   }finally{if(this._pending===ticket)this._pending=null;}
  })();
  return ticket.promise;
 }
 frameAt(sourceTime){
  const m=this._metadata;if(!m)return null;
  let n=this._frameIndex(sourceTime);
  if(this._status?.total_frames!=null)n=Math.min(n,this._status.total_frames-1);
  const chunk=this._chunks.get(Math.floor(n/m.chunk_frames)),hex=chunk?.frames[n-(chunk?.start_frame||0)];
  return hex===undefined?null:Object.freeze({hex,cols:m.cols,rows:m.rows,fps:m.fps,frameIndex:n,sourceTime:m.source_start+n/m.fps});
 }
 bufferedUntil(sourceTime=this._metadata?.source_start){
  const m=this._metadata;if(!m)return null;
  let n=this._frameIndex(sourceTime),end=sourceTime;
  if(this._status?.total_frames!=null)n=Math.min(n,this._status.total_frames-1);
  for(let i=Math.floor(n/m.chunk_frames);this._chunks.has(i);i++){
   const chunk=this._chunks.get(i);end=Math.max(end,m.source_start+(chunk.start_frame+chunk.frames.length)/m.fps);
  }
  return Math.min(end,m.range_end);
 }
}
root.WapflixStreamSource=WapflixStreamSource;
if(typeof module!=='undefined'&&module.exports)module.exports=WapflixStreamSource;
})(typeof globalThis!=='undefined'?globalThis:this);
