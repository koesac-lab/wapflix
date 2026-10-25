/* 5A.5B: bounded LCD caption presentation. No transport, clock or persistence. */
(function(root){
'use strict';
const COLUMNS = 38, MAX_LINES = 3, BOTTOM = 178;
function layoutLines(lines){
  const output = [];
  for (const value of lines) {
    let line = '';
    for (const word of String(value).split(/\s+/).filter(Boolean)) {
      let points = Array.from(word);
      if (line && Array.from(line).length + 1 + points.length > COLUMNS) { output.push(line); line = ''; }
      while (points.length > COLUMNS) { output.push(points.slice(0,COLUMNS).join('')); points = points.slice(COLUMNS); }
      const remainder = points.join('');
      if (remainder) line += (line ? ' ' : '') + remainder;
    }
    if (line) output.push(line);
  }
  if (output.length > MAX_LINES) {
    output.length = MAX_LINES;
    output[MAX_LINES-1] = Array.from(output[MAX_LINES-1]).slice(0,COLUMNS-3).join('').trimEnd() + '...';
  }
  return Object.freeze(output);
}
function create({selector,context,drawText,ink='#25371e',panelColour=()=> '#a6bd70',onText=()=>{}}={}){
  if (!selector?.prepare || !selector?.selectFrame || !context || typeof drawText !== 'function') {
    throw TypeError('Caption selector, canvas context and text renderer are required');
  }
  let enabled = true, loaded = false, track = selector.prepare(null), spoken = '';
  let selected = selector.selectFrame(track,null), visibleLines = Object.freeze([]);
  const publish = text => { if (text !== spoken) { spoken = text; onText(text); } };
  function clear(){
    loaded = false; track = selector.prepare(null); selected = selector.selectFrame(track,null);
    visibleLines = Object.freeze([]); publish('');
  }
  function setTrack(metadata){
    track = selector.prepare(metadata); loaded = true; selected = selector.selectFrame(track,null);
    visibleLines = Object.freeze([]); publish('');
  }
  function draw(presentedFrame,active=true){
    selected = selector.selectFrame(track,active && enabled ? presentedFrame : null);
    visibleLines = layoutLines(selected.lines); publish(selected.text);
    if (!visibleLines.length) return;
    const height = visibleLines.length*10+8, y = BOTTOM-height;
    context.fillStyle = panelColour(); context.fillRect(0,y,240,height);
    context.fillStyle = ink;
    visibleLines.forEach((line,index)=>drawText(line,Math.max(2,Math.floor((240-Array.from(line).length*6)/2)),y+4+index*10));
  }
  function toggle(){ enabled = !enabled; if (!enabled) { selected = selector.selectFrame(track,null); visibleLines = Object.freeze([]); publish(''); } return enabled; }
  function description(){
    const prefix = 'Captions ' + (enabled ? 'on.' : 'off.');
    if (!enabled) return prefix;
    if (!loaded) return prefix + ' Waiting for subtitle metadata.';
    if (track.status === 'missing') return prefix + ' No subtitle track.';
    if (track.status === 'invalid') return prefix + ' Subtitle metadata invalid.';
    return prefix + (track.warnings.length ? ' Subtitle warnings available.' : '');
  }
  function snapshot(){
    return Object.freeze({enabled,loaded,status:track.status,cueCount:track.cues.length,
      warningCount:track.warnings.length,parseErrorCount:track.parseErrorCount,
      sourceTime:selected.sourceTime,text:selected.text,lines:visibleLines});
  }
  return Object.freeze({clear,setTrack,draw,toggle,description,snapshot,get enabled(){return enabled;}});
}
const api = Object.freeze({layoutLines,create,columns:COLUMNS,maxLines:MAX_LINES,bottom:BOTTOM});
if (typeof module !== 'undefined' && module.exports) module.exports = api;
else root.WapflixHandsetCaptions = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
