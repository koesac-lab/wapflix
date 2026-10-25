// 5A.3B deterministic lifecycle/render/clock tests. Not browser acceptance.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'handset-live.js'), 'utf8');
const entry = {id:'local-stream-test', playback_type:'local-stream'};
const deferred = () => { let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject}; };
const flush = async () => { for(let n=0;n<12;n++) await Promise.resolve(); };
function environment(config = {token:'test-only',apiBase:'/'}) {
  const elements = new Map(), listeners = new Map(), queue = [], timers = new Map();
  let id=0, now=0, instance;
  const calls = {load:0, select:0, back:0, key:[], render:0, paint:0, staticTick:0, writes:0};
  const contexts=[];
  function context() {
    const log=[]; const c={log};
    for(const key of ['clearRect','fillRect','drawImage','strokeRect']) c[key]=(...args)=>log.push([key,...args]);
    contexts.push(c); return c;
  }
  function element(name) {
    const attrs={}; const c=context();
    return {id:name,width:0,height:0,attrs,context:c,textContent:'',getContext:()=>c,
      setAttribute:(k,v)=>attrs[k]=v, getAttribute:k=>attrs[k],
      closest:()=>null,classList:{contains:()=>false}};
  }
  const get=name=>{if(!elements.has(name))elements.set(name,element(name));return elements.get(name);};
  function listen(type,fn,opts){const key=(opts===true||opts?.capture?'capture:':'')+type;if(!listeners.has(key))listeners.set(key,[]);listeners.get(key).push(fn);}
  const meta={id:'stream',navigation_id:'nav',cols:8,rows:1,fps:8,chunk_frames:16,source_start:30,range_start:30,range_end:90};
  class Source {
    constructor(){instance=this;this.starts=0;this.stops=0;this.polls=[];this.end=34;this.complete=false;this.total=480;this.hex='80';this.meta=null;this.error=null;}
    async start(){this.starts++;const data=this.startGate?await this.startGate.promise:meta;this.meta=this.rangeEnd?{...data,range_end:this.rangeEnd}:data;return this.meta;}
    stop(){this.stops++;this.meta=null;return this.stopGate?.promise || Promise.resolve(true);}
    async poll(options){this.polls.push(options);if(this.pollGate)return this.pollGate.promise;
      if(this.error)throw this.error;
      return {state:this.complete?'complete':'running',total_frames:this.complete?this.total:null};}
    frameAt(at){if(!this.meta||at>=this.end-1e-8)return null;const n=Math.min(this.complete?this.total-1:99999,Math.max(0,Math.floor((at-30)*8+1e-7)));return {hex:this.hex,cols:8,rows:1,fps:8,sourceTime:30+n/8,frameIndex:n};}
    bufferedUntil(){return this.end;}
  }
  const sandbox={console,window:null,document:{hidden:false,getElementById:get,createElement:element,addEventListener:listen},
    wapflixLiveConfig:config,WapflixStreamSource:Source,requestAnimationFrame:fn=>{queue.push(fn);return ++id;},
    setInterval:(fn,ms)=>{const n=++id;timers.set(n,{fn,ms});return n;},clearInterval:n=>timers.delete(n),
    addEventListener:listen,localStorage:{setItem:()=>calls.writes++,removeItem:()=>calls.writes++},
    performance:{now:()=>now}, calls};
  sandbox.window=sandbox;
  const ctx=vm.createContext(sandbox);
  // These are lexical globals, NOT window.view/window.token.
  vm.runInContext(`
    const $=id=>document.getElementById(id),ctx=$('display').getContext('2d'),ink='#25371e';
    let view='details',item=null,clip=null,message='',detail=false,playing=false,last=0,frame=-1,token=7;
    function text(s,x,y){ctx.fillRect(x,y,String(s).length,1);}
    function center(s,y){text(s,0,y);} function wrap(s){return [s];}
    function announce(s){$('summary').textContent=s;}
    function setPlaying(value){playing=value;last=0;}
    function render(){calls.render++;} function paint(){calls.paint++;}
    function load(e){calls.load++;item=e;view='player';clip={frames:['static']};return Promise.resolve();}
    function select(){calls.select++;} function back(){calls.back++;view='home';}
    function key(v){calls.key.push(v);if(v==='*'){view='home';clip=null;}if(v==='#')render();}
    function tick(t){calls.staticTick++;requestAnimationFrame(tick);}
    requestAnimationFrame(tick);
  `,ctx);
  vm.runInContext(source,ctx,{filename:'handset-live.js'});
  queue.shift()(0); // The queued bootstrap callback hands off to the new global tick.
  const run=s=>vm.runInContext(s,ctx);
  return {run,calls,queue,timers,elements,contexts,ctx,listeners,
    get adapter(){return instance;}, snapshot:()=>sandbox.wapflixLive?.snapshot(),
    async play(){ctx.load(entry);await flush();},
    async poll(){for(const t of [...timers.values()])t.fn();await flush();},
    raf(t){now=t;const pending=queue.splice(0);for(const fn of pending)fn(t);assert.equal(queue.length,1,'exactly one successor callback');},
    event(type,target={},extra={}){const event={type,target:{closest:()=>null,...target},preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...extra};for(const fn of listeners.get('capture:'+type)||[])fn(event);return event;},
    async fire(type){for(const fn of listeners.get(type)||[])fn();await flush();}
  };
}

