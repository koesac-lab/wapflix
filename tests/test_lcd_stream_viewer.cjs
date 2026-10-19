const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../tools/lcd_stream_viewer.html'),'utf8');
const script=html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
function setup(){
 const elements=new Map(),events={};
 const ctx={fillRect(){}};
 const element=id=>{if(!elements.has(id))elements.set(id,{textContent:'',disabled:false,width:240,height:135,getContext:()=>ctx});return elements.get(id);};
 const c={console,AbortController,setInterval(){},requestAnimationFrame(){},
  document:{hidden:false,getElementById:element,addEventListener(k,f){events[k]=f;}},
  window:{addEventListener(){}},navigator:{sendBeacon(){}},
  fetch:async()=>({ok:true,status:200,json:async()=>({stopped:true})})};
 vm.createContext(c);vm.runInContext(script,c);
 const run=source=>vm.runInContext(source,c);
 run(`session='x';controller=new AbortController();manifest={fps:8,chunk_frames:16,source_start:30,cols:240,rows:135,total_frames:null,state:'running',retained_chunks:2,first_chunk_seconds:.1,worker_running:true};
  const testFrame='80'+'00'.repeat(4049);frames.set(0,{start_frame:0,frames:Array(16).fill(testFrame)});frames.set(1,{start_frame:16,frames:Array(16).fill(testFrame)});warmed=true;intent=true;`);
 return {c,run,element,events};
}
(async()=>{
 const h=setup();h.run('tick(1000);tick(1250);tick(1500);tick(1750);tick(2000)');
 assert.equal(h.run('clock'),1);assert.equal(h.element('state').textContent,'Playing');
 h.run('clock=2;frames.delete(1);last=2000;tick(2250)');
 assert.equal(h.run('clock'),2);assert.equal(h.element('state').textContent,'Buffering');
 h.run('frames.set(1,{start_frame:16,frames:Array(16).fill(testFrame)});tick(2500)');
 assert.equal(h.run('clock'),2.25);assert.equal(h.element('state').textContent,'Playing');
 h.element('pause').onclick();h.run('tick(2750)');assert.equal(h.run('clock'),2.25);
 h.c.document.hidden=true;h.events.visibilitychange();assert.equal(h.run('intent'),false);
 const short=setup();short.run(`clock=0;last=null;manifest.state='complete';manifest.total_frames=8;frames.clear();frames.set(0,{start_frame:0,frames:Array(8).fill(testFrame)});tick(1000);tick(1250);tick(1500);tick(1750);tick(2000)`);
 assert.equal(short.run('clock'),1);assert.equal(short.element('state').textContent,'Finished');
 const stale=setup();let resolvePulse;
 stale.c.fetch=(url)=>url==='/api/pulse'?new Promise(resolve=>{resolvePulse=()=>resolve({ok:true,status:200,json:async()=>({state:'running'})});}):Promise.resolve({ok:true,status:200,json:async()=>({stopped:true})});
 const pending=stale.run('poll()');await stale.run('stop()');resolvePulse();await pending;
 assert.equal(stale.run('session'),null);assert.equal(stale.run('frames.size'),0);assert.equal(stale.run('manifest'),null);
 console.log('Viewer state checks passed: playback clock, buffering freeze/recovery, pause, hidden tab, partial final chunk, stale response after Stop.');
})().catch(error=>{console.error(error);process.exitCode=1;});
