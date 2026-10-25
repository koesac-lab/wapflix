// 5A.4C controlled visibility/terminal tests. Browser/lease acceptance is separate.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const text=fs.readFileSync(path.join(__dirname,'test_handset_live_navigation.cjs'),'utf8');
const marker="for(const model of ['3210','3310','8210','6310','7110']){";
assert.equal(text.split(marker).length,2,'known saved model harness');
const {environment,entry,deferred,flush}=new Function('require','__dirname',
  text.split(marker)[0]+'\nreturn {environment,entry,deferred,flush};')(require,__dirname);
const hide=async e=>{e.document.hidden=true;await e.fire('visibilitychange');};
const show=async e=>{e.document.hidden=false;await e.fire('visibilitychange');};
function held(e,before){assert.equal(e.snapshot().position,before.position);assert.equal(e.snapshot().presentedSourceTime,before.presentedSourceTime);}
function failPoll(e,error){e.adapter.poll=async()=>{throw error;};}

test('hide pauses immediately, retains picture and does not Stop',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(1137);const before=e.snapshot();
  e.document.hidden=true;const hiding=e.fire('visibilitychange');assert.equal(e.snapshot().state,'paused');held(e,before);
  await hiding;e.raf(90000);held(e,before);assert.equal(e.adapter.stops,0);assert.equal(e.run('view'),'live-player');
});
test('healthy return validates with paused heartbeat and never auto-resumes',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(1200);const before=e.snapshot();await hide(e);await show(e);
  assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().resumeNeedsCheck,false);assert.equal(e.adapter.polls.at(-1).paused,true);
  e.raf(90000);held(e,before);assert.equal(e.adapter.starts,1);assert.equal(e.left.attrs['aria-label'],'RESUME');
  e.ctx.select();await flush();assert.equal(e.snapshot().state,'playing');e.raf(100000);held(e,before);
});
test('return must validate before accepting explicit Resume',async()=>{
  const e=environment();await e.play();await hide(e);const gate=deferred();e.adapter.pollGate=gate;e.document.hidden=false;
  const showing=e.fire('visibilitychange');assert.equal(e.snapshot().resumeNeedsCheck,true);assert.equal(e.left.attrs['aria-label'],'CHECK');
  e.ctx.select();assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().playIntent,false);
  e.adapter.pollGate=null;gate.resolve({state:'running',total_frames:null});await showing;await flush();
  assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().resumeNeedsCheck,false);
  e.ctx.select();await flush();assert.equal(e.snapshot().state,'playing');
});
test('a pre-hide response cannot validate a later visible return',async()=>{
  const e=environment();await e.play();const first=deferred(),second=deferred();e.adapter.pollGate=first;
  const old=e.poll();await hide(e);e.document.hidden=false;const showing=e.fire('visibilitychange');
  e.adapter.pollGate=second;first.resolve({state:'running'});await old;await showing;
  assert.equal(e.snapshot().resumeNeedsCheck,true);assert.equal(e.snapshot().state,'paused');
  e.adapter.pollGate=null;second.resolve({state:'running'});await flush();assert.equal(e.snapshot().resumeNeedsCheck,false);
});
test('hide during an in-flight playing poll sends one follow-up pause pulse',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.pollGate=gate;const polling=e.poll();
  const count=e.adapter.polls.length;await hide(e);e.adapter.pollGate=null;gate.resolve({state:'running'});await polling;await flush();
  assert.equal(e.adapter.polls.length,count+1);assert.equal(e.adapter.polls.at(-1).paused,true);assert.equal(e.snapshot().state,'paused');
});
test('hide before Start acknowledgement records pause intent and preserves cancellation',async()=>{
  const e=environment();const gate=deferred();e.adapter.startGate=gate;e.ctx.load(entry);await hide(e);
  assert.equal(e.snapshot().state,'starting');assert.equal(e.adapter.stops,0);assert.equal(e.snapshot().playIntent,false);
  gate.resolve({source_start:30,range_end:90,fps:8,chunk_frames:16});await flush();assert.equal(e.snapshot().state,'paused');
  assert.equal(e.adapter.polls.at(-1).paused,true);await show(e);assert.equal(e.snapshot().state,'paused');e.ctx.back();assert.equal(e.adapter.stops,1);
});
test('return before delayed Start acknowledgement still cannot auto-play',async()=>{
  const e=environment();const gate=deferred();e.adapter.startGate=gate;e.ctx.load(entry);await hide(e);await show(e);
  gate.resolve({source_start:30,range_end:90,fps:8,chunk_frames:16});await flush();
  assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().resumeNeedsCheck,false);assert.equal(e.snapshot().position,0);
});
test('programmatic Start while hidden has paused rather than play intent',async()=>{
  const e=environment();e.document.hidden=true;await e.play();assert.equal(e.snapshot().state,'paused');
  assert.equal(e.snapshot().playIntent,false);e.raf(90000);assert.equal(e.snapshot().position,0);
});
test('clock guard freezes if hidden flag changes before event dispatch',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(1200);const before=e.snapshot();
  e.document.hidden=true;e.raf(90000);assert.equal(e.snapshot().state,'paused');held(e,before);
});
test('hidden Select never silently resumes the worker',async()=>{
  const e=environment();await e.play();await hide(e);e.ctx.select();await flush();
  assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().playIntent,false);assert.equal(e.adapter.starts,1);
});
test('already user-paused session remains paused through hide and return',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();await hide(e);await show(e);
  assert.equal(e.snapshot().state,'paused');assert.equal(e.adapter.starts,1);assert.equal(e.adapter.stops,0);
});
test('expired-or-replaced generic 404 is neutral, actionable and never auto-restarts',async()=>{
  const e=environment();await e.play();await hide(e);failPoll(e,Object.assign(Error('session not found'),{status:404,code:'session_not_found'}));await show(e);
  assert.equal(e.snapshot().state,'error');assert.match(e.elements.get('summary').textContent,/SESSION ENDED - RESTART/);
  assert.doesNotMatch(e.elements.get('summary').textContent,/SESSION EXPIRED/);assert.equal(e.left.attrs['aria-label'],'RESTART');
  assert.equal(e.adapter.starts,1);assert.equal(e.timers.size,0);
});
test('verified expiry code is distinct from an unknown stopped reason',async()=>{
  const e=environment();await e.play();failPoll(e,Object.assign(Error('verified lease reason'),{code:'client_expired'}));await e.poll();
  assert.match(e.elements.get('summary').textContent,/SESSION EXPIRED/);assert.equal(e.adapter.starts,1);
});
test('structured conversion failure remains distinct from session expiry',async()=>{
  const e=environment();await e.play();failPoll(e,Object.assign(Error('Conversion failed'),{code:'conversion_failed'}));await e.poll();
  assert.match(e.elements.get('summary').textContent,/CONVERSION FAILED/);assert.doesNotMatch(e.elements.get('summary').textContent,/SESSION EXPIRED/);
});
test('raw current error status has explicit conversion-failure semantics',async()=>{
  const e=environment();await e.play();e.adapter.poll=async()=>({state:'error',error:'converter failed'});await e.poll();
  assert.match(e.elements.get('summary').textContent,/CONVERSION FAILED/);assert.equal(e.adapter.starts,1);
});
test('generic stopped status cannot be labelled expiry',async()=>{
  const e=environment();await e.play();e.adapter.poll=async()=>({state:'stopped'});await e.poll();
  assert.match(e.elements.get('summary').textContent,/SESSION ENDED - RESTART/);assert.doesNotMatch(e.elements.get('summary').textContent,/SESSION EXPIRED/);
});
test('timeout on return stays a timeout, not invented expiry',async()=>{
  const e=environment();await e.play();await hide(e);failPoll(e,Object.assign(Error('deadline'),{name:'TimeoutError'}));await show(e);
  assert.match(e.elements.get('summary').textContent,/TRANSPORT TIMEOUT/);assert.equal(e.adapter.starts,1);
});
test('explicit Restart begins at configured source start, not false position-preserving Resume',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(3000);assert.equal(e.snapshot().position,2);
  const poll=e.adapter.poll.bind(e.adapter);failPoll(e,Object.assign(Error('gone'),{status:404}));await e.poll();
  e.adapter.poll=poll;e.ctx.select();await flush();assert.equal(e.adapter.starts,2);assert.equal(e.snapshot().position,0);
  assert.equal(e.snapshot().presentedSourceTime,30);assert.equal(e.snapshot().state,'playing');
});
test('visibility changes on an error screen never retry or replace its explanation',async()=>{
  const e=environment();await e.play();failPoll(e,Error('gone'));await e.poll();const message=e.elements.get('summary').textContent;
  await hide(e);await show(e);assert.equal(e.adapter.starts,1);assert.equal(e.elements.get('summary').textContent,message);
});
test('natural EOF offers explicit Replay and creates no automatic next session',async()=>{
  const e=environment();e.adapter.complete=true;e.adapter.total=1;e.adapter.end=30.125;await e.play();e.raf(1000);e.raf(1125);
  assert.equal(e.snapshot().state,'ended');assert.equal(e.left.attrs['aria-label'],'REPLAY');assert.equal(e.adapter.starts,1);await flush();
  e.adapter.complete=false;e.adapter.end=38;e.ctx.key('5');await flush();assert.equal(e.adapter.starts,2);assert.equal(e.snapshot().position,0);
});
test('completed paused tail survives hide/return until explicit Resume',async()=>{
  const e=environment();e.adapter.complete=true;e.adapter.total=9;e.adapter.end=31.125;await e.play();e.raf(1000);e.raf(2000);
  const before=e.snapshot();await hide(e);await show(e);e.raf(90000);held(e,before);
  e.ctx.select();await flush();e.raf(100000);e.raf(101000);assert.equal(e.snapshot().state,'ended');assert.equal(e.snapshot().presentedFrameIndex,8);
});
test('pending validation then Back rejects late repaint and late Resume permission',async()=>{
  const e=environment();await e.play();await hide(e);const gate=deferred();e.adapter.pollGate=gate;e.document.hidden=false;
  const showing=e.fire('visibilitychange');e.ctx.back();const calls=e.elements.get('display').context.log.length;
  gate.resolve({state:'running'});await showing;await flush();assert.equal(e.run('view'),'details');
  assert.equal(e.elements.get('display').context.log.length,calls);assert.equal(e.snapshot().resumeNeedsCheck,false);assert.equal(e.timers.size,0);
});
test('pagehide still releases ownership after hidden pause',async()=>{
  const e=environment();await e.play();await hide(e);await e.fire('pagehide');
  assert.equal(e.run('view'),'details');assert.equal(e.adapter.stops,1);assert.equal(e.timers.size,0);await show(e);assert.equal(e.adapter.starts,1);
});
test('Back and Home remain available during return validation',async()=>{
  for(const home of [false,true]){
    const e=environment();await e.play();await hide(e);const gate=deferred();e.adapter.pollGate=gate;e.document.hidden=false;
    const showing=e.fire('visibilitychange');home?e.ctx.key('*'):e.ctx.back();assert.equal(e.run('view'),home?'home':'details');
    gate.resolve({state:'running'});await showing;assert.equal(e.adapter.stops,1);assert.equal(e.timers.size,0);
  }
});
test('repeated hide/show retains one foreground timer and one animation chain',async()=>{
  const e=environment();await e.play();for(let n=0;n<8;n++){
    await hide(e);await show(e);e.raf(1000+n*1000);assert.equal(e.timers.size,1);assert.equal(e.queue.length,1);
    assert.equal(e.snapshot().state,'paused');assert.equal(e.adapter.starts,1);
  }
});
test('no timer delivery while backgrounded is not treated as a confirmed surviving lease',async()=>{
  const e=environment();await e.play();await hide(e);const before=e.adapter.polls.length;
  e.raf(90000);assert.equal(e.adapter.polls.length,before);assert.equal(e.snapshot().resumeNeedsCheck,true);
  failPoll(e,Object.assign(Error('not found after suspension'),{status:404}));await show(e);
  assert.equal(e.snapshot().state,'error');assert.equal(e.adapter.starts,1);
});
test('model swap during validation advertises Check, then Resume only after validation',async()=>{
  const e=environment();await e.play();await hide(e);const gate=deferred();e.adapter.pollGate=gate;e.document.hidden=false;
  const showing=e.fire('visibilitychange');e.setModel('7110');assert.equal(e.physical.press.attrs['aria-label'],'Check session before resuming');
  e.adapter.pollGate=null;gate.resolve({state:'running'});await showing;assert.equal(e.physical.press.attrs['aria-label'],'Resume live playback');
});

