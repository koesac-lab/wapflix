// 5A.5B: pure layout/controller tests and isolated real-bridge integration.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const selector=require('../live-captions.js');
const ui=require('../handset-captions.js');
const metadata=(cues=[],extra={})=>({timebase:'source',track_found:true,cues,selected_cue_count:cues.length,parse_error_count:0,...extra});
const cue=(start=30,end=32,text='CAPTION')=>({start,end,text});
function controller(){
  const panels=[],drawn=[],spoken=[];const context={fillStyle:'',fillRect(...args){panels.push({args,colour:this.fillStyle});}};
  let colour='#a6bd70';const c=ui.create({selector,context,drawText:(...args)=>drawn.push(args),onText:t=>spoken.push(t),panelColour:()=>colour});
  return {c,panels,drawn,spoken,dim(){colour='#7c8c62';}};
}
test('wraps words within 38 glyph columns',()=>{
  const lines=ui.layoutLines(['ONE '.repeat(14)]);assert.ok(lines.length<=3);assert.ok(lines.every(s=>Array.from(s).length<=38));
});
test('hard-wraps unbroken long words instead of overflowing the LCD',()=>{
  const lines=ui.layoutLines(['X'.repeat(90)]);assert.deepEqual(lines.map(s=>s.length),[38,38,14]);
});
test('caps display at three lines with a visible truncation marker',()=>{
  const lines=ui.layoutLines(['A','B','C','D']);assert.deepEqual(lines,['A','B','C...']);assert.ok(Object.isFrozen(lines));
});
test('retains overlap line order and returns no rows for empty selection',()=>{
  assert.deepEqual(ui.layoutLines(['FIRST','SECOND']),['FIRST','SECOND']);assert.deepEqual(ui.layoutLines([]),[]);
});
test('caption plate stays within the scene and above status/footer rows',()=>{
  const t=controller();t.c.setTrack(metadata([cue(30,32,'A\nB\nC')]));t.c.draw({sourceTime:30});
  assert.deepEqual(t.panels[0].args,[0,140,240,38]);assert.equal(t.panels[0].args[1]+t.panels[0].args[3],178);
});
test('uses the existing light/dim LCD palette',()=>{
  const t=controller();t.c.setTrack(metadata([cue()]));t.c.draw({sourceTime:30});assert.equal(t.panels.at(-1).colour,'#a6bd70');
  t.dim();t.c.draw({sourceTime:30});assert.equal(t.panels.at(-1).colour,'#7c8c62');
});
test('controller selects the presented source time without adding an offset',()=>{
  const t=controller();t.c.setTrack(metadata([cue(30,31,'CORRECT'),cue(60,61,'WRONG')]));t.c.draw({sourceTime:30.125,source_start:30});
  assert.equal(t.c.snapshot().text,'CORRECT');assert.equal(t.c.snapshot().sourceTime,30.125);
});
test('announces changed cue text, not repeated renders of the same cue',()=>{
  const t=controller();t.c.setTrack(metadata([cue()]));for(let n=0;n<20;n++)t.c.draw({sourceTime:30+n/100});assert.deepEqual(t.spoken,['CAPTION']);
  t.c.draw({sourceTime:33});assert.deepEqual(t.spoken,['CAPTION','']);
});
test('toggle off/on clears/restores text without changing the track',()=>{
  const t=controller();t.c.setTrack(metadata([cue()]));t.c.draw({sourceTime:30});t.c.toggle();t.c.draw({sourceTime:30});
  assert.equal(t.c.snapshot().text,'');assert.equal(t.c.snapshot().cueCount,1);t.c.toggle();t.c.draw({sourceTime:30});assert.equal(t.c.snapshot().text,'CAPTION');
});
test('clear removes cues and accessibility text but preserves page preference',()=>{
  const t=controller();t.c.setTrack(metadata([cue()]));t.c.toggle();t.c.clear();assert.equal(t.c.snapshot().loaded,false);assert.equal(t.c.snapshot().cueCount,0);assert.equal(t.c.enabled,false);
  t.c.setTrack(metadata([cue()]));t.c.draw({sourceTime:30});assert.equal(t.c.snapshot().text,'');
});
test('new page/controller defaults on independently of a prior controller',()=>{
  const old=controller();old.c.toggle();assert.equal(controller().c.enabled,true);
});
test('missing, empty and invalid tracks retain distinct diagnostics',()=>{
  const t=controller();assert.match(t.c.description(),/Waiting/);t.c.setTrack(null);assert.match(t.c.description(),/No subtitle track/);
  t.c.setTrack(metadata([]));assert.equal(t.c.snapshot().status,'ready');t.c.draw({sourceTime:30});assert.equal(t.c.snapshot().text,'');
  t.c.setTrack({timebase:'clip',cues:[],track_found:true});assert.match(t.c.description(),/invalid/);
});
test('parse warnings survive without disabling valid caption drawing',()=>{
  const t=controller();t.c.setTrack(metadata([cue()],{parse_error_count:2}));t.c.draw({sourceTime:30});assert.equal(t.c.snapshot().text,'CAPTION');assert.equal(t.c.snapshot().parseErrorCount,2);assert.match(t.c.description(),/warnings/);
});
test('inactive view and absent frame cannot draw or announce stale text',()=>{
  const t=controller();t.c.setTrack(metadata([cue()]));t.c.draw({sourceTime:30},false);t.c.draw(null);assert.equal(t.drawn.length,0);assert.equal(t.spoken.length,0);
});
test('markup-looking captions remain literal text in callbacks and canvas writes',()=>{
  const t=controller();const text='<script>not-code</script>';t.c.setTrack(metadata([cue(30,32,text)]));t.c.draw({sourceTime:30});assert.equal(t.spoken[0],text);assert.equal(t.drawn[0][0],text);
});
test('UI module export performs no DOM, fetch, storage, timer or animation work',()=>{
  const source=fs.readFileSync(path.join(__dirname,'..','handset-captions.js'),'utf8');const fail=()=>{throw Error('unexpected side effect');};
  const env={fetch:fail,setTimeout:fail,setInterval:fail,requestAnimationFrame:fail};Object.defineProperty(env,'document',{get:fail});Object.defineProperty(env,'localStorage',{get:fail});
  vm.runInNewContext(source,env);assert.equal(typeof env.WapflixHandsetCaptions.create,'function');
});

