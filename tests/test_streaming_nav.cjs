const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.resolve(__dirname,'../streaming.js'),'utf8');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function setup(initial={}){
  const buttons=new Map();
  function button(id,key){if(!buttons.has(id))buttons.set(id,{dataset:{key},attrs:{},setAttribute(k,v){this.attrs[k]=v;},classList:{toggle(){}}});return buttons.get(id);}
  const keypad='1234567890*#'.split('').map(k=>button('key'+k,k));
  const nav=['4','2','8','5'].map(k=>button('nav'+k,k));
  const left=button('left'),back=button('back');
  const events={},winEvents={},draw=[],stored={};
  let raf=null,gate=null;
  const make=(prefix,count,series)=>Array.from({length:count},(_,i)=>({id:prefix+i,title:prefix+' '+i,episode_title:prefix+' '+i,episode:i+1,season:1,series,description:'An ASCII demo description.'}));
  const s={console,Promise,Date,Math,Number,String,Object,Array,Set,Map,
    groups:[{name:'FIRST S1',items:make('a',15,'FIRST')},{name:'SECOND S1',items:make('b',15,'SECOND')},{name:'ORIGINALS',items:make('o',15,null)}],
    group:0,index:0,view:'library',previous:'library',item:null,clip:null,elapsed:0,playing:false,detail:false,token:0,message:'',last:0,quality:0,lit:true,labels:['LOW','MEDIUM','HIGH'],
    localStorage:{getItem(){return JSON.stringify(initial);},setItem(k,v){stored[k]=JSON.parse(v);}},
    document:{hidden:false,querySelectorAll(q){return q.startsWith('.keypad')?keypad:nav;},addEventListener(k,f){events[k]=f;}},
    window:{wapflixReady:Promise.resolve(),addEventListener(k,f){winEvents[k]=f;},wapflixHandset:{current(){return '3310';},cycle(){return '8210';}}},
    $:id=>button(id),ink:'#25371e',ctx:{fillRect(){},save(){},restore(){}},
    text(t,x,y){draw.push({text:String(t),x,y});},center(t,y){draw.push({text:String(t),x:0,y});},header(){draw.length=0;},
    footer(l,r){s.footerLabels=[l,r];left.setAttribute('aria-label',l);back.setAttribute('aria-label',r);},
    wrap(t,w){const lines=[];for(const word of t.split(/\s+/)){if(!lines.length||lines.at(-1).length+word.length+1>w)lines.push(word);else lines[lines.length-1]+=' '+word;}return lines;},
    announce(t){s.spoken=t;},setPlaying(on){s.playing=on;s.last=0;},
    render(){s.header();s.footer(s.playing?'PAUSE':'PLAY','BACK');},
    paint(){s.render();},select(){if(s.detail)s.detail=false;s.setPlaying(!s.playing);s.paint();},
    back(){if(s.detail){s.detail=false;s.render();return;}s.view='episodes';s.clip=null;},
    key(k){if(k==='5')s.select();if(k==='1'){s.setPlaying(false);s.detail=!s.detail;s.render();}if(k==='2')s.captionToggles=(s.captionToggles||0)+1;if(k==='#'){s.lit=!s.lit;s.render();}if((k==='4'||k==='6')&&s.clip){s.elapsed=Math.max(0,Math.min(24,s.elapsed+(k==='4'?-5:5)));s.paint();}},
    async load(entry,keep){const id=++s.token,old=s.elapsed;s.item=entry;s.view='player';s.clip=null;s.detail=false;s.message='RECEIVING CHARACTERS...';s.setPlaying(false);s.render();await(gate||Promise.resolve());if(id!==s.token)return;s.clip={frames:Array(96).fill('x'),fps:4};s.elapsed=keep?old:0;s.message='';s.paint();},
    tick(t){if(s.playing&&s.clip){if(s.last)s.elapsed+=(t-s.last)/1000;s.last=t;if(s.elapsed>=24){s.elapsed=24;s.setPlaying(false);}s.paint();}raf=s.tick;}
  };
  back.onclick=s.back;left.onclick=s.select;
  vm.createContext(s);vm.runInContext(source,s);
  return {s,draw,buttons,events,winEvents,stored,step(t){(raf||s.tick)(t);},hold(){gate=new Promise(resolve=>this.release=()=>{resolve();gate=null;});},left(){left.onclick();},right(){back.onclick();},nav(k){button('nav'+k,k).onclick();}};
}
const tests=[];
function test(name,fn){tests.push({name,fn});}
function rowText(h){return h.draw.filter(d=>d.y>=40&&d.y<=180).map(d=>d.text).join(' ');}
async function openFirst(h){h.left();h.left();h.left();await settle();}
test('Home right soft key opens Options, Back restores focus',async()=>{
 const h=setup();await settle();h.right();assert.equal(h.s.view,'options');h.right();assert.equal(h.s.view,'home');assert.match(h.s.spoken,/SERIES/);
});
test('titles and first list row have separate vertical positions',async()=>{
 const h=setup();await settle();assert(h.draw.some(d=>d.y===26));assert(h.draw.some(d=>d.y===48));assert(!h.draw.some(d=>d.y===30));
});
test('physical Back is dynamically rebound and Info closes before leaving player',async()=>{
 const h=setup();await settle();await openFirst(h);assert.equal(h.s.view,'player');h.s.key('1');assert(h.s.detail);h.right();assert.equal(h.s.view,'player');assert(!h.s.detail);h.right();assert.equal(h.s.view,'series');assert.equal(h.s.playing,false);
});
test('About is a rendered screen; both buttons return to Options',async()=>{
 const h=setup();await settle();h.right();for(let i=0;i<4;i++)h.s.key('8');h.left();assert.equal(h.s.view,'about');assert.match(rowText(h),/ASCII DEMOS/);h.left();assert.equal(h.s.view,'options');h.left();assert.equal(h.s.view,'about');h.right();assert.equal(h.s.view,'options');
});
test('empty My List exits using either soft key',async()=>{
 const h=setup();await settle();h.s.key('8');h.s.key('8');h.left();assert.equal(h.s.view,'mylist');assert.equal(h.s.footerLabels[0],'BACK');h.left();assert.equal(h.s.view,'home');h.left();h.right();assert.equal(h.s.view,'home');
});
test('My List paginates 15 rows and Back preserves the selected row',async()=>{
 const h=setup({list:Array.from({length:15},(_,i)=>'a'+i)});await settle();h.s.key('8');h.s.key('8');h.left();for(let i=0;i<12;i++)h.s.key('8');assert.match(rowText(h),/a 12/);assert(!rowText(h).includes('a 0'));h.left();assert.equal(h.s.view,'details');h.right();assert.equal(h.s.view,'mylist');assert.match(rowText(h),/a 12/);
});
test('all menus clamp at boundaries rather than wrapping inconsistently',async()=>{
 const h=setup();await settle();h.s.key('2');assert.match(h.s.spoken,/SERIES/);h.right();for(let i=0;i<12;i++)h.s.key('8');assert.match(h.s.spoken,/ABOUT/);h.s.key('8');assert.match(h.s.spoken,/ABOUT/);
});
test('playing from My List synchronizes group for seek and next episode',async()=>{
 const h=setup({list:['b3']});await settle();h.s.key('8');h.s.key('8');h.left();h.left();h.left();await settle();assert.equal(h.s.group,1);assert.equal(h.s.index,3);assert.equal(h.s.item.id,'b3');h.s.key('6');assert.equal(h.s.elapsed,5);h.right();assert.equal(h.s.view,'details');h.right();assert.equal(h.s.view,'mylist');
});
test('dedicated navigation arrows do not accidentally toggle captions',async()=>{
 const h=setup();await settle();await openFirst(h);h.nav('2');assert.equal(h.s.captionToggles,undefined);h.s.key('2');assert.equal(h.s.captionToggles,1);
});
test('Home saves progress; Continue Watching resumes and retains Home focus',async()=>{
 const h=setup();await settle();await openFirst(h);h.s.elapsed=10;h.s.key('*');assert.equal(h.s.view,'home');assert.match(rowText(h),/RESUME a 0/);h.left();await settle();assert.equal(h.s.elapsed,10);assert(h.s.playing);h.right();assert.equal(h.s.view,'home');
});
test('completed episodes retain SEEN and leave Continue Watching',async()=>{
 const h=setup();await settle();await openFirst(h);h.s.elapsed=23;h.s.last=1000;h.step(2000);assert.equal(h.s.view,'ended');assert(h.stored['wapflix-state-v1'].progress.a0.complete);h.right();assert.equal(h.s.view,'episodes');assert.match(rowText(h),/SEEN/);h.s.key('*');assert(!rowText(h).includes('RESUME a 0'));
});
test('next countdown works through scheduled frame callbacks and can be cancelled',async()=>{
 const h=setup();await settle();await openFirst(h);h.s.elapsed=23;h.s.last=1000;h.step(2000);h.step(4500);h.step(7000);await settle();assert.equal(h.s.item.id,'a1');assert(h.s.playing);
 h.s.elapsed=23;h.s.last=8000;h.step(9000);h.right();h.step(15000);assert.equal(h.s.view,'episodes');assert.equal(h.s.playing,false);
});
test('hidden tab suspends end countdown instead of starting another episode',async()=>{
 const h=setup();await settle();await openFirst(h);h.s.elapsed=23;h.s.last=1000;h.step(2000);h.s.document.hidden=true;h.events.visibilitychange();h.step(9000);h.s.document.hidden=false;h.step(20000);assert.equal(h.s.view,'ended');h.step(25000);await settle();assert.equal(h.s.item.id,'a1');
});
test('shared-style load stays paused, including a position at the end',async()=>{
 const h=setup();await settle();await h.s.load(h.s.groups[1].items[5]);h.s.elapsed=24;h.step(1000);assert.equal(h.s.view,'player');assert.equal(h.s.playing,false);assert.equal(h.s.group,1);
});
test('leaving a pending download prevents stale playback',async()=>{
 const h=setup();await settle();h.left();h.left();h.hold();h.left();assert.equal(h.s.view,'player');h.right();h.release();await settle();assert.equal(h.s.view,'series');assert.equal(h.s.clip,null);assert.equal(h.s.playing,false);
});
test('quality change preserves time and playing state',async()=>{
 const h=setup();await settle();await openFirst(h);h.s.elapsed=9;h.s.key('0');await settle();assert.equal(h.s.elapsed,9);assert(h.s.playing);h.left();h.s.key('0');await settle();assert(!h.s.playing);
});
test('pagehide flushes progress synchronously',async()=>{
 const h=setup();await settle();await openFirst(h);h.s.elapsed=11;h.winEvents.pagehide();assert.equal(h.stored['wapflix-state-v1'].progress.a0.elapsed,11);
});
(async()=>{let failed=0;for(const {name,fn} of tests){try{await fn();console.log('PASS '+name);}catch(e){failed++;console.error('FAIL '+name+'\n'+e.stack);}}if(failed)process.exitCode=1;else console.log(tests.length+' navigation regression tests passed.');})();
