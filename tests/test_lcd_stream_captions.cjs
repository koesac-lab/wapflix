const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const root=path.resolve(__dirname,'..');
const html=cp.execFileSync(process.env.PYTHON||'python3',['-c',
 "from pathlib import Path; from tools.lcd_stream_captions import caption_html; print(caption_html(Path('tools/lcd_stream_viewer.html').read_text()))"],{cwd:root,encoding:'utf8'});
const script=html.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const hostile='<img src=x onerror="window.captionExecuted=true">';
const standardCues=[{start:30,end:31,text:'First'},{start:31,end:32,text:'Second'},{start:32,end:34,text:hostile+'\nTwo lines'}];
function setup(cues=standardCues,trackFound=true){
 const elements=new Map(),events={};let count=0,currentId='';
 const element=id=>{
  if(!elements.has(id)){
   const e={textContent:'',disabled:false,width:240,height:135,attrs:{},setAttribute(k,v){this.attrs[k]=v;},getContext(){return {fillRect(){}};}};
   Object.defineProperty(e,'innerHTML',{set(){throw Error('Unsafe HTML write');}});elements.set(id,e);
  }
  return elements.get(id);
 };
 const meta=()=>({id:currentId,state:'running',error:null,cols:240,rows:135,fps:8,chunk_frames:16,source_start:30,
  generated_chunks:2,ready_frames:32,total_frames:null,retained_chunks:2,first_chunk_seconds:.05,worker_running:true});
 const response=data=>({ok:true,status:200,json:async()=>data});
 const c={console,AbortController,setInterval(){},requestAnimationFrame(){},
  document:{hidden:false,getElementById:element,addEventListener(k,f){events[k]=f;}},window:{addEventListener(){}},navigator:{sendBeacon(){}},
  fetch:async(url)=>{
   if(url==='/api/start'){
    currentId='s'+(++count);
    return response({...meta(),captions:{timebase:'source',cues,selected_cue_count:cues.length,parse_error_count:0,track_found:trackFound}});
   }
   if(url==='/api/pulse')return response(meta());
   if(url.startsWith('/api/chunk')){const n=Number(new URL(url,'http://test').searchParams.get('n'));return response({start_frame:n*16,frames:Array(16).fill('80'+'00'.repeat(4049))});}
   return response({stopped:true});
  }};
 vm.createContext(c);vm.runInContext(script,c);
 return {c,element,events,response,meta,run:source=>vm.runInContext(source,c),async start(){await element('start').onclick();await settle();await settle();}};
}
(async()=>{
 const h=setup();await h.start();h.run('tick(1000)');assert.equal(h.element('captionText').textContent,'First');
 h.run('tick(1250);tick(1500);tick(1750);tick(2000)');assert.equal(h.run('clock'),1);assert.equal(h.element('captionText').textContent,'Second');
 h.run('clock=1.875;draw();frames.delete(1);last=3000;tick(3250)');
 assert.equal(h.run('clock'),2);assert.equal(h.run('painted'),15);assert.equal(h.element('state').textContent,'Buffering');
 assert.equal(h.element('captionText').textContent,'Second');h.run('tick(3500)');assert.equal(h.element('captionText').textContent,'Second');
 h.run("frames.set(1,{start_frame:16,frames:Array(16).fill('80'+'00'.repeat(4049))});tick(3750)");
 assert.equal(h.element('captionText').textContent,hostile+'\nTwo lines');assert.equal(h.c.window.captionExecuted,undefined);
 const clock=h.run('clock');h.element('captions').onclick();assert.equal(h.element('captionText').textContent,'');assert.equal(h.run('clock'),clock);
 h.element('captions').onclick();assert.equal(h.element('captionText').textContent,hostile+'\nTwo lines');
 h.element('pause').onclick();h.run('tick(4000);tick(4500)');assert.equal(h.run('clock'),clock);assert.equal(h.element('captionText').textContent,hostile+'\nTwo lines');
 h.c.document.hidden=true;h.events.visibilitychange();h.run('tick(9000)');assert.equal(h.run('clock'),clock);
 await h.run('stop()');assert.equal(h.element('captionText').textContent,'');assert.equal(h.element('captions').disabled,true);
 h.c.document.hidden=false;await h.start();h.run('tick(10000)');assert.equal(h.run('clock'),0);assert.equal(h.element('captionText').textContent,'First');
 h.run('manifest.state="complete";manifest.total_frames=1;clock=.125;intent=true;last=10000;tick(10250)');
 assert.equal(h.element('state').textContent,'Finished');assert.equal(h.element('captionText').textContent,'');
 const absent=setup([],false);await absent.start();absent.run('tick(1000)');assert.equal(absent.element('captions').disabled,true);assert.match(absent.element('captionInfo').textContent,/No adjacent SRT/);
 const stale=setup();let deliver;
 stale.c.fetch=url=>url==='/api/start'?new Promise(resolve=>{deliver=()=>resolve(stale.response({...stale.meta(),id:'old',captions:{timebase:'source',cues:standardCues,selected_cue_count:3,parse_error_count:0,track_found:true}}));}):Promise.resolve(stale.response({stopped:true}));
 const starting=stale.element('start').onclick();await settle();await stale.run('stop()');deliver();await starting;
 assert.equal(stale.run('captionCues.length'),0);assert.equal(stale.run('captionSession'),null);assert.equal(stale.element('captionText').textContent,'');
 console.log('M3 caption state checks passed: source offset, held-frame buffering, pause, visibility, toggle, literal text, Stop/restart, end-of-clip, absent SRT and stale start response.');
})().catch(error=>{console.error(error);process.exitCode=1;});
