(() => {
'use strict';
const playerRender=render, playerSelect=select, playerBack=back, playerKey=key, playerLoad=load, playerTick=tick;
const STORE='wapflix-state-v1';
let saved={progress:{},list:[],autoplayNext:true};
try {
  const raw=JSON.parse(localStorage.getItem(STORE)||'null');
  if(raw&&typeof raw==='object') {
    saved.autoplayNext=raw.autoplayNext!==false;
    saved.list=Array.isArray(raw.list)?[...new Set(raw.list.filter(x=>typeof x==='string'))]:[];
    for(const [id,p] of Object.entries(raw.progress||{}))
      if(p&&Number.isFinite(p.elapsed)&&Number.isFinite(p.duration)&&p.duration>0)
        saved.progress[id]={elapsed:Math.max(0,Math.min(p.elapsed,p.duration)),duration:p.duration,at:Number(p.at)||0,complete:p.complete===true||p.elapsed>=p.duration-2};
  }
} catch {}
let page={name:'home',selected:0},history=[],ending=null,serial=0,lastSave=0,intent={};
const entries=()=>groups.flatMap(g=>g.items);
const byId=id=>entries().find(e=>e.id===id);
const total=()=>clip?clip.frames.length/clip.fps:0;
const short=e=>e.episode_title||e.title;
function persist(){try{localStorage.setItem(STORE,JSON.stringify(saved));}catch{}}
function remember(){
  if(!item||!clip||message) return;
  const length=total();
  if(elapsed>3||saved.progress[item.id]) {
    saved.progress[item.id]={elapsed:Math.min(elapsed,length),duration:length,at:Date.now(),complete:elapsed>=length-2};
    persist();
  }
}
function resumeList(){return Object.entries(saved.progress).map(([id,p])=>({entry:byId(id),...p})).filter(p=>p.entry&&!p.complete&&p.elapsed>3).sort((a,b)=>b.at-a.at);}
function say(){
  const rows=actions();
  announce(rows.length?rows[Math.min(page.selected,rows.length-1)].label:'No items. Back returns to the previous screen.');
}
function snapshot(){const r=actions()[page.selected];return {...page,focus:r?.entry?.id||r?.label};}
function enter(name,extra={}){
  history.push(snapshot());page={name,selected:0,...extra};view=name;render();say();
}
function leavePlayer(){remember();++serial;++token;setPlaying(false);clip=null;message='';detail=false;ending=null;}
function home(){leavePlayer();history=[];page={name:'home',selected:0};view='home';render();say();}
function openDetails(entry){enter('details',{id:entry.id});}
function episodeRows(){return groups[page.gi]?.items||[];}
function locate(entry){
  const gi=groups.findIndex(g=>g.items.some(e=>e.id===entry.id));
  if(gi<0) return false;
  group=gi;index=groups[gi].items.findIndex(e=>e.id===entry.id);return true;
}
function begin(entry,resume=false){load(entry,false,{resume,autoplay:true});}
function actions(){
  if(page.name==='home'){
    const rows=resumeList().slice(0,3).map(p=>({label:'RESUME '+short(p.entry),suffix:Math.floor(p.elapsed/p.duration*100)+'%',run:()=>begin(p.entry,true)}));
    if(groups.some(g=>g.items.some(e=>e.series))) rows.push({label:'SERIES',run:()=>enter('serieslist')});
    const gi=groups.findIndex(g=>!g.items.some(e=>e.series));
    if(gi>=0) rows.push({label:'ORIGINAL TRANSMISSIONS',run:()=>enter('episodes',{gi})});
    rows.push({label:'MY LIST',run:()=>enter('mylist')},{label:'OPTIONS',run:()=>enter('options')});return rows;
  }
  if(page.name==='serieslist') return groups.map((g,gi)=>({g,gi})).filter(x=>x.g.items.some(e=>e.series)).map(x=>({label:x.g.name,run:()=>enter('series',{gi:x.gi})}));
  if(page.name==='series'){
    const groupItems=groups[page.gi]?.items||[];
    if(!groupItems.length)return [];
    const progress=resumeList().find(p=>groupItems.some(e=>e.id===p.entry.id));
    return [{label:progress?'RESUME':'PLAY',run:()=>begin(progress?progress.entry:groupItems[0],!!progress)},
      {label:'EPISODES',run:()=>enter('episodes',{gi:page.gi})}];
  }
  if(page.name==='episodes'||page.name==='mylist'){
    const list=page.name==='episodes'?episodeRows():saved.list.map(byId).filter(Boolean);
    return list.map(entry=>{
      const progress=saved.progress[entry.id];
      return {entry,label:(entry.episode?'E'+String(entry.episode).padStart(2,'0')+' ':'')+short(entry),
        suffix:progress?(progress.complete?'SEEN':Math.floor(progress.elapsed/progress.duration*100)+'%'):'',run:()=>openDetails(entry)};
    });
  }
  if(page.name==='details'){
    const entry=byId(page.id);if(!entry)return [];
    const progress=saved.progress[entry.id],resume=!!(progress&&!progress.complete&&progress.elapsed>3);
    return [{label:resume?'RESUME':'PLAY',run:()=>begin(entry,resume)},
      {label:saved.list.includes(entry.id)?'REMOVE FROM MY LIST':'ADD TO MY LIST',run:()=>{
        saved.list=saved.list.includes(entry.id)?saved.list.filter(id=>id!==entry.id):[entry.id,...saved.list];persist();render();say();
      }}];
  }
  if(page.name==='options') return [
    {label:'AUTOPLAY NEXT: '+(saved.autoplayNext?'ON':'OFF'),run:()=>{saved.autoplayNext=!saved.autoplayNext;persist();render();say();}},
    {label:'HANDSET: '+(window.wapflixHandset?.current()||'DEFAULT'),run:()=>{window.wapflixHandset?.cycle();render();say();}},
    {label:'CONNECTION: '+labels[quality],run:()=>{quality=(quality+1)%3;render();say();}},
    {label:'BACKLIGHT: '+(lit?'ON':'OFF'),run:()=>playerKey('#')},
    {label:'ABOUT WAPFLIX',run:()=>enter('about')}];
  return [];
}
function title(){
  if(page.name==='episodes'||page.name==='series')return groups[page.gi]?.name||'EPISODES';
  if(page.name==='details')return short(byId(page.id)||{title:'NOT FOUND'});
  return {home:'HOME',serieslist:'SERIES',mylist:'MY LIST',options:'OPTIONS',about:'ABOUT WAPFLIX'}[page.name]||'HOME';
}
function drawLine(value,y,selected=false,suffix=''){
  const room=37-(suffix?suffix.length+2:0),line=(selected?'> ':'  ')+String(value).slice(0,room);
  if(selected){ctx.fillStyle=ink;ctx.fillRect(0,y-4,240,17);ctx.save();ctx.globalCompositeOperation='destination-out';}
  text(line,3,y);if(suffix)text(suffix,237-suffix.length*6,y);
  if(selected)ctx.restore();
}
function renderPage(){
  header();center(title().slice(0,38),26);
  if(page.name==='about'){
    ['A GREEN SCREEN. LARGE FEELINGS.','','ASCII DEMOS, NOT TV FOOTAGE.','MODEM LABELS ARE FICTIONAL.','','UP/DOWN BROWSE. OK SELECTS.','BACK RETURNS ONE SCREEN.','* RETURNS HOME. 3 SHARES.'].forEach((s,n)=>text(s,4,48+n*15));
    footer('BACK','BACK');return;
  }
  const rows=actions();
  if(page.focus){const at=rows.findIndex(r=>(r.entry?.id||r.label)===page.focus);if(at>=0)page.selected=at;delete page.focus;}
  page.selected=Math.max(0,Math.min(page.selected,rows.length-1));
  let y=48,capacity=6;
  if(page.name==='series'||page.name==='details'){
    const entry=page.name==='details'?byId(page.id):groups[page.gi]?.items[0];
    const description=page.name==='series'?'Choose Play or browse the episodes.':entry?.description||'';
    wrap(description,38).slice(0,5).forEach((s,n)=>text(s,4,44+n*11));
    y=125;capacity=3;
  }
  if(!rows.length){center('NOTHING HERE YET',88);center('BACK TO CONTINUE',103);footer('BACK','BACK');return;}
  const start=Math.floor(page.selected/capacity)*capacity;
  rows.slice(start,start+capacity).forEach((r,n)=>drawLine(r.label,y+n*20,start+n===page.selected,r.suffix||''));
  text((page.selected+1)+'/'+rows.length,4,193);
  if(rows.length>capacity)text('2 UP / 8 DOWN',151,193);
  let left='OPEN';
  if(page.name==='details'||page.name==='series')left=rows[page.selected].label.startsWith('REMOVE')?'REMOVE':rows[page.selected].label.startsWith('ADD')?'ADD':rows[page.selected].label;
  if(page.name==='options')left=page.selected===4?'OPEN':'CHANGE';
  footer(left,page.name==='home'?'OPTIONS':'BACK');
  if(page.name==='episodes'){group=page.gi;index=page.selected;}
  if(page.name==='details')item=byId(page.id)||item;
}
function renderEnd(){
  header();center('TRANSMISSION ENDED',43);
  if(ending?.next){center('NEXT UP',70);wrap(short(ending.next),36).slice(0,3).forEach((s,n)=>center(s,89+n*11));
    center(saved.autoplayNext?'STARTING IN '+Math.ceil(ending.remaining/1000)+'...':'READY WHEN YOU ARE',139);footer('PLAY NEXT','EPISODES');
  }else{center('END OF THIS COLLECTION',95);footer('REPLAY','EPISODES');}
}
render=function(){if(view==='player')playerRender();else if(view==='ended')renderEnd();else renderPage();};
function move(delta){
  if(view==='player'||view==='ended')return;
  const rows=actions();if(!rows.length)return;
  page.selected=Math.max(0,Math.min(rows.length-1,page.selected+delta));render();say();
}
select=function(){
  if(view==='player'){
    if(!clip){if(item&&message&&!message.startsWith('RECEIVING'))load(item,false,intent);return;}
    playerSelect();remember();return;
  }
  if(view==='ended') {const next=ending?.next;ending=null;begin(next||item);return;}
  const rows=actions();if(!rows.length){back();return;}
  rows[Math.min(page.selected,rows.length-1)].run();
};
back=function(){
  if(view==='player'){
    if(detail){playerBack();return;}
    leavePlayer();view=page.name;render();say();return;
  }
  if(view==='ended'){
    const gi=group,selected=index;leavePlayer();
    history=[{name:'home',selected:0}];page={name:'episodes',gi,selected};view='episodes';render();say();return;
  }
  if(!history.length){view='home';page={name:'home',selected:page.name==='home'?page.selected:0};render();return;}
  page=history.pop();view=page.name;render();say();
};
function rightAction(){if(view==='home'){enter('options');return;}back();}
key=function(value){
  if(value==='*'){home();return;}
  if(value==='#'){playerKey(value);return;}
  if(value==='0'){
    if(view==='player'){
      remember();quality=(quality+1)%3;if(item)load(item,true,{autoplay:playing});
    }else{quality=(quality+1)%3;render();say();}return;
  }
  if(view==='player'){playerKey(value);return;}
  if(value==='5'){select();return;}
  if(value==='2'){move(-1);return;}
  if(value==='8'){move(1);return;}
};
load=function(selected,keep=false,options={}){
  if(view!=='player'&&view!=='ended')page=snapshot();
  remember();
  if(!locate(selected))return Promise.resolve();
  if(view==='player'&&!keep&&item&&selected.id!==item.id)remember();
  ending=null;
  const request=++serial;
  intent={resume:!!options.resume,autoplay:!!options.autoplay};
  const requestIntent={...intent};
  const pending=playerLoad(selected,keep),version=token;
  return Promise.resolve(pending).then(()=>{
    if(request!==serial||version!==token||view!=='player'||!clip||item?.id!==selected.id)return;
    if(requestIntent.resume){const p=saved.progress[selected.id];if(p&&!p.complete)elapsed=Math.max(0,Math.min(p.elapsed,total()-.001));}
    setPlaying(requestIntent.autoplay);paint();
    announce((playing?'Playing. ':'Ready. ')+short(selected));
  });
};
function endPlayback(){
  remember();const list=groups[group]?.items||[];const at=list.findIndex(e=>e.id===item?.id);
  ending={next:at>=0?list[at+1]||null:null,remaining:5000,last:null};view='ended';setPlaying(false);render();
}
tick=function(time){
  const wasPlaying=playing;playerTick(time);
  if(view==='player'&&clip&&playing&&time-lastSave>=2000){remember();lastSave=time;}
  if(view==='player'&&clip&&wasPlaying&&!playing&&elapsed>=total()&& !message)endPlayback();
  if(view==='ended'&&ending?.next&&saved.autoplayNext){
    if(document.hidden){ending.last=null;return;}
    const before=Math.ceil(ending.remaining/1000);
    if(ending.last!==null)ending.remaining=Math.max(0,ending.remaining-(time-ending.last));
    ending.last=time;
    if(ending.remaining===0){const next=ending.next;ending=null;begin(next);}
    else if(before!==Math.ceil(ending.remaining/1000))render();
  }
};
$('left').onclick=()=>select();
$('back').onclick=()=>rightAction();
document.querySelectorAll('.keypad [data-key]').forEach(b=>b.onclick=()=>key(b.dataset.key));
document.querySelectorAll('.nav [data-key]').forEach(b=>{
  b.onclick=()=>{
    const k=b.dataset.key;
    if(k==='5'){select();return;}
    if(k==='4'){if(view==='player')key('4');else back();return;}
    if(k==='2')move(-1);if(k==='8')move(1);
  };
});
document.addEventListener('visibilitychange',()=>{if(document.hidden){remember();if(ending)ending.last=null;}});
window.addEventListener('pagehide',remember);
Promise.resolve(window.wapflixReady).then(()=>{
  if(view!=='player'&&view!=='ended'){view='home';page={name:'home',selected:0};history=[];render();say();}
});
})();
