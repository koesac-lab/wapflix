// 5A.6B: real bridge/adapter/captions with controlled HTTP and synthetic DOM.
const {test}=require('node:test'),assert=require('node:assert/strict');
const {handset,settle}=require('./helpers/fenced_seek_harness.cjs');
for(const model of ['3210','3310','8210','6310','7110'])test(model+' numeric seeking, physical movement isolation and label restoration',async()=>{
 const e=handset({model});const original={...e.keypad['4'].attrs};e.keypad['6'].setAttribute('aria-disabled','false');
 await e.play();assert.equal(e.snap().state,'playing');assert.equal(e.keypad['4'].getAttribute('aria-disabled'),null);
 assert.equal(e.keypad['6'].getAttribute('aria-label'),'Seek forward 5 seconds');
 assert.equal(e.physical.up.getAttribute('aria-disabled'),'true');e.event('click',e.physical.up);
 if(e.physical.rollUp)e.event('click',e.physical.rollUp);
 if(e.physical.call)assert.equal(e.physical.call.getAttribute('aria-label'),'Pause live playback');
 if(e.physical.press)assert.equal(e.physical.press.getAttribute('aria-label'),'Pause live playback');
 assert.equal(e.http.count('/api/seek'),0);assert.equal(e.snap().captions.enabled,true);
 e.key('6');await settle();assert.equal(e.snap().presentedSourceTime,35);assert.equal(e.snap().state,'playing');
 e.key('4');await settle();assert.equal(e.snap().presentedSourceTime,30);assert.equal(e.http.count('/api/start'),1);
 await e.close();assert.deepEqual(e.keypad['4'].attrs,original);assert.equal(e.keypad['6'].getAttribute('aria-disabled'),'false');
 assert.equal(e.physical.up.getAttribute('aria-label'),'Scroll up');assert.equal(e.physical.up.getAttribute('aria-disabled'),null);
 e.key('4');e.key('6');assert.deepEqual(Array.from(e.context.staticKeys),['4','6']);
});
test('playing seek clears old picture/caption immediately and follows target frame',async()=>{
 const e=handset();await e.play();assert.equal(e.snap().captions.text,'BEFORE');
 e.http.config.holdSeeks=true;e.key('6');await settle();assert.equal(e.snap().state,'seeking');
 assert.equal(e.snap().presentedSourceTime,null);assert.equal(e.snap().captions.text,'');assert.equal(e.timers.size,0);
 e.raf(50000);assert.equal(e.snap().position,0);e.http.release('seeks');await settle();
 assert.equal(e.snap().captions.text,'AFTER');assert.equal(e.snap().captions.sourceTime,e.snap().presentedSourceTime);assert.equal(e.timers.size,1);await e.close();
});
test('paused seek presents target, remains paused, and parks after prefill',async()=>{
 const e=handset();await e.play();e.key('5');await settle();e.key('6');await settle();
 assert.equal(e.snap().state,'paused');assert.equal(e.snap().position,0);assert.equal(e.snap().presentedSourceTime,35);
 e.raf(1000);e.raf(60000);assert.equal(e.snap().presentedSourceTime,35);await e.poll();
 assert.equal(e.http.requests.filter(r=>r.path==='/api/pulse').at(-1).body.paused,true);await e.close();
});
test('rapid seeks accumulate intended target, serialize and skip obsolete intermediate intent',async()=>{
 const e=handset();await e.play();e.http.config.holdSeeks=true;e.key('6');await settle();
 e.key('6');e.key('6');e.key('4');assert.equal(e.snap().seekTarget,40);assert.equal(e.http.pending.seeks.length,1);
 e.http.release('seeks');await settle();assert.equal(e.snap().presentedSourceTime,null);
 assert.equal(e.http.pending.seeks.length,1);assert.deepEqual(e.http.requests.filter(r=>r.path==='/api/seek').map(r=>r.body.position),[35,40]);
 e.http.release('seeks');await settle();assert.equal(e.snap().presentedSourceTime,40);assert.equal(e.snap().state,'playing');await e.close();
});
test('Select during seek changes post-seek intent without another Start or seek',async()=>{
 const e=handset();await e.play();e.http.config.holdSeeks=true;e.key('6');await settle();e.key('5');
 assert.equal(e.snap().playIntent,false);assert.equal(e.snap().state,'seeking');e.http.release('seeks');await settle();
 assert.equal(e.snap().state,'paused');assert.equal(e.http.count('/api/seek'),1);assert.equal(e.http.count('/api/start'),1);await e.close();
});
test('caption preference survives pending seek and replacement',async()=>{
 const e=handset();await e.play();e.key('2');e.http.config.holdSeeks=true;e.key('6');await settle();
 assert.equal(e.snap().captions.enabled,false);e.http.release('seeks');await settle();assert.equal(e.snap().captions.text,'');
 e.key('2');assert.equal(e.snap().captions.text,'AFTER');assert.equal(e.snap().presentedSourceTime,35);await e.close();
});
for(const action of ['back','home','pagehide','static'])test(action+' cancels pending seek with no late picture/caption restoration',async()=>{
 const e=handset();await e.play();e.http.config.holdSeeks=true;e.key('6');await settle();
 if(action==='back')e.back();if(action==='home')e.key('*');if(action==='pagehide')await e.fire('pagehide');
 if(action==='static')e.context.load({id:'static'});await settle();assert.notEqual(e.run('view'),'live-player');
 assert.equal(e.timers.size,0);assert.equal(e.snap().captions.text,'');e.http.release('seeks');await settle();
 assert.equal(e.snap().presentedSourceTime,null);assert.equal(e.http.active,null);assert.equal(e.timers.size,0);
 if(action==='static')assert.equal(e.context.staticLoads.length,1);
});
test('hide during seek cannot resume automatically on replacement or return',async()=>{
 const e=handset();await e.play();e.http.config.holdSeeks=true;e.key('6');await settle();
 e.document.hidden=true;await e.fire('visibilitychange');assert.equal(e.snap().state,'seeking');assert.equal(e.snap().playIntent,false);
 e.http.release('seeks');await settle();assert.equal(e.snap().state,'paused');assert.equal(e.snap().presentedSourceTime,35);
 e.document.hidden=false;await e.fire('visibilitychange');assert.equal(e.snap().state,'paused');
 e.key('5');await settle();assert.equal(e.snap().state,'playing');await e.close();
});
test('seeking while hidden remains paused after target prefill',async()=>{
 const e=handset();await e.play();e.document.hidden=true;await e.fire('visibilitychange');e.key('6');await settle();
 assert.equal(e.snap().state,'paused');assert.equal(e.snap().playIntent,false);assert.equal(e.snap().presentedSourceTime,35);await e.close();
});
test('original-extract progress survives forward and backward replacement streams',async()=>{
 const e=handset();await e.play();e.key('6');await settle();assert.equal(e.snap().position,0);
 assert.equal(e.snap().extractPosition,5);assert.equal(e.snap().extractDuration,60);
 e.key('6');await settle();assert.equal(e.snap().extractPosition,10);e.key('4');await settle();
 assert.equal(e.snap().extractPosition,5);assert.equal(e.snap().extractDuration,60);await e.close();
});
test('seek backward clamps at original beginning',async()=>{
 const e=handset();await e.play();e.key('4');await settle();assert.equal(e.snap().presentedSourceTime,30);await e.close();
});
test('last-frame seek uses EOF tail exception and terminates, not endless buffering',async()=>{
 const e=handset({end:30.125});await e.play();e.key('6');await settle();assert.equal(e.snap().presentedSourceTime,30);
 assert.equal(e.http.requests.find(r=>r.path==='/api/seek').body.position,30);e.raf(1000);e.raf(1125);
 assert.equal(e.snap().state,'ended');assert.equal(e.snap().captions.text,'');await e.close();
});
test('fractional extract endpoint clamps to a renderable target',async()=>{
 const e=handset({start:30.03,end:30.34});await e.play();e.key('6');await settle();
 assert.equal(e.snap().presentedSourceTime,30.28);assert.ok(e.snap().extractPosition>0);await e.close();
});
test('target buffering freezes clock and captions until replacement data is ready',async()=>{
 const e=handset();await e.play();e.http.config.complete=false;e.http.config.ready=0;e.key('6');await settle();
 assert.equal(e.snap().state,'buffering');assert.equal(e.snap().captions.text,'');e.raf(1000);e.raf(99000);assert.equal(e.snap().position,0);
 e.http.config.ready=32;await e.poll();assert.equal(e.snap().state,'playing');assert.equal(e.snap().captions.text,'AFTER');await e.close();
});
test('old delayed pulse cannot overwrite seek result or captions',async()=>{
 const e=handset();await e.play();e.http.config.holdPulses=true;void e.poll();await settle();
 e.http.config.holdPulses=false;e.key('6');await settle();assert.equal(e.snap().presentedSourceTime,35);
 e.http.release('pulses');await settle();assert.equal(e.snap().presentedSourceTime,35);assert.equal(e.snap().captions.text,'AFTER');await e.close();
});
test('latest seek rejection exposes error without retry or abandoned timer',async()=>{
 const e=handset();await e.play();e.http.config.seekError='stale_seek';e.key('6');await settle();
 assert.equal(e.snap().state,'error');assert.equal(e.snap().seeking,false);assert.equal(e.timers.size,0);
 assert.equal(e.snap().captions.text,'');assert.equal(e.http.count('/api/seek'),1);await e.close();
});
test('failure of superseded target is fail-closed rather than hidden retry',async()=>{
 const e=handset();await e.play();e.http.config.holdSeeks=true;e.key('6');await settle();e.key('6');
 e.http.config.seekError='stale_seek';e.http.release('seeks');await settle();assert.equal(e.snap().state,'error');
 assert.equal(e.http.count('/api/seek'),1);assert.equal(e.snap().seeking,false);await e.close();
});
test('physical nav-4, wheel and arrows cannot trigger numeric seek',async()=>{
 const e=handset();await e.play();const start=e.http.count('/api/seek');
 e.event('click',e.element('nav',['.nav [data-key="4"]']));
 e.event('wheel',e.element('roller',['.handset-roller']));e.event('keydown',e.element('body'),{key:'ArrowLeft'});
 assert.equal(e.http.count('/api/seek'),start);assert.equal(e.snap().captions.enabled,true);assert.equal(e.snap().state,'playing');await e.close();
});
test('seek rejected before metadata and in terminal state',async()=>{
 const e=handset();e.http.config.holdStarts=true;e.context.load({id:'local-stream-test',playback_type:'local-stream'});await settle();
 e.key('6');assert.equal(e.http.count('/api/seek'),0);e.http.release('starts');await settle();
 e.http.config.seekError='stale_seek';e.key('6');await settle();e.key('4');assert.equal(e.http.count('/api/seek'),1);await e.close();
});
test('backlight and repeated seeks retain one RAF chain and one active poll timer',async()=>{
 const e=handset();await e.play();for(let n=0;n<5;n++){e.key('6');await settle();e.key('#');e.raf(n*1000);assert.equal(e.timers.size,1);}
 assert.equal(e.http.count('/api/start'),1);assert.equal(e.rafs.length,1);await e.close();
});
