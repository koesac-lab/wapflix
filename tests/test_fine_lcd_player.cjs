const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const draws=[],fills=[],spoken=[],loads=[];
const c={quality:0,glyphs:{},ink:'#25371e',render(){},key(){},select(){},back(){},
  clip:null,item:null,view:'player',frame:-1,elapsed:0,playing:true,message:'',detail:false,lit:true,bytes:10,
  labels:['LOW','MEDIUM','HIGH'],text(){},center(){},footer(){},wrap(s){return [s||''];},seconds:String,
  ctx:{clearRect(){},fillRect(){},drawImage(...a){draws.push(a);}},
  image:{width:1,height:1},imageCtx:{clearRect(){fills.length=0;},fillRect(...a){fills.push(a);}},
  localStorage:{getItem(){return null;},setItem(){}},announce(s){spoken.push(s);},setPlaying(on){c.playing=on;},
  load(e,keep){c.item=e;loads.push({e,keep});return Promise.resolve();}};
vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(__dirname,'../player.js'),'utf8'),c);
assert.equal(c.quality,1);
c.load({title:'Test',variants:{medium:{path:'lcd'}},lcd_variants:{medium:{path:'lcd'}},lcd_only:true});
c.clip={layout:'lcd-1bit',encoding:'hex-msb',cols:240,rows:135,fps:8,frames:['80'+'00'.repeat(4049)]};
c.paint();assert.equal(c.image.width,240);assert.equal(c.image.height,135);
assert.equal(draws.at(-1)[3],240);assert.equal(draws.at(-1)[4],135);
assert.deepEqual(fills,[[0,0,1,1]]);
const before=loads.length;c.key('7');assert.equal(loads.length,before);assert.match(spoken.at(-1),/--ascii/);
c.item={title:'Legacy',variants:{medium:{path:'ascii'}},lcd_variants:{medium:{path:'lcd'}}};
c.key('7');assert.equal(loads.at(-1).e.variants.medium.path,'ascii');
console.log('Fine LCD player checks passed: default medium, 240px 1:1, bit order, LCD-only notice, ASCII fallback.');
