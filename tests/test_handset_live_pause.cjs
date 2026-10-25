// 5A.4A: deterministic bridge intent/state tests, not real-server acceptance.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
// Reuse the existing lexical-state DOM/adapter harness, without registering its tests.
const original = fs.readFileSync(path.join(__dirname, 'test_handset_live_bridge.cjs'), 'utf8');
const marker = "test('static path and absent capability remain inert'";
assert.equal(original.split(marker).length, 2, 'known bridge harness boundary');
const {environment, entry, deferred, flush} = new Function('require', '__dirname',
  original.split(marker)[0] + '\nreturn {environment, entry, deferred, flush};')(require, __dirname);

function held(e, before) {
  const now=e.snapshot();
  assert.equal(now.position,before.position);
  assert.equal(now.presentedSourceTime,before.presentedSourceTime);
  assert.equal(now.presentedFrameIndex,before.presentedFrameIndex);
}

test('Pause immediately freezes intent, position and presented frame',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(1137);const before=e.snapshot();
  e.ctx.select();assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().playIntent,false);
  e.raf(90000);held(e,before);await e.poll();held(e,before);assert.equal(e.adapter.stops,0);
});
test('key 5 pauses/resumes the same session without Start or Stop',async()=>{
  const e=environment();await e.play();e.ctx.key('5');await flush();assert.equal(e.snapshot().state,'paused');
  e.ctx.key('5');await flush();assert.equal(e.snapshot().state,'playing');assert.equal(e.snapshot().playIntent,true);
  assert.equal(e.adapter.starts,1);assert.equal(e.adapter.stops,0);assert.equal(e.run('view'),'live-player');
});
test('Resume resets wall-clock reference rather than charging paused time',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(1137);e.ctx.select();await flush();e.raf(80000);
  e.ctx.select();await flush();e.raf(90000);assert.ok(Math.abs(e.snapshot().position-.137)<1e-8);
  e.raf(90137);assert.ok(Math.abs(e.snapshot().position-.274)<1e-8);
});
test('Pause keeps one foreground 250ms heartbeat with paused intent',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();await e.poll();
  assert.equal(e.timers.size,1);assert.equal([...e.timers.values()][0].ms,250);
  assert.equal(e.adapter.polls.at(-1).paused,true);assert.equal(e.adapter.polls.at(-1).sourceTime,30);
});
test('Resume sends play intent to the existing adapter',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();e.ctx.select();await flush();
  assert.equal(e.adapter.polls.at(-1).paused,false);assert.equal(e.adapter.starts,1);
});
test('Pause/Resume do not invalidate current stream generation',async()=>{
  const e=environment();await e.play();const g=e.snapshot().generation;e.ctx.select();await flush();
  assert.equal(e.snapshot().generation,g);e.ctx.select();await flush();assert.equal(e.snapshot().generation,g);
});
test('Pause during startup buffering admits first picture but does not auto-play',async()=>{
  const e=environment();e.adapter.end=30;await e.play();e.ctx.select();await flush();
  assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().presentedSourceTime,null);
  e.adapter.end=34;await e.poll();assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().presentedSourceTime,30);
  assert.equal(e.snapshot().warmed,true);e.raf(50000);assert.equal(e.snapshot().position,0);
});
test('first paused picture does not weaken the four-second startup target',async()=>{
  const e=environment();e.adapter.end=30;await e.play();e.ctx.select();await flush();
  e.adapter.end=32;await e.poll();assert.equal(e.snapshot().presentedSourceTime,30);assert.equal(e.snapshot().warmed,false);
  e.ctx.select();await flush();assert.equal(e.snapshot().state,'buffering');assert.equal(e.snapshot().position,0);
  e.adapter.end=34;await e.poll();assert.equal(e.snapshot().state,'playing');
});
test('later prefill cannot change an already presented paused picture',async()=>{
  const e=environment();e.adapter.end=30;await e.play();e.ctx.select();await flush();
  e.adapter.end=30.125;await e.poll();const before=e.snapshot();e.adapter.end=34;await e.poll();held(e,before);
  assert.equal(e.snapshot().state,'paused');
});
test('pending playing poll cannot undo a newer Pause',async()=>{
  const e=environment();await e.play();const gate=deferred();e.adapter.pollGate=gate;const polling=e.poll();
  e.ctx.select();assert.equal(e.snapshot().state,'paused');gate.resolve({state:'running'});await polling;
  assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().playIntent,false);
});
test('pending paused poll cannot undo a newer Resume',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();const gate=deferred();e.adapter.pollGate=gate;
  const polling=e.poll();e.ctx.select();gate.resolve({state:'running'});await polling;
  assert.equal(e.snapshot().playIntent,true);assert.equal(e.snapshot().state,'playing');
});
test('pause request after playback beyond initial chunks keeps current source offset',async()=>{
  const e=environment();e.adapter.end=40;await e.play();e.raf(1000);e.raf(6500);e.ctx.select();await flush();await e.poll();
  assert.equal(e.adapter.polls.at(-1).paused,true);assert.equal(e.adapter.polls.at(-1).sourceTime,35.5);
  assert.equal(e.snapshot().position,5.5);assert.equal(e.adapter.starts,1);
});
test('Pause during rebuffering holds state while new chunks arrive',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(2000);e.adapter.end=31.1;e.raf(3000);
  assert.equal(e.snapshot().state,'buffering');e.ctx.select();const before=e.snapshot();await flush();
  e.adapter.end=35;await e.poll();assert.equal(e.snapshot().state,'paused');held(e,before);
});
test('Resume without enough data buffers rather than advancing or restarting',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(2000);e.adapter.end=31.1;e.raf(3000);
  e.ctx.select();await flush();e.ctx.select();await flush();assert.equal(e.snapshot().state,'buffering');
  e.raf(9000);assert.equal(e.snapshot().position,1);assert.equal(e.adapter.starts,1);
});
test('completed conversion remains paused and resumes retained data without replacement',async()=>{
  const e=environment();e.adapter.complete=true;e.adapter.total=32;e.adapter.end=34;await e.play();
  e.raf(1000);e.raf(2000);e.ctx.select();await flush();e.raf(50000);await e.poll();
  assert.equal(e.snapshot().state,'paused');assert.equal(e.snapshot().position,1);assert.equal(e.adapter.stops,0);
  e.ctx.select();await flush();e.raf(60000);e.raf(63000);assert.equal(e.snapshot().state,'ended');
  assert.equal(e.snapshot().presentedFrameIndex,31);assert.equal(e.adapter.starts,1);assert.equal(e.adapter.stops,1);
});
for(const tail of [1,5])test('paused completed rebuffer tail '+tail+' frame(s) resumes through EOF',async()=>{
  const e=environment();await e.play();e.raf(1000);e.raf(2000);e.adapter.end=31.01;e.raf(3000);
  e.ctx.select();await flush();e.adapter.complete=true;e.adapter.total=8+tail;e.adapter.end=30+(8+tail)/8;
  await e.poll();assert.equal(e.snapshot().state,'paused');e.ctx.select();await flush();
  assert.equal(e.snapshot().state,'playing');e.raf(5000);e.raf(6000);assert.equal(e.snapshot().state,'ended');
  assert.equal(e.snapshot().presentedFrameIndex,7+tail);assert.equal(e.timers.size,0);
});
for(const action of ['back','home'])test(action+' from Paused stops and leaves',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();
  action==='back'?e.ctx.back():e.ctx.key('*');await flush();assert.equal(e.adapter.stops,1);
  assert.equal(e.run('view'),action==='back'?'details':'home');assert.equal(e.timers.size,0);
});
test('repeated Play while paused is guarded; no competing session/timer',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();await e.play();await e.play();
  assert.equal(e.snapshot().state,'paused');assert.equal(e.adapter.starts,1);assert.equal(e.timers.size,1);
});
test('one animation chain survives repeated pause/resume cycles',async()=>{
  const e=environment();await e.play();for(let n=0;n<12;n++){
    e.ctx.select();await flush();e.raf(1000+n*100);assert.equal(e.queue.length,1);assert.equal(e.timers.size,1);
  }assert.equal(e.adapter.starts,1);assert.equal(e.adapter.stops,0);
});
test('action labels match Pause and Resume',async()=>{
  const e=environment();await e.play();assert.equal(e.elements.get('left').attrs['aria-label'],'PAUSE');
  e.ctx.select();assert.equal(e.elements.get('left').attrs['aria-label'],'RESUME');
  assert.equal(e.elements.get('back').attrs['aria-label'],'BACK');await flush();
  e.ctx.select();assert.equal(e.elements.get('left').attrs['aria-label'],'PAUSE');
});
test('numeric unsupported controls and static preferences remain isolated while paused',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();const before=e.snapshot();
  for(const key of ['0','1','3','4','6','7','8','9'])e.ctx.key(key);
  held(e,before);assert.equal(e.calls.writes,0);assert.equal(e.calls.key.length,0);
  e.ctx.key('#');assert.deepEqual(e.calls.key,['#']);assert.equal(e.snapshot().state,'paused');
});
test('static switch from paused awaits confirmed Stop',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();const gate=deferred();e.adapter.stopGate=gate;
  const switching=e.ctx.load({id:'static'});assert.equal(e.calls.load,0);gate.resolve(true);await switching;
  assert.equal(e.calls.load,1);assert.equal(e.run('view'),'player');assert.equal(e.timers.size,0);
});
test('late paused poll after Back cannot repaint or resurrect',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();const gate=deferred();e.adapter.pollGate=gate;
  const polling=e.poll();e.ctx.back();const draws=e.elements.get('display').context.log.length;
  gate.resolve({state:'complete',total_frames:1});await polling;assert.equal(e.run('view'),'details');
  assert.equal(e.elements.get('display').context.log.length,draws);assert.equal(e.timers.size,0);
});
test('paused transport failure is actionable, not silent resume or another Start',async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();e.adapter.error=Object.assign(Error('deadline'),{name:'TimeoutError'});
  await e.poll();assert.equal(e.snapshot().state,'error');assert.match(e.elements.get('summary').textContent,/TIMEOUT/);
  assert.equal(e.adapter.starts,1);assert.equal(e.timers.size,0);e.ctx.back();assert.equal(e.run('view'),'details');
});
for(const event of ['visibilitychange','pagehide'])test('5A.4C pauses on hide and stops on page exit: '+event,async()=>{
  const e=environment();await e.play();e.ctx.select();await flush();e.ctx.document.hidden=true;await e.fire(event);
  if(event==='visibilitychange'){
    assert.equal(e.run('view'),'live-player');assert.equal(e.snapshot().state,'paused');assert.equal(e.adapter.stops,0);assert.equal(e.timers.size,1);
  }else{assert.equal(e.run('view'),'details');assert.equal(e.adapter.stops,1);assert.equal(e.timers.size,0);}
});
test('Start can be cancelled before metadata even with Pause/Resume enabled',async()=>{
  const e=environment();const gate=deferred();e.adapter.startGate=gate;e.ctx.load(entry);
  assert.equal(e.elements.get('left').attrs['aria-label'],'STOP');e.ctx.key('5');
  gate.resolve({source_start:30,range_end:90});await flush();assert.equal(e.run('view'),'details');
  assert.equal(e.snapshot().state,'idle');assert.equal(e.timers.size,0);
});