test('static path and absent capability remain inert',async()=>{
  for(const cfg of [undefined,null]){const e=environment(cfg===undefined?{token:'x'}:null);e.ctx.load({id:'static'});await flush();assert.equal(e.calls.load,1);assert.equal(e.run('view'),'player');}
  const e=environment(null);e.ctx.load(entry);assert.equal(e.calls.load,1);assert.equal(e.adapter,undefined);
});
test('recognition needs exact ID and explicit playback type',()=>{
  const e=environment();e.ctx.load({id:'local-stream-test-extra',playback_type:'local-stream'});e.ctx.load({id:'local-stream-test'});assert.equal(e.calls.load,2);
});
test('uses lexical handset state, keeps clip null, invalidates static token',async()=>{
  const e=environment();await e.play();assert.equal(e.run('view'),'live-player');assert.equal(e.ctx.view,undefined);assert.equal(e.run('clip'),null);assert.equal(e.run('playing'),false);assert.equal(e.run('token'),8);assert.equal(e.calls.load,0);assert.equal(e.calls.writes,0);
});
test('one pre-existing animation chain and one 250ms timer across repeated Play',async()=>{
  const e=environment();await e.play();await e.play();await e.play();assert.equal(e.adapter.starts,1);assert.equal(e.timers.size,1);assert.equal([...e.timers.values()][0].ms,250);assert.equal(e.queue.length,1);e.raf(1000);e.raf(1137);assert.equal(e.calls.staticTick,1);assert.equal(e.queue.length,1);
});
test('smooth clock and presented frame time stay distinct',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(1137);assert.ok(Math.abs(e.snapshot().position-.137)<1e-8);assert.equal(e.snapshot().presentedSourceTime,30.125);assert.equal(e.snapshot().presentedFrameIndex,1);
});
test('four second startup target actually gates presentation',async()=>{
  const e=environment();e.adapter.end=32;await e.play();assert.equal(e.snapshot().state,'buffering');e.raf(1000);e.raf(9000);assert.equal(e.snapshot().position,0);e.adapter.end=34;await e.poll();assert.equal(e.snapshot().state,'playing');e.raf(10000);assert.equal(e.snapshot().position,0);
});
test('startup short-complete exception includes a one-frame extract',async()=>{
  const e=environment();e.adapter.complete=true;e.adapter.total=1;e.adapter.end=30.125;await e.play();assert.equal(e.snapshot().state,'playing');e.raf(1000);e.raf(1125);assert.equal(e.snapshot().state,'ended');assert.equal(e.snapshot().presentedFrameIndex,0);assert.equal(e.timers.size,0);await flush();assert.equal(e.adapter.stops,1);
});
test('underflow freezes smooth position, image, and keeps polling',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(1100);const before=e.snapshot();e.adapter.end=30.2;e.raf(1500);assert.equal(e.snapshot().state,'buffering');assert.equal(e.snapshot().position,before.position);assert.equal(e.snapshot().presentedSourceTime,before.presentedSourceTime);assert.equal(e.timers.size,1);const n=e.adapter.polls.length;await e.poll();assert.equal(e.adapter.polls.length,n+1);e.raf(9000);assert.equal(e.snapshot().position,before.position);
});
test('rebuffer recovery needs one chunk and resets wall-clock reference',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(1100);e.adapter.end=30.2;e.raf(1500);e.adapter.end=31;await e.poll();assert.equal(e.snapshot().state,'buffering');e.adapter.end=32.2;await e.poll();assert.equal(e.snapshot().state,'playing');e.raf(9000);assert.ok(Math.abs(e.snapshot().position-.1)<1e-8);e.raf(9137);assert.ok(Math.abs(e.snapshot().position-.237)<1e-8);
});
for(const tailFrames of [1,5])test('completed rebuffer tail of '+tailFrames+' frame(s) drains to final frame',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(2000);e.adapter.end=31.01;e.raf(3000);assert.equal(e.snapshot().state,'buffering');e.adapter.complete=true;e.adapter.total=8+tailFrames;e.adapter.end=30+e.adapter.total/8;await e.poll();assert.equal(e.snapshot().state,'playing');e.raf(5000);e.raf(6000);assert.equal(e.snapshot().state,'ended');assert.equal(e.snapshot().presentedFrameIndex,e.adapter.total-1);assert.equal(e.snapshot().position,e.adapter.total/8);assert.equal(e.timers.size,0);
});
test('conversion complete does not end playback early',async()=>{
  const e=environment();e.adapter.complete=true;e.adapter.total=48;e.adapter.end=36;await e.play();assert.equal(e.snapshot().state,'playing');e.raf(1000);e.raf(2000);assert.equal(e.snapshot().state,'playing');assert.equal(e.snapshot().position,1);assert.equal(e.adapter.stops,0);
});
test('Back during pending Start stops immediately and rejects late acknowledgement',async()=>{
  const e=environment();const gate=deferred();e.adapter.startGate=gate;e.ctx.load(entry);assert.equal(e.snapshot().state,'starting');e.ctx.back();assert.equal(e.run('view'),'details');assert.equal(e.adapter.stops,1);gate.resolve({source_start:30,range_end:90});await flush();assert.equal(e.run('view'),'details');assert.equal(e.timers.size,0);assert.equal(e.snapshot().state,'idle');
});
test('stale Start rejection cannot replace navigation with error',async()=>{
  const e=environment();const gate=deferred();e.adapter.startGate=gate;e.ctx.load(entry);e.ctx.back();gate.reject(Error('late error'));await flush();assert.equal(e.snapshot().state,'idle');assert.equal(e.run('view'),'details');
});
for(const reject of [false,true])test('stale poll '+(reject?'rejection':'reply')+' cannot resurrect after exit',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.pollGate=gate;const polling=e.poll();e.ctx.back();reject?gate.reject(Error('late')):gate.resolve({state:'complete',total_frames:1});await polling;await flush();assert.equal(e.run('view'),'details');assert.equal(e.snapshot().state,'idle');assert.equal(e.timers.size,0);e.raf(8000);assert.equal(e.calls.staticTick,2);
});
test('concurrent interval callbacks do not overlap bridge poll',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.pollGate=gate;const n=e.adapter.polls.length;e.poll();e.poll();e.poll();assert.equal(e.adapter.polls.length,n+1);gate.resolve({state:'running'});await flush();
});
test('key 5 still cancels unacknowledged Start',async()=>{
  const e=environment();e.adapter.startGate=deferred();e.ctx.load(entry);await flush();
  assert.equal(e.snapshot().state,'starting');e.ctx.key('5');
  assert.equal(e.run('view'),'details');assert.equal(e.adapter.stops,1);assert.equal(e.snapshot().state,'idle');
});
test('Stop cleanup failure is visible, not falsely confirmed',async()=>{
  const e=environment();await e.play();e.adapter.stopGate=deferred();e.ctx.back();assert.equal(e.run('view'),'details');assert.equal(e.snapshot().cleanupPending,true);e.adapter.stopGate.reject(Error('network lost'));await flush();assert.equal(e.snapshot().cleanupUnconfirmed,true);assert.match(e.elements.get('summary').textContent,/UNCONFIRMED/);
});
test('static switch waits for cleanup then delegates, preserving return state',async()=>{
  const e=environment();await e.play();e.adapter.stopGate=deferred();const switching=e.ctx.load({id:'static'});assert.equal(e.calls.load,0);e.adapter.stopGate.resolve(true);await switching;assert.equal(e.calls.load,1);assert.equal(e.run('view'),'player');assert.equal(e.snapshot().pollTimer,false);
});
test('old delayed static switch cannot overwrite a newer load',async()=>{
  const e=environment();await e.play();e.adapter.stopGate=deferred();const switching=e.ctx.load({id:'old'});e.ctx.load({id:'new'});e.adapter.stopGate.resolve(true);await switching;assert.equal(e.calls.load,1);assert.equal(e.run('item.id'),'new');
});
test('static switch is cancelled if cleanup fails',async()=>{
  const e=environment();await e.play();e.adapter.stopGate=deferred();const switching=e.ctx.load({id:'static'});e.adapter.stopGate.reject(Error('failed'));await switching;assert.equal(e.calls.load,0);assert.match(e.elements.get('summary').textContent,/cancelled/);
});
test('Home delegates to original navigation rather than fake pagehide/window.page',async()=>{
  const e=environment();await e.play();e.ctx.key('*');assert.equal(e.run('view'),'home');assert.deepEqual(e.calls.key,['*']);assert.equal(e.adapter.stops,1);assert.equal(e.ctx.page,undefined);
});
for(const event of ['visibilitychange','pagehide'])test(event+' applies the current visibility/exit policy',async()=>{
  const e=environment();await e.play();e.ctx.document.hidden=true;await e.fire(event);
  if(event==='visibilitychange'){
    assert.equal(e.adapter.stops,0);assert.equal(e.run('view'),'live-player');assert.equal(e.snapshot().state,'paused');assert.equal(e.timers.size,1);
  }else{assert.equal(e.adapter.stops,1);assert.equal(e.run('view'),'details');assert.equal(e.timers.size,0);}
});
test('unsupported numeric actions never reach static handlers; backlight still delegates',async()=>{
  const e=environment();await e.play();for(const k of ['0','1','2','3','4','6','7','8','9']){e.ctx.key(k);assert.match(e.elements.get('summary').textContent,/unavailable/);}assert.deepEqual(e.calls.key,[]);e.ctx.key('#');assert.deepEqual(e.calls.key,['#']);assert.equal(e.snapshot().state,'playing');
});
test('physical rocker/roller movement, wheel and keyboard arrows are navigation origins',async()=>{
  const e=environment();await e.play();for(const type of ['click','wheel']){const target={closest:selector=>selector==='.roller-press'?null:({classList:{contains:()=>false}})};const event=e.event(type,target);assert.equal(event.stopped,true);assert.match(e.elements.get('summary').textContent,/Navigation/);}const arrow=e.event('keydown',{}, {key:'ArrowUp'});assert.equal(arrow.stopped,true);assert.deepEqual(e.calls.key,[]);
});
test('roller press is Select/Pause, never interpreted as movement',async()=>{
  const e=environment();await e.play();const press={classList:{contains:c=>c==='roller-press'}};
  e.event('click',{closest:()=>press});assert.equal(e.adapter.stops,0);
  assert.equal(e.run('view'),'live-player');assert.equal(e.snapshot().state,'paused');
});
test('pixels are cleared for every decoded frame; LCD scene is 200px high',async()=>{
  const e=environment();await e.play();e.raf(1000);e.adapter.hex='00';e.raf(1137);const pixelLog=e.contexts[1].log;const lastClear=pixelLog.map(x=>x[0]).lastIndexOf('clearRect');assert.ok(lastClear>=0);assert.equal(pixelLog.slice(lastClear+1).filter(x=>x[0]==='fillRect').length,0);const draw=e.elements.get('display').context.log.filter(x=>x[0]==='drawImage').at(-1);assert.ok(draw[3]+draw[5]<=200);assert.equal(e.elements.get('left').attrs['aria-label'],'PAUSE');assert.equal(e.elements.get('back').attrs['aria-label'],'BACK');
});
test('transport timeout stays distinct; error has usable Back and no leaked timer',async()=>{
  const e=environment();await e.play();e.adapter.error=Object.assign(Error('deadline'),{name:'TimeoutError'});await e.poll();assert.equal(e.snapshot().state,'error');assert.match(e.elements.get('summary').textContent,/TRANSPORT TIMEOUT/);assert.equal(e.timers.size,0);e.ctx.back();assert.equal(e.run('view'),'details');
});
test('late cleanup completion cannot return a newer live view to idle/details',async()=>{
  const e=environment();await e.play();e.adapter.stopGate=deferred();e.ctx.back();await e.play();const g=e.snapshot().generation;e.adapter.stopGate.resolve(true);await flush();assert.equal(e.run('view'),'live-player');assert.equal(e.snapshot().generation,g);assert.equal(e.snapshot().state,'playing');
});
test('fractional configured endpoint completes without requesting an out-of-range timestamp',async()=>{
  const e=environment();e.adapter.rangeEnd=30.15;e.adapter.end=30.15;e.adapter.complete=true;e.adapter.total=2;
  const original=e.adapter.frameAt.bind(e.adapter);
  e.adapter.frameAt=at=>{assert.ok(at<=30.15+1e-7,'timestamp within configured range');return original(at);};
  await e.play();assert.equal(e.snapshot().state,'playing');e.raf(1000);e.raf(2000);assert.equal(e.snapshot().state,'ended');assert.equal(e.snapshot().presentedSourceTime,30.125);
});
test('wheel over roller press never selects/stops; modified wheel preserves browser zoom',async()=>{
  const e=environment();await e.play();const press={classList:{contains:c=>c==='roller-press'}};
  const movement=e.event('wheel',{closest:()=>press});assert.equal(movement.stopped,true);assert.equal(e.adapter.stops,0);assert.equal(e.run('view'),'live-player');
  const zoom=e.event('wheel',{closest:()=>press},{ctrlKey:true});assert.equal(zoom.prevented,undefined);assert.equal(e.adapter.stops,0);
});
test('return screen captured from episodes is preserved through EOF and Back',async()=>{
  const e=environment();e.run("view='episodes'");e.adapter.complete=true;e.adapter.total=1;e.adapter.end=30.125;
  await e.play();e.raf(1000);e.raf(2000);assert.equal(e.snapshot().state,'ended');e.ctx.back();assert.equal(e.run('view'),'episodes');
});
