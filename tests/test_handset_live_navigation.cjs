// 5A.4B isolated navigation/focus/control tests. Not a browser or real-server test.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const SOURCE=fs.readFileSync(path.join(__dirname,'..','handset-live.js'),'utf8');
const entry={id:'local-stream-test',playback_type:'local-stream'};
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const flush=async()=>{for(let n=0;n<16;n++)await Promise.resolve();};
function environment(model='3310'){
  const listeners=new Map(),timers=new Map(),queue=[],nodes=[],observers=[];
  const calls={loads:[],keys:[],staticSelect:0,staticBack:0,staticTick:0,writes:0};
  let id=0,adapter,ctx,document;
  function canvasContext(){const log=[];const c={log};for(const key of ['clearRect','fillRect','drawImage'])c[key]=(...args)=>log.push([key,...args]);return c;}
  function element(name,selectors=[],label=null){
    const attrs={};if(label!==null)attrs['aria-label']=label;
    const context=canvasContext();const e={id:name,attrs,selectors:new Set(selectors),isConnected:true,disabled:false,inert:false,
      dataset:{},width:0,height:0,textContent:'',context,onclick:null,focusCalls:0,
      getContext:()=>context,getAttribute:k=>Object.hasOwn(attrs,k)?attrs[k]:null,
      setAttribute:(k,v)=>attrs[k]=String(v),removeAttribute:k=>delete attrs[k],
      focus(){this.focusCalls++;document.activeElement=this;},
      classList:{contains:c=>selectors.includes('.'+c)},
      closest(selector){if(selector==='[inert]')return this.inertAncestor?this:null;
        return selector.split(',').some(s=>this.selectors.has(s.trim()))?this:null;}
    };nodes.push(e);return e;
  }
  const elements=new Map();
  const get=name=>{if(!elements.has(name))elements.set(name,element(name));return elements.get(name);};
  const phone=element('phone',['.phone']);
  const keypad={};for(const digit of '0123456789*#'){
    const e=element('numeric-'+digit,['.keypad [data-key="'+digit+'"]'],digit==='5'?null:'Static '+digit);
    e.dataset.key=digit;keypad[digit]=e;
  }
  get('summary');
  const left=get('left'),back=get('back');left.setAttribute('aria-label','PLAY');back.setAttribute('aria-label','BACK');
  function addPhysical(name,cls,label,action){const e=element(name,[cls],label);e.onclick=()=>action();return e;}
  let physical={};
  function setModel(next){
    for(const e of Object.values(physical))e.isConnected=false;
    physical={};model=next;
    physical.up=addPhysical('up','.handset-up','Scroll up',()=>ctx.key('2'));
    physical.down=addPhysical('down','.handset-down','Scroll down',()=>ctx.key('8'));
    if(!['3210','3310'].includes(next)){
      physical.call=addPhysical('call','.handset-call','Select or play and pause',()=>ctx.select());
      physical.end=addPhysical('end','.handset-end','Return home',()=>ctx.key('*'));
    }
    if(next==='7110'){
      physical.roller=element('roller',['.handset-roller'],'Navi roller');
      physical.press=addPhysical('press','.roller-press','Press roller to select or play and pause',()=>ctx.select());
      physical.rollUp=addPhysical('roll-up','.roller-up','Roll up',()=>ctx.key('2'));
      physical.rollDown=addPhysical('roll-down','.roller-down','Roll down',()=>ctx.key('8'));
      for(const e of [physical.press,physical.rollUp,physical.rollDown]){
        const own=e.closest.bind(e);e.closest=s=>s.includes('.handset-roller')?physical.roller:own(s);
      }
    }
    for(const o of observers)o.callback([{type:'childList'}]);
  }
  const listen=(type,fn,opts)=>{const key=(opts===true||opts?.capture?'capture:':'')+type;
    if(!listeners.has(key))listeners.set(key,[]);listeners.get(key).push(fn);};
  document={activeElement:left,hidden:false,getElementById:get,createElement:name=>element(name),
    querySelector:s=>s==='.phone'?phone:null,
    querySelectorAll:selector=>nodes.filter(e=>e.isConnected&&selector.split(',').some(s=>e.selectors.has(s.trim()))),
    addEventListener:listen};
  class Source{
    constructor(){adapter=this;this.starts=0;this.stops=0;this.polls=[];this.end=38;this.total=64;this.complete=false;this.meta=null;}
    async start(){this.starts++;const m=this.startGate?await this.startGate.promise:{source_start:30,range_end:90,fps:8,chunk_frames:16};this.meta=m;return m;}
    stop(){this.stops++;this.meta=null;return this.stopGate?.promise||Promise.resolve(true);}
    async poll(options){this.polls.push(options);if(this.pollGate)return this.pollGate.promise;
      return {state:this.complete?'complete':'running',total_frames:this.complete?this.total:null};}
    bufferedUntil(){return this.end;}
    frameAt(at){if(!this.meta||at>=this.end)return null;const n=Math.floor((at-30)*8+1e-7);
      return {hex:'80',cols:8,rows:1,frameIndex:n,sourceTime:30+n/8};}
  }
  class Observer{constructor(callback){this.callback=callback;observers.push(this);}observe(target,options){this.target=target;this.options=options;}}
  const sandbox={window:null,document,WapflixStreamSource:Source,wapflixLiveConfig:{token:'test-only',apiBase:'/'},
    MutationObserver:Observer,console,calls,requestAnimationFrame:fn=>{queue.push(fn);return ++id;},
    setInterval:(fn,ms)=>{const n=++id;timers.set(n,{fn,ms});return n;},clearInterval:n=>timers.delete(n),addEventListener:listen};
  sandbox.window=sandbox;ctx=vm.createContext(sandbox);
  vm.runInContext(`
    const $=id=>document.getElementById(id),ctx=$('display').getContext('2d'),ink='#25371e';
    let view='details',item=null,clip=null,message='',detail=false,playing=false,last=0,frame=-1,token=7;
    function text(value,x,y){ctx.fillRect(x,y,String(value).length,1);}function center(s,y){text(s,0,y);}function wrap(s){return [s];}
    function announce(s){$('summary').textContent=s;}function setPlaying(on){playing=on;last=0;}
    function render(){}function paint(){}
    function load(e,keep=false,options={}){calls.loads.push({e,keep,options});view='player';item=e;clip={frames:['static']};return Promise.resolve();}
    function select(){calls.staticSelect++;}function back(){calls.staticBack++;view='home';}
    function key(k){calls.keys.push(k);if(k==='*'){view='home';clip=null;}if(k==='#')render();}
    function tick(t){calls.staticTick++;requestAnimationFrame(tick);}requestAnimationFrame(tick);
  `,ctx);
  setModel(model);
  vm.runInContext(SOURCE,ctx,{filename:'handset-live.js'});queue.shift()(0);
  left.onclick=()=>ctx.select();back.onclick=()=>ctx.back();for(const [k,e]of Object.entries(keypad))e.onclick=()=>ctx.key(k);
  const run=s=>vm.runInContext(s,ctx);
  const event=(type,target,extra={})=>{
    const e={type,target,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...extra};
    for(const fn of listeners.get('capture:'+type)||[]){fn(e);if(e.stopped)break;}return e;
  };
  return {ctx,run,calls,timers,queue,elements,keypad,left,back,document,observers,element,setModel,
    get physical(){return physical;},get adapter(){return adapter;},snapshot:()=>sandbox.wapflixLive.snapshot(),
    async play(){ctx.load(entry);await flush();},
    click(target){document.activeElement=target;const e=event('click',target);if(!e.stopped)target.onclick?.();return e;},
    event,async poll(){for(const t of [...timers.values()])t.fn();await flush();},
    raf(t){const pending=queue.splice(0);for(const fn of pending)fn(t);assert.equal(queue.length,1);},
    async fire(type){for(const fn of listeners.get(type)||[])fn();await flush();}
  };
}