// Real source adapter + bridge, with scripted fetch (still not real HTTP/FFmpeg).
const RealSource=require('../stream-source.js');
async function settle(){for(let n=0;n<100;n++)await Promise.resolve();}
function connected(){
  const client='a'.repeat(48),requests=[];let starts=0,currentId=null,revision=0,pulseFailure=null;
  const metadata=()=>({id:currentId,navigation_id:'nav-'+starts,cols:8,rows:1,fps:8,chunk_frames:16,
    source_start:30,range_start:30,range_end:90});
  const reply=(status,data)=>({ok:status>=200&&status<300,status,json:async()=>data});
  async function fetchImpl(url,options){
    const u=new URL(url),body=options.body?JSON.parse(options.body):undefined;requests.push({path:u.pathname,body});
    if(u.pathname==='/api/control/open')return reply(200,{control_protocol:'start-fence-v1',control_client_id:client,control_lease_seconds:60});
    if(u.pathname==='/api/control/cancel')return reply(200,{fence_recorded:true,cleanup:'confirmed'});
    if(u.pathname==='/api/start'){
      starts++;revision=body.start_revision;currentId='stream-'+starts;
      return reply(200,{...metadata(),control_protocol:'start-fence-v1',control_client_id:client,start_revision:revision});
    }
    if(u.pathname==='/api/pulse'){
      if(pulseFailure)return reply(pulseFailure.status,pulseFailure.data);
      return reply(200,{...metadata(),state:'running',ready_frames:48,generated_chunks:3,total_frames:null});
    }
    if(u.pathname==='/api/chunk'){
      const n=Number(u.searchParams.get('n'));return reply(200,{...metadata(),version:1,layout:'lcd-1bit',encoding:'hex-msb',index:n,
        start_frame:n*16,frames:Array(16).fill('80')});
    }
    throw Error('unexpected '+u.pathname);
  }
  let source;
  class InjectedSource extends RealSource{constructor(options){super({...options,fetchImpl});source=this;}}
  const prefix=text.split(marker)[0].replace('WapflixStreamSource:Source,','WapflixStreamSource:InjectedSource,');
  assert.ok(prefix.includes('WapflixStreamSource:InjectedSource,'));
  const {environment:realEnvironment}=new Function('require','__dirname','InjectedSource',prefix+'\nreturn {environment};')(require,__dirname,InjectedSource);
  const e=realEnvironment();
  return {e,requests,get source(){return source;},get starts(){return starts;},get revision(){return revision;},
    fail(status,data){pulseFailure={status,data};},healthy(){pulseFailure=null;},
    async play(){await e.ctx.load(entry);await settle();}};
}
test('real adapter retains session across healthy hide/return/explicit Resume',async()=>{
  const x=connected();await x.play();const id=x.source.metadata.id;assert.equal(x.e.snapshot().state,'playing');
  await hide(x.e);await settle();await show(x.e);await settle();assert.equal(x.e.snapshot().state,'paused');
  assert.equal(x.source.metadata.id,id);assert.equal(x.starts,1);
  assert.ok(x.requests.some(r=>r.path==='/api/pulse'&&r.body.paused===true));
  x.e.ctx.select();await settle();assert.equal(x.e.snapshot().state,'playing');assert.equal(x.source.metadata.id,id);
  x.e.ctx.back();await settle();
});
test('real adapter 404 on return is neutral; restart is an explicit new fenced Start',async()=>{
  const x=connected();await x.play();await hide(x.e);await settle();x.fail(404,{error:'Session not found',code:'session_not_found'});
  await show(x.e);await settle();assert.equal(x.e.snapshot().state,'error');assert.equal(x.starts,1);
  assert.match(x.e.elements.get('summary').textContent,/SESSION ENDED - RESTART/);
  x.healthy();x.e.ctx.select();await settle();assert.equal(x.starts,2);assert.equal(x.e.snapshot().position,0);
  assert.equal(x.source.metadata.source_start,30);x.e.ctx.back();await settle();
});
test('real adapter explicit converter status reaches the bridge without message inference',async()=>{
  const x=connected();await x.play();x.fail(200,{state:'error',error:'worker failed'});await x.e.poll();await settle();
  assert.equal(x.e.snapshot().state,'error');assert.match(x.e.elements.get('summary').textContent,/CONVERSION FAILED/);
  assert.equal(x.starts,1);x.e.ctx.back();await settle();
});
test('real adapter page exit sends scoped cancellation for the current Start revision',async()=>{
  const x=connected();await x.play();await hide(x.e);await settle();await x.e.fire('pagehide');await settle();
  const cancel=x.requests.filter(r=>r.path==='/api/control/cancel').at(-1);
  assert.equal(cancel.body.cancel_through,x.revision);assert.equal(cancel.body.control_client_id,'a'.repeat(48));
  assert.equal(x.e.run('view'),'details');assert.equal(x.e.timers.size,0);
});
