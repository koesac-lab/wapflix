// Isolated player contract tests; no browser dependencies.
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const fills=[],draws=[],loads=[],announcements=[],storage=new Map();
const context={
  glyphs:{A:'0E11111F111111'},ink:'#25371e',
  ctx:{clearRect(){},fillRect(){},drawImage(...args){draws.push(args);}},
  image:{width:1,height:1},imageCtx:{clearRect(){fills.length=0;},fillRect(...args){fills.push(args);}},
  render(){},key(){},select(){},back(){},
  view:'player',clip:null,item:null,elapsed:0,frame:-1,playing:false,message:'',detail:false,
  lit:true,bytes:10,quality:0,labels:['14.4K'],
  text(){},center(){},footer(){},wrap(s){return [s||''];},seconds:s=>String(s),
  announce:s=>announcements.push(s),setPlaying(on){context.playing=on;},
  localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
  load(selected,keep){loads.push({selected,keep});context.item=selected;return Promise.resolve();}
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../player.js'),'utf8'),context);
const entry={id:'test',title:'Test',description:'Original study',
  variants:{low:{path:'ascii'}},lcd_variants:{low:{path:'lcd'}}};
context.load(entry);
assert.equal(loads.at(-1).selected.variants.low.path,'lcd');
context.clip={layout:'lcd-1bit',encoding:'hex-msb',cols:4,rows:2,fps:4,frames:['a5'],subtitles:[]};
context.paint();
assert.equal(context.image.width,4);assert.equal(context.image.height,2);
assert.deepEqual(fills,[[0,0,1,1],[2,0,1,1],[1,1,1,1],[3,1,1,1]]);
assert.equal(draws.at(-1)[3],240);assert.equal(draws.at(-1)[4],120);
const actualLoad=context.load;let switched;
context.load=(selected,keep,options)=>{switched={selected,keep,options};return actualLoad(selected,keep);};
context.playing=true;context.elapsed=2.5;context.key('7');
assert.equal(storage.get('wapflix-renderer'),'ascii');
assert.equal(loads.at(-1).selected.variants.low.path,'ascii');
assert.equal(switched.keep,true);assert.equal(switched.options.autoplay,true);assert.equal(context.elapsed,2.5);
context.key('7');assert.equal(loads.at(-1).selected.variants.low.path,'lcd');
const legacy={id:'legacy',variants:{low:{path:'legacy-ascii'}}};
context.load(legacy);assert.equal(loads.at(-1).selected.variants.low.path,'legacy-ascii');
context.key('7');assert.match(announcements.at(-1),/No LCD variant/);
context.item=entry;context.frame=-1;
context.clip={cols:1,rows:1,fps:4,frames:['A'],layout:'phone-cells'};
context.elapsed=0;context.paint();assert.equal(context.image.width,6);assert.equal(context.image.height,8);
assert.ok(fills.length>0);
context.frame=-1;context.clip={cols:3,rows:3,fps:4,frames:['ff80'],layout:'lcd-1bit',encoding:'hex-msb'};
context.paint();assert.equal(fills.length,9);
context.frame=-1;context.clip.frames=['nothex'];context.playing=true;
context.paint();assert.equal(context.playing,false);assert.equal(context.message,'INVALID LCD FRAME');
console.log('LCD player contracts passed: bit order, dimensions, padding, integer scaling, mode selection, playback intent, legacy fallback, invalid data.');
