(() => {
'use strict';
// UI text remains uppercase. ASCII artwork keeps its original character case.
const artGlyphs = {...glyphs,i:'04000C0404040E',r:'00001619101010',s:'00000F100E011E',h:'10101619111111',o:'00000E1111110E'};
const menuRender = render, oldKey = key, oldSelect = select, oldBack = back;
let captions = true;
function artText(value,x,y) {
  imageCtx.fillStyle = ink;
  for (const char of value) {
    const bits = artGlyphs[char] || artGlyphs[char.toUpperCase()];
    if (bits) for(let row=0;row<7;row++) {
      const mask=parseInt(bits.slice(row*2,row*2+2),16);
      for(let col=0;col<5;col++) if(mask&(16>>col)) imageCtx.fillRect(x+col,y+row,1,1);
    }
    x+=6;
  }
}
function panel(y,height) {
  ctx.fillStyle=lit?'#a6bd70':'#7c8c62';
  ctx.fillRect(0,y,240,height);
}
function info() {
  panel(0,224);
  center('TRANSMISSION INFO',5);
  const title=item.episode_title||item.title;
  wrap(title,37).slice(0,2).forEach((line,n)=>text(line,5,25+n*10));
  wrap(item.description,37).slice(0,8).forEach((line,n)=>text(line,5,51+n*11));
  text(`${seconds(elapsed)} / ${seconds(clip.frames.length/clip.fps)}   ${labels[quality]}`,5,150);
  text(`${clip.cols}X${clip.rows} / ${clip.fps} FPS / ${(bytes/1024).toFixed(1)}K`,5,163);
  text('2 CAPTIONS '+(captions?'ON':'OFF')+' / 3 SHARE',5,178);
  text(item.fictional?'ASCII DEMO / INVENTED DIALOGUE':'ORIGINAL ASCII ART',5,192);
  footer('PLAY','BACK');
}
render = function() {
  if(view!=='player') { menuRender(); return; }
  ctx.clearRect(0,0,240,224);
  if(message || !clip) {
    center('TRANSMISSION',25);
    wrap(message||'CONNECTING...',36).slice(0,8).forEach((line,n)=>center(line,73+n*12));
    footer(message.startsWith('RECEIVING')?'WAIT':'PLAY','BACK');
    return;
  }
  if(detail) { info(); return; }
  ctx.imageSmoothingEnabled=false;
  const native=clip.layout==='phone-cells';
  const width=clip.cols*(native?6:4),height=clip.rows*8;
  const scale=Math.min(240/width,200/height);
  const w=Math.round(width*scale),h=Math.round(height*scale);
  ctx.drawImage(image,Math.floor((240-w)/2),Math.floor((200-h)/2),w,h);
  const subtitle=captions?(clip.subtitles||[]).find(s=>elapsed>=s.start&&elapsed<s.end):null;
  if(subtitle) {
    const lines=wrap(subtitle.text,38).slice(0,3),height=lines.length*10+8,y=200-height;
    panel(y,height);
    lines.forEach((line,n)=>center(line,y+4+n*10));
  }
  if(!playing) {
    const lines=wrap(item.episode_title||item.title,38).slice(0,2);
    panel(0,lines.length*10+20);
    lines.forEach((line,n)=>text(line,4,4+n*10));
    text('PAUSED '+seconds(elapsed)+' / '+seconds(clip.frames.length/clip.fps),4,lines.length*10+7);
  }
  ctx.fillStyle=ink;
  ctx.fillRect(2,204,Math.round(236*Math.min(1,elapsed/(clip.frames.length/clip.fps))),2);
  footer(playing?'PAUSE':'PLAY','BACK');
};
paint = function() {
  if(!clip) return;
  const n=Math.min(clip.frames.length-1,Math.floor(elapsed*clip.fps));
  if(n!==frame) {
    frame=n;
    const width=clip.cols*6,height=clip.rows*8;
    if(image.width!==width||image.height!==height) { image.width=width;image.height=height; }
    imageCtx.clearRect(0,0,width,height);
    clip.frames[n].split('\n').forEach((line,row)=>artText(line,0,row*8));
  }
  render();
};
key = function(value) {
  if(view==='player'&&clip&&value==='2') {
    captions=!captions;render();announce('Captions '+(captions?'on.':'off.'));return;
  }
  if(view==='player'&&clip&&value==='1'&&!detail) setPlaying(false);
  oldKey(value);
};
select = function() {
  if(view==='player'&&clip&&detail) detail=false;
  oldSelect();
};
back = function() {
  if(view==='player'&&detail) {detail=false;render();announce('Player.');return;}
  oldBack();
};
if(view==='player'&&clip) paint();
})();
