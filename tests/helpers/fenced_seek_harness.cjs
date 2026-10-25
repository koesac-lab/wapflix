// Controlled HTTP/DOM fixtures. No sockets, FFmpeg or browser acceptance.
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..');
const settle=async()=>{for(let n=0;n<6;n++)await new Promise(r=>setImmediate(r));};
function transport({start=30,end=90,complete=true,timeoutMs=2000}={}){
 const requests=[],sessions=new Map(),pending={seeks:[],pulses:[],chunks:[],starts:[]};
 const config={holdSeeks:false,holdPulses:false,holdChunks:false,holdStarts:false,seekError:null,cancelError:false,badSeek:null,complete,ready:64};
 const client='a'.repeat(48);let serial=0,nav=0,active=null,cancelled=0;
 const response=(body,status=200)=>({ok:status>=200&&status<300,status,json:async()=>body});
 const error=(code,status=409)=>response({error:code,code},status);
 const captions={timebase:'source',track_found:true,cues:[{start:0,end:35,text:'BEFORE'},{start:35,end:200,text:'AFTER'}]};
 function create(source,revision,body){
  const id='s'+ ++serial,metadata={id,navigation_id:active?.navigation_id||'n'+ ++nav,revision,
   cols:8,rows:1,fps:8,chunk_frames:16,source_start:source,range_start:start,range_end:end,captions};
  if(body)Object.assign(metadata,{control_protocol:'start-fence-v1',control_client_id:client,start_revision:body.start_revision});
  sessions.set(id,metadata);active=metadata;return {...metadata};
 }
 function delayed(kind,deliver){return new Promise(resolve=>pending[kind].push(()=>resolve(deliver())));}
 async function fetchImpl(url,options={}){
  const u=new URL(url),body=options.body?JSON.parse(options.body):null;
  requests.push({path:u.pathname,body,options,query:u.searchParams});
  if(u.pathname==='/api/control/open')return response({control_protocol:'start-fence-v1',control_client_id:client,control_lease_seconds:60});
  if(u.pathname==='/api/control/cancel'){
   cancelled=Math.max(cancelled,body.cancel_through);
   if(config.cancelError)return error('cleanup_unconfirmed',503);
   if(active?.startOwner<=cancelled)active=null;
   return response({fence_recorded:true,cleanup:'confirmed'});
  }
  if(u.pathname==='/api/start'){
   const deliver=()=>{
    if(body.start_revision<=cancelled)return error('cancelled_start');
    active=null;const data=create(start,0,body);active.startOwner=body.start_revision;return response(data);
   };
   return config.holdStarts?delayed('starts',deliver):deliver();
  }
  if(u.pathname==='/api/seek'){
   const owner=active?.startOwner;
   const deliver=()=>{
    if(config.seekError)return error(config.seekError);
    if(!active||owner<=cancelled||active.navigation_id!==body.navigation_id)return error('navigation_ended');
    if(body.revision<=active.revision)return error('stale_seek');
    if(!(body.position>=start&&body.position<end))return error('invalid_request',400);
    const source=start+Math.floor((body.position-start)*8)/8;
    const data=create(source,body.revision);active.startOwner=owner;
    if(config.badSeek==='navigation')data.navigation_id='foreign';
    if(config.badSeek==='revision')data.revision--;
    if(config.badSeek==='destination')data.source_start=start;
    if(config.badSeek==='range')data.range_end++;
    return response(data);
   };
   return config.holdSeeks?delayed('seeks',deliver):deliver();
  }
  if(u.pathname==='/api/pulse'){
   const m=sessions.get(body.id),count=Math.ceil((m.range_end-m.source_start)*8);
   const ready=config.complete?count:Math.min(count,config.ready);
   const data={...m,state:config.complete?'complete':'running',ready_frames:ready,generated_chunks:Math.ceil(ready/16),total_frames:config.complete?count:null};
   const deliver=()=>response(data);return config.holdPulses?delayed('pulses',deliver):deliver();
  }
  if(u.pathname==='/api/chunk'){
   const m=sessions.get(u.searchParams.get('id')),n=Number(u.searchParams.get('n'));
   const count=Math.ceil((m.range_end-m.source_start)*8),ready=config.complete?count:Math.min(count,config.ready);
   const deliver=()=>n*16>=ready?response(null,204):response({version:1,layout:'lcd-1bit',encoding:'hex-msb',index:n,
    cols:8,rows:1,fps:8,source_start:m.source_start,start_frame:n*16,frames:Array(Math.min(16,ready-n*16)).fill(m.source_start<35?'80':'40')});
   return config.holdChunks?delayed('chunks',deliver):deliver();
  }
  return error('unknown_route',404);
 }
 return {requests,sessions,pending,config,fetchImpl,timeoutMs,get active(){return active;},
  count:p=>requests.filter(r=>r.path===p).length,release(kind){const f=pending[kind].shift();if(!f)throw Error('No pending '+kind);f();}};
}
function handset(options={}){
 const http=transport(options),nodes=[],elements=new Map(),listeners=new Map(),timers=new Map(),rafs=[];
 let id=0,context;const model=options.model||'3310';
 const drawing={clearRect(){},fillRect(){},drawImage(){}};
 function element(name,selectors=[],attrs={}){
  const e={name,selectors:new Set(selectors),attrs:{...attrs},dataset:{},isConnected:true,textContent:'',
   getContext:()=>drawing,appendChild(){},getAttribute(k){return Object.hasOwn(this.attrs,k)?this.attrs[k]:null;},
   setAttribute(k,v){this.attrs[k]=String(v);},removeAttribute(k){delete this.attrs[k];},
   focus(){document.activeElement=this;},classList:{contains:c=>selectors.includes('.'+c)},
   closest(s){return s.split(',').some(t=>this.selectors.has(t.trim()))?this:null;}};
  nodes.push(e);return e;
 }
 const get=id=>{if(!elements.has(id))elements.set(id,element(id));return elements.get(id);};
 const keypad={};for(const digit of '0123456789*#'){
  keypad[digit]=element('key'+digit,['.keypad [data-key="'+digit+'"]'],{'aria-label':'Static '+digit});keypad[digit].dataset.key=digit;
 }
 const physical={up:element('up',['.handset-up'],{'aria-label':'Scroll up'}),down:element('down',['.handset-down'],{'aria-label':'Scroll down'})};
 if(!['3210','3310'].includes(model)){
  physical.call=element('call',['.handset-call'],{'aria-label':'Select or play and pause'});
  physical.end=element('end',['.handset-end'],{'aria-label':'Return home'});
 }
 if(model==='7110'){
  physical.roller=element('roller',['.handset-roller']);
  physical.press=element('press',['.roller-press','.handset-roller'],{'aria-label':'Press roller to select'});
  physical.rollUp=element('roll-up',['.roller-up','.handset-roller'],{'aria-label':'Roll up'});
 }
 get('summary').textContent='LAUNCH';
 const document={hidden:false,activeElement:get('left'),getElementById:get,createElement:n=>element(n),
  querySelector:()=>null,querySelectorAll:s=>nodes.filter(e=>e.isConnected&&s.split(',').some(t=>e.selectors.has(t.trim()))),
  addEventListener(type,fn,opts){const k=(opts===true||opts?.capture?'capture:':'')+type;if(!listeners.has(k))listeners.set(k,[]);listeners.get(k).push(fn);}};
 const sandbox={document,console,URL,AbortController,setTimeout,clearTimeout,fetch:http.fetchImpl,
  wapflixLiveConfig:{token:'test-only',apiBase:'http://localhost/'},
  requestAnimationFrame:f=>{rafs.push(f);return ++id;},setInterval:(f,ms)=>{const n=++id;timers.set(n,f);return n;},clearInterval:n=>timers.delete(n),
  addEventListener:(type,fn)=>document.addEventListener(type,fn),staticKeys:[],staticLoads:[]};
 sandbox.window=sandbox;context=vm.createContext(sandbox);
 vm.runInContext(`const $=id=>document.getElementById(id),ctx=$('display').getContext('2d'),ink='#123';
 let view='details',item=null,clip=null,message='',detail=false,playing=false,last=0,frame=-1,token=0;
 function text(){}function center(){}function wrap(s){return [s];}function announce(s){$('summary').textContent=s;}
 function setPlaying(v){playing=v;}function render(){}function paint(){}
 function load(e){staticLoads.push(e);view='player';return Promise.resolve();}function select(){}function back(){view='home';}
 function key(v){staticKeys.push(v);if(v==='*')view='home';}function tick(){requestAnimationFrame(tick);}requestAnimationFrame(tick);`,context);
 for(const name of ['stream-source.js','live-captions.js','handset-captions.js','handset-live.js'])vm.runInContext(fs.readFileSync(path.join(ROOT,name),'utf8'),context,{filename:name});
 rafs.shift()(0);
 return {http,context,document,elements,keypad,physical,timers,rafs,element,
  snap:()=>sandbox.wapflixLive.snapshot(),key:v=>sandbox.key(v),back:()=>sandbox.back(),
  run:s=>vm.runInContext(s,context),async play(){sandbox.load({id:'local-stream-test',playback_type:'local-stream'});await settle();},
  async poll(){for(const f of [...timers.values()])f();await settle();},
  raf(t){const q=rafs.splice(0);q.forEach(f=>f(t));if(rafs.length!==1)throw Error('RAF chain duplicated');},
  async fire(type){for(const fn of listeners.get(type)||[])fn();await settle();},
  event(type,target,extra={}){const ev={type,target,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...extra};for(const fn of listeners.get('capture:'+type)||[]){fn(ev);if(ev.stopped)break;}return ev;},
  async close(){sandbox.back();await settle();}};
}
module.exports={transport,handset,settle};