for(const model of ['3210','3310','8210','6310','7110']){
  test(model+' Select/key5 labels agree with Pause/Resume and Back',async()=>{
    const e=environment(model);await e.play();assert.equal(e.left.attrs['aria-label'],'PAUSE');
    assert.equal(e.keypad['5'].attrs['aria-label'],'Pause live playback');
    const select=e.physical.press||e.physical.call||e.left;
    e.click(select);await flush();assert.equal(e.snapshot().state,'paused');assert.equal(e.left.attrs['aria-label'],'RESUME');
    assert.equal(e.keypad['5'].attrs['aria-label'],'Resume live playback');
    if(e.physical.call)assert.equal(e.physical.call.attrs['aria-label'],'Resume live playback');
    e.click(e.keypad['5']);await flush();assert.equal(e.snapshot().state,'playing');e.click(e.back);
    assert.equal(e.run('view'),'details');assert.equal(e.adapter.stops,1);
  });
  test(model+' physical movement cannot toggle captions or change play intent',async()=>{
    const e=environment(model);await e.play();const before=e.snapshot();
    e.click(e.physical.up);e.click(e.physical.down);
    assert.equal(e.snapshot().playIntent,before.playIntent);assert.equal(e.snapshot().position,before.position);
    assert.deepEqual(e.calls.keys,[]);assert.match(e.elements.get('summary').textContent,/Navigation unavailable/);
    e.click(e.keypad['2']);assert.match(e.elements.get('summary').textContent,/Caption toggle unavailable/);
  });
  test(model+' live labels are restored exactly on exit',async()=>{
    const e=environment(model);const before=e.keypad['2'].getAttribute('aria-label');
    await e.play();assert.equal(e.keypad['2'].attrs['aria-disabled'],'true');e.ctx.back();
    assert.equal(e.keypad['2'].getAttribute('aria-label'),before);assert.equal(e.keypad['2'].getAttribute('aria-disabled'),null);
    assert.equal(e.keypad['5'].getAttribute('aria-label'),null);
    if(e.physical.call)assert.equal(e.physical.call.attrs['aria-label'],'Select or play and pause');
  });
}

