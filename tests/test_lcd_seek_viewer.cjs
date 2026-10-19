const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const root=path.resolve(__dirname,'..');
let source=fs.readFileSync(path.join(root,'tools/lcd_stream_viewer.html'),'utf8');
source=source.replace('<canvas id="screen"','<button id="captions"></button><canvas id="screen"').replace('</canvas>','</canvas><div id="captionText"></div><p id="captionInfo"></p>');
source=source.replace('</script>',fs.readFileSync(path.join(root,'tools/lcd_caption_overlay.js'),'utf8')+'\n</script>');
const html=cp.execFileSync(process.env.PYTHON||'python3',['-c',"import sys; from tools.lcd_stream_seek_viewer import seek_html; print(seek_html(sys.stdin.read()))"],{cwd:root,input:source,encoding:'utf8'});
const script=html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function setup(){
 const els=new Map(),events={},winEvents={},requests=[],beacons=[],states=new Map(),pending=[],pendingStops=[];
 let starts=0,currentId='';const config={deferSeek:false,deferStop:false};
 const element=id=>{
  if(!els.has(id)){
   const e={textContent:'',value:'',disabled:false,width:240,height:135,attrs:{},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,f){this[k]=f;},getContext(){return {fillRect(){}};}};
   Object.defineProperty(e,'innerHTML',{set(){throw Error('Unsafe HTML write');}});els.set(id,e);
  }return els.get(id);
 };
 function metadata(id,position,nav,revision){
  const remaining=Math.ceil((90-position)*8),count=Math.min(32,remaining);
  const data={id,source_start:position,state:remaining<=32?'complete':'running',error:null,cols:240,rows:135,fps:8,chunk_frames:16,
   total_frames:remaining<=32?remaining:null,generated_chunks:Math.ceil(count/16),ready_frames:count,retained_chunks:Math.ceil(count/16),first_chunk_seconds:.05,worker_running:remaining>32,
   navigation_id:nav,revision,range_start:30,range_end:90,seek_position:position,
   captions:{timebase:'source',cues:[{start:position,end:90,text:'Caption '+position}],selected_cue_count:1,parse_error_count:0,track_found:true}};
  states.set(id,data);currentId=id;return data;
 }
 const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
 const c={console,AbortController,setInterval(){},requestAnimationFrame(){},
  document:{hidden:false,activeElement:null,getElementById:element,addEventListener(k,f){events[k]=f;}},
  window:{addEventListener(k,f){(winEvents[k]||=[]).push(f);}},navigator:{sendBeacon(url,body){beacons.push({url,body:JSON.parse(body)});}},
  fetch:async(url,options={})=>{
   const body=options.body?JSON.parse(options.body):null;requests.push({url,body});
   if(url==='/api/start'){const nav='n'+(++starts);return response(metadata('start'+starts,30,nav,0));}
   if(url==='/api/pulse'){
    const data={...states.get(body.id)};delete data.captions;return response(data);
   }
   if(url.startsWith('/api/chunk')){
    const query=new URL(url,'http://test').searchParams,n=Number(query.get('n')),data=states.get(query.get('id'));
    return response({start_frame:n*16,frames:Array(Math.max(0,Math.min(16,data.ready_frames-n*16))).fill('80'+'00'.repeat(4049))});
   }
   if(url==='/api/seek'){
    const deliver=(status=200)=>status===200?response(metadata('seek'+body.revision,30+Math.floor((body.position-30)*8)/8,body.navigation_id,body.revision)):response({error:'Seek rejected'},status);
    if(config.deferSeek)return new Promise(resolve=>pending.push({body,resolve:(status=200)=>resolve(deliver(status))}));
    return deliver();
   }
   if(url==='/api/navigation/stop'&&config.deferStop)return new Promise(resolve=>pendingStops.push(status=>resolve(response(status===200?{stopped:true}:{error:'Stop rejected'},status))));
   return response({stopped:true});
  }};
 vm.createContext(c);vm.runInContext(script,c);
 return {c,element,events,winEvents,requests,beacons,config,pending,pendingStops,run:s=>vm.runInContext(s,c),async start(){await element('start').onclick();await settle();await settle();}};
}
(async()=>{
 const h=setup();await h.start();h.run('tick(1000)');assert.equal(h.element('seekForward').disabled,false);
 await h.element('seekForward').onclick();await settle();h.run('tick(1500)');
 assert.equal(h.run('manifest.source_start'),40);assert.equal(h.element('captionText').textContent,'Caption 40');assert.equal(h.run('intent'),true);
 h.element('pause').onclick();h.element('captions').onclick();await h.run('seekTo(55)');await settle();h.run('tick(2000)');
 assert.equal(h.run('manifest.source_start'),55);assert.equal(h.run('intent'),false);assert.equal(h.run('clock'),0);assert.equal(h.run('captionsOn'),false);
 assert.equal(h.element('captionText').textContent,'');assert.equal(h.element('pause').textContent,'Resume');
 const pulses=h.requests.filter(r=>r.url==='/api/pulse');assert.equal(pulses.at(-1).body.paused,false);
 await h.run('poll()');assert.equal(h.requests.filter(r=>r.url==='/api/pulse').at(-1).body.paused,true);
 h.element('captions').onclick();h.run('draw()');assert.equal(h.element('captionText').textContent,'Caption 55');
 const before=h.requests.length;await h.run("seekTo('')");assert.equal(h.requests.length,before);
 await h.run('seekTo(999)');await settle();assert.equal(h.run('manifest.source_start'),89.875);
 const rapid=setup();await rapid.start();rapid.config.deferSeek=true;
 const a=rapid.run('seekTo(40)'),b=rapid.run('seekTo(50)');
 assert.equal(rapid.pending.length,2);rapid.pending[1].resolve();await b;await settle();rapid.run('tick(1000)');
 rapid.pending[0].resolve(409);await a;
 assert.equal(rapid.run('manifest.source_start'),50);assert.equal(rapid.run('intent'),true);assert.equal(rapid.element('captionText').textContent,'Caption 50');
 const stop=setup();await stop.start();stop.config.deferSeek=true;
 const late=stop.run('seekTo(60)');await stop.run('stop()');stop.pending[0].resolve();await late;
 assert.equal(stop.run('session'),null);assert.equal(stop.run('manifest'),null);assert.equal(stop.run('navigationId'),null);assert.equal(stop.element('captionText').textContent,'');
 assert(stop.requests.some(r=>r.url==='/api/navigation/stop'&&r.body.navigation_id==='n1'));
 const hidden=setup();await hidden.start();hidden.config.deferSeek=true;const pending=hidden.run('seekTo(45)');
 hidden.c.document.hidden=true;hidden.events.visibilitychange();hidden.pending[0].resolve();await pending;assert.equal(hidden.run('intent'),false);
 const failure=setup();await failure.start();failure.config.deferSeek=true;
 const bad=failure.run('seekTo(45)');failure.pending[0].resolve(409);await bad;assert.match(failure.element('state').textContent,/Error:/);assert.equal(failure.run('navigationId'),null);
 const restore=setup();await restore.start();restore.config.deferStop=true;
 const oldStop=restore.run('stop()');await restore.start();restore.pendingStops[0](503);await oldStop;
 assert.equal(restore.run('navigationId'),'n2');assert(!restore.element('state').textContent.startsWith('Stop failed'));
 const unload=setup();await unload.start();for(const fn of unload.winEvents.pagehide)fn();
 assert(unload.beacons.some(b=>b.url==='/api/navigation/stop'&&b.body.navigation_id==='n1'));
 const focus=setup();await focus.start();focus.c.document.activeElement=focus.element('seekPosition');focus.element('seekPosition').value='42';focus.run('tick(1000)');assert.equal(focus.element('seekPosition').value,'42');
 console.log('M4B state checks passed: forward seek, paused target preview, caption preference, warmup pulses, clamp/invalid input, rapid stale rejection, Stop cancellation, hidden-tab seek, failures, stale Stop, unload and input focus.');
})().catch(error=>{console.error(error);process.exitCode=1;});