const harness=fs.readFileSync(path.join(__dirname,'test_handset_live_navigation.cjs'),'utf8');
const marker="for(const model of ['3210','3310','8210','6310','7110']){";
assert.equal(harness.split(marker).length,2,'known model harness');
const prefix=harness.split(marker)[0].replace('return {ctx,run,calls,timers','return {createdNodes:nodes,ctx,run,calls,timers');
const {environment,entry,deferred,flush}=new Function('require','__dirname',prefix+'\nreturn {environment,entry,deferred,flush};')(require,__dirname);
function app(model='3310',captions=metadata([cue()])){
  const e=environment(model);e.adapter.start=async function(){this.starts++;this.meta={source_start:30,range_end:90,fps:8,chunk_frames:16,captions};return this.meta;};return e;
}
function captionNode(e){return e.createdNodes.find(n=>n.id==='live-caption-status');}
function samePlayback(e,before){assert.equal(e.snapshot().position,before.position);assert.equal(e.snapshot().presentedSourceTime,before.presentedSourceTime);assert.equal(e.snapshot().state,before.state);}
for(const model of ['3210','3310','8210','6310','7110'])test(model+' numeric 2 toggles captions, physical movement does not',async()=>{
  const e=app(model);await e.play();assert.equal(e.snapshot().captions.text,'CAPTION');const before=e.snapshot();
  e.click(e.physical.up);e.click(e.physical.down);assert.equal(e.snapshot().captions.enabled,true);samePlayback(e,before);
  if(e.physical.roller)e.event('wheel',e.physical.roller,{deltaY:30});assert.equal(e.snapshot().captions.enabled,true);
  e.click(e.keypad['2']);assert.equal(e.snapshot().captions.enabled,false);assert.equal(e.snapshot().captions.text,'');samePlayback(e,before);
  assert.equal(e.keypad['2'].getAttribute('aria-pressed'),'false');assert.equal(e.keypad['2'].getAttribute('aria-disabled'),null);
  e.click(e.keypad['2']);assert.equal(e.snapshot().captions.text,'CAPTION');samePlayback(e,before);assert.equal(e.adapter.starts,1);assert.equal(e.adapter.stops,0);
});
test('caption time is quantised presented time rather than smooth position',async()=>{
  const e=app('3310',metadata([cue(30,30.13,'FIRST'),cue(30.13,31,'SECOND')]));await e.play();e.raf(1000);e.raf(1137);
  assert.ok(Math.abs(e.snapshot().position-.137)<1e-8);assert.equal(e.snapshot().captions.sourceTime,30.125);assert.equal(e.snapshot().captions.text,'FIRST');
});
test('Pause and rebuffering hold captions with the presented picture',async()=>{
  const e=app('3310',metadata([cue(30,31,'FIRST'),cue(31,33,'SECOND')]));await e.play();e.raf(1000);e.raf(1500);e.ctx.select();await flush();
  e.raf(90000);assert.equal(e.snapshot().captions.text,'FIRST');e.ctx.select();await flush();e.raf(100000);e.adapter.end=30.51;e.raf(101000);
  assert.equal(e.snapshot().state,'buffering');assert.equal(e.snapshot().captions.text,'FIRST');
});
test('toggle redraws the original picture but never loads/restarts/seeks',async()=>{
  const e=app();await e.play();const before=e.snapshot(),n=e.elements.get('display').context.log.filter(c=>c[0]==='drawImage').length;
  e.ctx.key('2');assert.ok(e.elements.get('display').context.log.filter(c=>c[0]==='drawImage').length>n);
  samePlayback(e,before);assert.equal(e.calls.loads.length,0);assert.equal(e.adapter.starts,1);assert.equal(e.calls.keys.length,0);
});
test('page preference survives Stop and new live session without storage writes',async()=>{
  const e=app();await e.play();e.ctx.key('2');e.ctx.back();await flush();await e.play();assert.equal(e.snapshot().captions.enabled,false);assert.equal(e.snapshot().captions.text,'');assert.equal(e.calls.writes,0);
});
test('static numeric 2 delegates unchanged and labels/pressed state restore on exit',async()=>{
  const e=app();const label=e.keypad['2'].getAttribute('aria-label');await e.play();e.ctx.key('2');e.ctx.back();await flush();
  assert.equal(e.keypad['2'].getAttribute('aria-label'),label);assert.equal(e.keypad['2'].getAttribute('aria-pressed'),null);assert.equal(e.keypad['2'].getAttribute('aria-disabled'),null);
  e.ctx.key('2');assert.deepEqual(e.calls.keys,['2']);assert.equal(e.snapshot().captions.enabled,false);
});
test('metadata with no track remains playable and is honestly reported on toggle',async()=>{
  const e=app('3310',metadata([],{track_found:false}));await e.play();assert.equal(e.snapshot().state,'playing');assert.equal(e.snapshot().captions.status,'missing');
  e.ctx.key('2');e.ctx.key('2');assert.match(e.elements.get('summary').textContent,/No subtitle track/);assert.equal(e.adapter.starts,1);
});
test('present empty extract and parser warnings remain separate diagnostics',async()=>{
  const e=app('3310',metadata([],{parse_error_count:3}));await e.play();assert.equal(e.snapshot().captions.status,'ready');assert.equal(e.snapshot().captions.parseErrorCount,3);assert.equal(e.snapshot().captions.text,'');
});
test('accessibility cue node is text-only and changes once per cue, not per tick',async()=>{
  const e=app();const node=captionNode(e);let writes=0,value=node.textContent;Object.defineProperty(node,'textContent',{get:()=>value,set:v=>{writes++;value=v;}});
  Object.defineProperty(node,'innerHTML',{get(){throw Error('HTML forbidden');},set(){throw Error('HTML forbidden');}});
  await e.play();const first=writes;e.raf(1000);e.raf(1100);e.ctx.render();assert.equal(writes,first);assert.equal(value,'CAPTION');
  e.ctx.key('2');assert.equal(value,'');assert.equal(writes,first+1);
});
test('caption panel uses dim palette without changing frame or toggle preference',async()=>{
  const e=app();e.run('let lit=false');const context=e.elements.get('display').context,original=context.fillRect,panels=[];
  context.fillRect=(...args)=>{if(args[2]===240&&args[3]===18)panels.push(context.fillStyle);return original(...args);};
  await e.play();assert.ok(panels.includes('#7c8c62'));assert.equal(e.snapshot().captions.enabled,true);
});
test('Stop immediately clears cue metadata and live accessibility text',async()=>{
  const e=app();await e.play();e.adapter.stopGate=deferred();e.ctx.back();assert.equal(e.snapshot().captions.cueCount,0);assert.equal(captionNode(e).textContent,'');assert.equal(e.run('view'),'details');
  e.adapter.stopGate.resolve(true);await flush();assert.equal(e.snapshot().captions.text,'');
});
test('late Start metadata cannot restore another generation captions after Back',async()=>{
  const e=environment();const gate=deferred();e.adapter.startGate=gate;e.ctx.load(entry);e.ctx.back();
  gate.resolve({source_start:30,range_end:90,fps:8,chunk_frames:16,captions:metadata([cue()])});await flush();assert.equal(e.snapshot().captions.cueCount,0);assert.equal(captionNode(e).textContent,'');
});
test('EOF retains final picture but clears caption metadata and text',async()=>{
  const e=app();e.adapter.complete=true;e.adapter.total=1;e.adapter.end=30.125;await e.play();e.raf(1000);e.raf(1125);
  assert.equal(e.snapshot().state,'ended');assert.equal(e.snapshot().captions.cueCount,0);assert.equal(captionNode(e).textContent,'');
});
test('terminal error clears captions; terminal numeric 2 is not a hidden preference change',async()=>{
  const e=app();await e.play();e.adapter.poll=async()=>{throw Error('gone');};await e.poll();assert.equal(e.snapshot().captions.cueCount,0);
  const pref=e.snapshot().captions.enabled;e.ctx.key('2');assert.equal(e.snapshot().captions.enabled,pref);assert.equal(e.snapshot().state,'error');
});
test('model replacement keeps numeric-2 labels synchronized with page preference',async()=>{
  const e=app();await e.play();e.ctx.key('2');e.setModel('7110');assert.equal(e.keypad['2'].getAttribute('aria-label'),'Enable live captions');assert.equal(e.keypad['2'].getAttribute('aria-pressed'),'false');
  e.click(e.physical.rollUp);assert.equal(e.snapshot().captions.enabled,false);
});
test('hide/return validation holds the cue and does not automatically Resume',async()=>{
  const e=app();await e.play();e.document.hidden=true;await e.fire('visibilitychange');e.document.hidden=false;await e.fire('visibilitychange');
  assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().captions.text,'CAPTION');assert.equal(e.adapter.starts,1);
});