test('Back restores launch screen, summary and actual launch focus immediately',async()=>{
  const e=environment();const focus=e.element('launch',['button'],'Launch');e.document.activeElement=focus;
  e.elements.get('summary').textContent='PLAY LOCAL STREAM';e.run("view='episodes'");await e.play();
  e.adapter.stopGate=deferred();e.click(e.back);assert.equal(e.run('view'),'episodes');
  assert.equal(e.document.activeElement,focus);assert.equal(e.elements.get('summary').textContent,'PLAY LOCAL STREAM');
  e.adapter.stopGate.resolve(true);await flush();assert.equal(e.document.activeElement,focus);
});
for(const unavailable of ['disconnected','disabled','inert','ancestor-inert'])test('focus fallback when launch control is '+unavailable,async()=>{
  const e=environment();const focus=e.element('launch',['button'],'Launch');e.document.activeElement=focus;await e.play();
  if(unavailable==='disconnected')focus.isConnected=false;if(unavailable==='disabled')focus.disabled=true;
  if(unavailable==='inert')focus.inert=true;if(unavailable==='ancestor-inert')focus.inertAncestor=true;
  e.ctx.back();assert.equal(e.document.activeElement,e.left);
});
test('Home restores a stable Home control rather than the old launch focus',async()=>{
  const e=environment('8210');const focus=e.element('launch',[],'Launch');e.document.activeElement=focus;
  await e.play();e.click(e.physical.end);assert.equal(e.run('view'),'home');assert.equal(e.document.activeElement,e.left);
});
test('Back then static load waits for the pending Stop acknowledgement',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.stopGate=gate;e.ctx.back();
  const options={resume:true,autoplay:true};const pending=e.ctx.load({id:'static'},true,options);
  assert.equal(e.calls.loads.length,0);gate.resolve(true);await pending;
  assert.equal(e.calls.loads.length,1);assert.equal(e.calls.loads[0].keep,true);assert.deepEqual(e.calls.loads[0].options,options);
});
test('latest static intent wins while Stop is pending',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.stopGate=gate;e.ctx.back();
  const first=e.ctx.load({id:'old'}),second=e.ctx.load({id:'new'});assert.equal(e.calls.loads.length,0);
  gate.resolve(true);await Promise.all([first,second]);assert.equal(e.calls.loads.length,1);assert.equal(e.calls.loads[0].e.id,'new');
});
test('backlight while Stop is pending does not cancel the chosen static load',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.stopGate=gate;
  const pending=e.ctx.load({id:'static'});e.ctx.key('#');gate.resolve(true);await pending;
  assert.equal(e.calls.loads.length,1);assert.deepEqual(e.calls.keys,['#']);
});
test('Back navigation cancels a queued static switch',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.stopGate=gate;
  const pending=e.ctx.load({id:'static'});e.ctx.back();gate.resolve(true);await pending;assert.equal(e.calls.loads.length,0);
});
test('failed cleanup after Back blocks static playback, explicit retry can recover',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.stopGate=gate;e.ctx.back();
  const pending=e.ctx.load({id:'static'});gate.reject(Error('network'));await pending;assert.equal(e.calls.loads.length,0);
  assert.match(e.elements.get('summary').textContent,/Static load cancelled/);e.adapter.stopGate=null;
  await e.ctx.load({id:'static'});assert.equal(e.calls.loads.length,1);assert.equal(e.adapter.stops,2);
});
test('stale cleanup failure cannot overwrite a newer navigation announcement',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.stopGate=gate;
  const pending=e.ctx.load({id:'static'});e.ctx.back();e.elements.get('summary').textContent='NEW NAVIGATION';
  gate.reject(Error('old failure'));await pending;await flush();assert.equal(e.elements.get('summary').textContent,'NEW NAVIGATION');
});
test('fresh live intent supersedes a pending static switch without a late repaint',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.stopGate=gate;
  const pending=e.ctx.load({id:'static'});await e.play();gate.resolve(true);await pending;await flush();
  assert.equal(e.run('view'),'live-player');assert.equal(e.calls.loads.length,0);assert.equal(e.timers.size,1);
});
test('return from pending Start restores focus; late Start acknowledgement is ignored',async()=>{
  const e=environment();const gate=deferred();e.adapter.startGate=gate;e.ctx.load(entry);
  assert.equal(e.keypad['5'].attrs['aria-label'],'Cancel live startup');e.ctx.back();assert.equal(e.document.activeElement,e.left);
  gate.resolve({source_start:30,range_end:90,fps:8,chunk_frames:16});await flush();assert.equal(e.run('view'),'details');assert.equal(e.timers.size,0);
});
test('model replacement refreshes new controls while paused without a timer or Start',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();e.setModel('7110');
  assert.equal(e.physical.press.attrs['aria-label'],'Resume live playback');
  assert.equal(e.physical.rollUp.attrs['aria-disabled'],'true');assert.equal(e.adapter.starts,1);assert.equal(e.timers.size,1);
  e.click(e.physical.press);await flush();assert.equal(e.snapshot().state,'playing');
  e.ctx.back();assert.equal(e.physical.press.attrs['aria-label'],'Press roller to select or play and pause');
});
test('observer cannot loop on its own aria-label writes',()=>{
  const e=environment();assert.equal(e.observers.length,1);
  assert.equal(e.observers[0].options.childList,true);assert.deepEqual(Array.from(e.observers[0].options.attributeFilter),['data-handset']);
});
test('7110 wheel over press never selects; modified wheel remains native',async()=>{
  const e=environment('7110');await e.play();const event=e.event('wheel',e.physical.press,{deltaY:80});
  assert.equal(event.stopped,true);assert.equal(e.snapshot().state,'playing');assert.equal(e.adapter.stops,0);
  const zoom=e.event('wheel',e.physical.press,{deltaY:80,ctrlKey:true});assert.equal(zoom.prevented,undefined);
});
test('keyboard arrows distinguish navigation from numeric 2 and respect native fields',async()=>{
  const e=environment();await e.play();const target=e.element('body');
  const arrow=e.event('keydown',target,{key:'ArrowUp'});assert.equal(arrow.stopped,true);
  e.ctx.key('2');assert.match(e.elements.get('summary').textContent,/Caption toggle/);
  for(const selector of ['input','select','textarea','[contenteditable]','.handset-tools','dialog']){
    const field=e.element('field',[selector]);const native=e.event('keydown',field,{key:'ArrowDown'});assert.equal(native.stopped,undefined);
  }
});
test('explicit terminal replay creates one fresh session and retains original launch focus',async()=>{
  const e=environment();const focus=e.element('launch');e.document.activeElement=focus;e.adapter.complete=true;e.adapter.total=1;e.adapter.end=30.125;
  await e.play();e.raf(1000);e.raf(1125);assert.equal(e.snapshot().state,'ended');await flush();
  e.adapter.complete=false;e.adapter.end=38;await e.play();assert.equal(e.adapter.starts,2);assert.equal(e.timers.size,1);
  e.ctx.back();assert.equal(e.document.activeElement,focus);
});
test('repeated cycles retain exactly one RAF and at most one active timer',async()=>{
  const e=environment();for(let n=0;n<8;n++){
    await e.play();e.raf(1000+n*2000);assert.equal(e.timers.size,1);e.ctx.select();await flush();
    e.ctx.back();await flush();assert.equal(e.timers.size,0);e.raf(1500+n*2000);
  }assert.equal(e.adapter.starts,8);assert.equal(e.adapter.stops,8);
});
test('read-only input-origin matrix is explicit and cannot change bridge controls',()=>{
  const e=environment();assert.equal(e.ctx.wapflixLive.inputMatrix.rollerPress,'Select');assert.equal(e.ctx.wapflixLive.inputMatrix.numeric2,'Captions unavailable');
  assert.ok(Object.isFrozen(e.ctx.wapflixLive.inputMatrix));
});
test('all movement label overrides restore after switching through all five models',async()=>{
  const e=environment();await e.play();for(const model of ['3210','3310','8210','6310','7110'])e.setModel(model);
  assert.equal(e.physical.up.attrs['aria-label'],'Navigation unavailable during live playback');e.ctx.back();
  assert.equal(e.physical.up.attrs['aria-label'],'Scroll up');assert.equal(e.physical.up.getAttribute('aria-disabled'),null);
});
test('static controls delegate unchanged after live exit',async()=>{
  const e=environment();await e.play();e.ctx.back();await flush();e.ctx.select();e.ctx.key('2');
  assert.equal(e.calls.staticSelect,1);assert.deepEqual(e.calls.keys,['2']);
});
