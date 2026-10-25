// Pure cue-selection tests. No browser, streaming session or caption renderer.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {prepare,selectAt,selectFrame}=require('../live-captions.js');
const data=(cues,extra={})=>({timebase:'source',cues,track_found:true,selected_cue_count:cues.length,parse_error_count:0,...extra});
const cue=(start=30,end=31,text='Caption')=>({start,end,text});
const at=(track,time)=>selectAt(track,time).text;

test('existing M3/M4 metadata shape is accepted',()=>{
  const t=prepare(data([cue()]));assert.equal(t.status,'ready');assert.equal(t.timebase,'source');assert.equal(t.cues.length,1);assert.deepEqual(t.warnings,[]);
});
test('absolute source offset is not subtracted or double-added',()=>{
  const t=prepare(data([cue(30,32,'SOURCE 30')]));assert.equal(at(t,0),'');assert.equal(at(t,30),'SOURCE 30');assert.equal(at(t,60),'');
});
test('source_start and smooth-position fields are ignored in favour of frame sourceTime',()=>{
  const t=prepare(data([cue(30,31,'RIGHT'),cue(60,61,'WRONG')]));
  assert.equal(selectFrame(t,{sourceTime:30.125,source_start:30,position:30.125,elapsed:60,requestedSourceTime:60}).text,'RIGHT');
});
test('cue start is inclusive and end is exclusive',()=>{
  const t=prepare(data([cue(30,31,'A')]));assert.equal(at(t,29.999),'');assert.equal(at(t,30),'A');assert.equal(at(t,30.999),'A');assert.equal(at(t,31),'');
});
test('adjacent cue boundary selects only the next cue',()=>{
  const t=prepare(data([cue(30,31,'A'),cue(31,32,'B')]));assert.equal(at(t,31),'B');
});
test('fractional source times retain exact boundary semantics',()=>{
  const t=prepare(data([cue(30.125,30.375,'F')]));assert.equal(at(t,30.124999),'');assert.equal(at(t,30.125),'F');assert.equal(at(t,30.375),'');
});
test('no epsilon or hidden FPS quantisation shifts the supplied timestamp',()=>{
  const t=prepare(data([cue(30.13,30.14,'NARROW')]));assert.equal(at(t,30.135),'NARROW');assert.equal(at(t,30.125),'');
});
test('actual presented frame time wins over the ahead-of-picture smooth clock',()=>{
  const t=prepare(data([cue(30,30.13,'FIRST'),cue(30.13,31,'SECOND')]));
  assert.equal(selectFrame(t,{sourceTime:30.125,requestedTime:30.137}).text,'FIRST');assert.equal(at(t,30.137),'SECOND');
});
test('overlapping cues preserve incoming order even if not sorted by time',()=>{
  const t=prepare(data([cue(31,34,'SECOND IN TIME'),cue(30,33,'FIRST IN TIME')]));
  const s=selectAt(t,32);assert.deepEqual(s.activeCueIndices,[0,1]);assert.deepEqual(s.lines,['SECOND IN TIME','FIRST IN TIME']);
});
test('overlap deduplication retains first occurrence and relative line order',()=>{
  const t=prepare(data([cue(30,33,'A\nB'),cue(31,34,'B\nC\nA')]));
  assert.deepEqual(selectAt(t,32).lines,['A','B','C']);assert.deepEqual(selectAt(t,32).activeCueIndices,[0,1]);
});
test('repeated lines inside one cue are suppressed without changing case',()=>{
  const t=prepare(data([cue(30,31,'A\nA\na')]));assert.deepEqual(selectAt(t,30).lines,['A','a']);
});
test('CRLF/CR become lines; edge whitespace and blank lines are removed',()=>{
  const t=prepare(data([cue(30,31,'  A \r\n\r\n B\r C  ')]));assert.deepEqual(selectAt(t,30).lines,['A','B','C']);
});
test('internal spacing, punctuation and Unicode remain plain text',()=>{
  const text='Café  déjà vu — αβ!';const t=prepare(data([cue(30,31,text)]));assert.equal(at(t,30),text);
});
test('markup and script-looking text are never interpreted as HTML',()=>{
  const text='<img src=x onerror=alert(1)>\n<script>bad()</script>';
  const t=prepare(data([cue(30,31,text)]));assert.equal(at(t,30),text);
});
test('missing metadata is distinct from a present empty cue window',()=>{
  assert.equal(prepare(null).status,'missing');assert.equal(prepare(undefined).status,'missing');
  const t=prepare(data([]));assert.equal(t.status,'ready');assert.equal(at(t,30),'');assert.deepEqual(t.warnings,[]);
});
test('track_found=false is missing, not a playback failure',()=>{
  const t=prepare(data([],{track_found:false}));assert.equal(t.status,'missing');assert.equal(at(t,30),'');
});
test('contradictory missing-track cues are ignored with a warning',()=>{
  const t=prepare(data([cue()],{track_found:false}));assert.equal(t.status,'missing');assert.equal(t.cues.length,0);assert.equal(t.warnings[0].code,'cues_without_track');
});
test('no active cue is not a missing track',()=>{
  const t=prepare(data([cue()]));const s=selectAt(t,40);assert.equal(s.status,'ready');assert.equal(s.text,'');
});
test('server malformed-cue count stays visible independently of valid selection',()=>{
  const t=prepare(data([cue()],{parse_error_count:3}));assert.equal(t.parseErrorCount,3);
  assert.deepEqual(t.warnings,[{code:'server_parse_warnings',index:null,count:3}]);assert.equal(at(t,30),'Caption');
});
test('local malformed cues are skipped, not allowed to hide valid neighbours',()=>{
  const t=prepare(data([cue(),{start:31,end:30,text:'bad'},cue(30,32,'VALID')]));
  assert.equal(at(t,30),'Caption\nVALID');assert.deepEqual(selectAt(t,30).activeCueIndices,[0,2]);assert.equal(t.warnings[0].index,1);
});
for(const bad of [null,{},cue(-1,1),cue(NaN,31),cue(30,Infinity),cue(31,31),cue(32,31),cue('30',31),cue(30,31,42)]){
  test('rejects malformed cue '+JSON.stringify(bad),()=>{
    const t=prepare(data([bad]));assert.equal(t.cues.length,0);assert.equal(t.warnings[0].code,'invalid_cue');assert.equal(at(t,30),'');
  });
}
test('empty caption text is warned and omitted',()=>{
  const t=prepare(data([cue(30,31,' \r\n ')]));assert.equal(t.cues.length,0);assert.equal(t.warnings[0].code,'empty_cue');
});
test('sparse cue arrays report the missing slot instead of silently changing indices',()=>{
  const cues=[];cues.length=2;cues[1]=cue();const t=prepare(data(cues));assert.equal(t.warnings[0].index,0);assert.deepEqual(selectAt(t,30).activeCueIndices,[1]);
});
test('clip-relative metadata is invalid rather than guessed to be source-time',()=>{
  const t=prepare(data([cue()],{timebase:'clip'}));assert.equal(t.status,'invalid');assert.equal(at(t,30),'');assert.equal(t.warnings[0].code,'unsupported_timebase');
});
test('malformed metadata is a distinct non-throwing invalid track',()=>{
  for(const metadata of [[],42,'bad',{}, {timebase:'source',track_found:true,cues:null}]){
    const t=prepare(metadata);assert.equal(t.status,'invalid');assert.equal(at(t,30),'');
  }
});
test('selected count mismatch warns but does not suppress valid text',()=>{
  const t=prepare(data([cue()],{selected_cue_count:2}));assert.equal(t.warnings[0].code,'selected_count_mismatch');assert.equal(at(t,30),'Caption');
});
test('invalid server warning count is not treated as a valid count',()=>{
  const t=prepare(data([],{parse_error_count:-1}));assert.equal(t.parseErrorCount,0);assert.equal(t.warnings[0].code,'invalid_parse_error_count');
});
test('no presented frame yields no caption even if a cue exists',()=>{
  const t=prepare(data([cue()]));assert.equal(selectFrame(t,null).sourceTime,null);assert.equal(selectFrame(t,undefined).text,'');
});
test('held frame deterministically holds captions during Pause or rebuffering',()=>{
  const t=prepare(data([cue(30,31,'HOLD'),cue(31,32,'NEXT')]));const frame={sourceTime:30.875};
  const first=selectFrame(t,frame);for(let n=0;n<100;n++)assert.deepEqual(selectFrame(t,frame),first);
});
test('replacing the prepared track cannot leak an old cue into new selection',()=>{
  const old=prepare(data([cue(30,31,'OLD')])),next=prepare(data([]));assert.equal(at(old,30),'OLD');assert.equal(at(next,30),'');
});
test('preparation snapshots input without mutating caller data',()=>{
  const raw=data([cue(30,31,'A')]);const before=JSON.stringify(raw),t=prepare(raw);assert.equal(JSON.stringify(raw),before);
  raw.cues[0].text='CHANGED';raw.cues.push(cue());assert.equal(at(t,30),'A');assert.equal(t.cues.length,1);
});
test('prepared and selected outputs are deeply frozen where they own collections',()=>{
  const t=prepare(data([cue()])),s=selectAt(t,30);
  for(const object of [t,t.cues,t.cues[0],t.cues[0].lines,t.warnings,s,s.lines,s.activeCueIndices])assert.ok(Object.isFrozen(object));
});
for(const invalid of [NaN,Infinity,-1,'30',null,undefined])test('invalid explicit source time '+String(invalid)+' is rejected',()=>{
  assert.throws(()=>selectAt(prepare(data([])),invalid),RangeError);
});
test('raw metadata cannot accidentally be used as a prepared track',()=>{
  assert.throws(()=>selectAt(data([cue()]),30),TypeError);assert.throws(()=>selectFrame(null,null),TypeError);
});
test('invalid frame shape is a caller error, not an offset fallback',()=>{
  const t=prepare(data([]));assert.throws(()=>selectFrame(t,30),TypeError);assert.throws(()=>selectFrame(t,{elapsed:30}),RangeError);
});
test('zero-time and one-frame-width cues use the same interval rules',()=>{
  const t=prepare(data([cue(0,.125,'ZERO')]));assert.equal(at(t,0),'ZERO');assert.equal(at(t,.125),'');
});
test('module has a browser global export without DOM, network, clocks or timers',()=>{
  const source=fs.readFileSync(path.join(__dirname,'..','live-captions.js'),'utf8');
  const fail=()=>{throw Error('unexpected side effect');};
  const env={fetch:fail,setTimeout:fail,setInterval:fail,requestAnimationFrame:fail};
  Object.defineProperty(env,'document',{get:fail});Object.defineProperty(env,'localStorage',{get:fail});
  vm.runInNewContext(source,env);assert.equal(typeof env.WapflixLiveCaptions.selectFrame,'function');assert.ok(Object.isFrozen(env.WapflixLiveCaptions));
});
