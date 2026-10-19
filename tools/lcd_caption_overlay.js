// Additive M3 layer. Cue times are absolute source times, never wall-clock times.
let captionCues=[],captionSession=null,captionsOn=true;
const captionText=$('captionText'),captionButton=$('captions'),captionInfo=$('captionInfo');
function renderCaptions(){
 const status=$('state').textContent;
 const active=session&&manifest&&captionSession===session&&painted>=0&&captionsOn&&
  !['Starting','Stopped','Finished'].includes(status)&&!status.startsWith('Error')&&!status.startsWith('Stop failed');
 // painted is the actual displayed frame. At a missing-chunk boundary it stays
 // behind clock, preventing captions advancing over a held video frame.
 const sourceTime=active?manifest.source_start+painted/manifest.fps:0;
 const lines=active?captionCues.filter(c=>sourceTime>=c.start&&sourceTime<c.end).flatMap(c=>c.text.split('\n')):[];
 const value=[...new Set(lines)].join('\n');
 if(captionText.textContent!==value)captionText.textContent=value;
}
captionButton.onclick=()=>{
 captionsOn=!captionsOn;captionButton.textContent='Captions: '+(captionsOn?'on':'off');
 captionButton.setAttribute('aria-pressed',String(captionsOn));renderCaptions();
};
const uncaptainedApi=api;
api=async function(path,body,signal){
 const requestGeneration=generation;
 const result=await uncaptainedApi(path,body,signal);
 if(path==='/api/start'&&requestGeneration===generation&&!signal?.aborted){
  const data=result.captions;
  if(!data||data.timebase!=='source'||!Array.isArray(data.cues))throw Error('Unsupported caption metadata');
  captionCues=data.cues;captionSession=result.id;captionsOn=true;
  captionButton.disabled=!captionCues.length;
  captionButton.textContent=captionCues.length?'Captions: on':'Captions: none';
  captionButton.setAttribute('aria-pressed',String(!!captionCues.length));
  captionInfo.textContent=data.track_found?
   `${data.selected_cue_count} cues in this extract; ${data.parse_error_count} parser warnings. Captions follow displayed video frames.`:
   'No adjacent SRT found. Use --srt /path/to/subtitles.srt to select one.';
  renderCaptions();
 }
 return result;
};
const uncaptainedDraw=draw;
draw=function(){uncaptainedDraw();renderCaptions();};
const uncaptainedPhase=phase;
phase=function(value){
 uncaptainedPhase(value);
 if(['Starting','Stopped','Finished'].includes(value)||value.startsWith('Error')||value.startsWith('Stop failed')){
  captionText.textContent='';
  if(['Starting','Stopped'].includes(value)){captionButton.disabled=true;captionSession=null;captionCues=[];captionInfo.textContent='Waiting for a session.';}
 }
};
