// M4B: UI only. The server remains the verified M4A restart-seek implementation.
let navigationId=null,seekRevision=0,seekRange=null,seekPending=false,seekTarget=0,seekIntent=true,seekCaptions=true;
const seekBack=$('seekBack'),seekForward=$('seekForward'),seekGo=$('seekGo'),seekPosition=$('seekPosition'),seekNotice=$('seekNotice');
function latestSourcePosition(){
 if(seekPending)return seekTarget;
 return manifest?manifest.source_start+(painted>=0?painted/manifest.fps:clock):seekRange?.start||0;
}
function updateSeekUI(){
 const enabled=!!navigationId&&!!seekRange;
 for(const element of [seekBack,seekForward,seekGo,seekPosition])element.disabled=!enabled;
 if(enabled){
  seekPosition.min=String(seekRange.start);seekPosition.max=String(seekRange.last);
  if(document.activeElement!==seekPosition)seekPosition.value=latestSourcePosition().toFixed(3);
 }
}
function readNavigation(data){
 if(typeof data.navigation_id!=='string'||!Number.isFinite(data.range_start)||!Number.isFinite(data.range_end)||data.range_end<=data.range_start||!Number.isSafeInteger(data.revision)||data.revision<0||!Number.isFinite(data.fps)||data.fps<=0)throw Error('Unsupported M4A navigation metadata');
 navigationId=data.navigation_id;seekRevision=data.revision;
 seekRange={start:data.range_start,end:data.range_end,last:data.range_start+Math.max(0,Math.ceil((data.range_end-data.range_start)*data.fps)-1)/data.fps};
 seekTarget=data.source_start;seekIntent=true;seekPending=false;
 seekNotice.textContent=`Seek within source ${seekRange.start.toFixed(3)}–${seekRange.end.toFixed(3)} seconds. Every seek restarts conversion.`;
 updateSeekUI();
}
const beforeSeekApi=api;
api=async function(path,body,signal){
 const g=generation;
 // A paused seek must still generate its initial picture/buffer before parking
 // the worker. Otherwise an early paused heartbeat can deadlock startup.
 if(path==='/api/pulse'&&navigationId&&!warmed&&body)body={...body,paused:false};
 const data=await beforeSeekApi(path,body,signal);
 if(path==='/api/start'){
  if(g===generation&&!signal?.aborted)readNavigation(data);
  else if(data?.navigation_id)navigator.sendBeacon('/api/navigation/stop',JSON.stringify({navigation_id:data.navigation_id,token}));
 }
 return data;
};
const oldPause=$('pause').onclick;
$('pause').onclick=()=>{oldPause();if(!seekPending)seekIntent=intent;};
stop=async function(){
 const nav=navigationId,old=session;
 navigationId=null;seekRange=null;seekPending=false;session=null;++generation;const stopGeneration=generation;
 if(controller)controller.abort();busy=false;intent=false;last=null;manifest=null;painted=-1;frames.clear();
 $('pause').disabled=true;$('stop').disabled=true;phase('Stopped');seekNotice.textContent='Stopped';updateSeekUI();
 try{
  if(nav)await api('/api/navigation/stop',{navigation_id:nav});
  else if(old)await api('/api/stop',{id:old});
  return true;
 }catch(error){if(generation===stopGeneration)phase('Stop failed: '+error.message);return false;}
};
$('stop').onclick=()=>stop();
window.addEventListener('pagehide',()=>{
 if(navigationId)navigator.sendBeacon('/api/navigation/stop',JSON.stringify({navigation_id:navigationId,token}));
});
function adoptSeek(data,wanted,captionsWanted){
 wanted=wanted&&!document.hidden;
 if(data.captions?.timebase!=='source'||!Array.isArray(data.captions.cues))throw Error('Unsupported caption metadata');
 session=data.id;manifest=data;clock=0;last=null;painted=-1;frames.clear();warmed=false;intent=wanted;
 seekPending=false;seekTarget=data.source_start;
 canvas.width=data.cols;canvas.height=data.rows;ctx.fillStyle='#a6bd70';ctx.fillRect(0,0,canvas.width,canvas.height);
 captionCues=data.captions.cues;captionSession=data.id;captionsOn=captionsWanted;
 captionButton.disabled=!captionCues.length;captionButton.textContent=captionCues.length?'Captions: '+(captionsOn?'on':'off'):'Captions: none';
 captionButton.setAttribute('aria-pressed',String(!!captionCues.length&&captionsOn));
 captionInfo.textContent=data.captions.track_found?`${data.captions.selected_cue_count} cues after seek; ${data.captions.parse_error_count} parser warnings.`:'No SRT track.';
 $('pause').disabled=false;$('pause').textContent=wanted?'Pause':'Resume';$('stop').disabled=false;
 phase(wanted?'Buffering':'Paused');seekNotice.textContent='Seeking buffer at source '+data.source_start.toFixed(3)+'s';updateSeekUI();poll();
}
async function seekTo(value){
 if(!navigationId||!seekRange)return;
 const number=Number(value);
 if(String(value).trim()===''||!Number.isFinite(number)){seekNotice.textContent='Enter a finite source time in seconds.';return;}
 const position=Math.max(seekRange.start,Math.min(seekRange.last,number));
 if(!seekPending){seekIntent=intent;seekCaptions=captionsOn;}
 const wanted=seekIntent,captionsWanted=seekCaptions,nav=navigationId,revision=++seekRevision,g=++generation;
 if(controller)controller.abort();controller=new AbortController();busy=false;
 seekPending=true;seekTarget=position;session=null;manifest=null;intent=false;last=null;painted=-1;warmed=false;frames.clear();
 captionText.textContent='';captionCues=[];captionSession=null;captionButton.disabled=true;
 $('pause').disabled=true;$('stop').disabled=false;phase('Buffering');seekNotice.textContent='Requesting source '+position.toFixed(3)+'s';updateSeekUI();
 try{
  const data=await api('/api/seek',{navigation_id:nav,revision,position},controller.signal);
  if(g!==generation||nav!==navigationId)return;
  if(data.navigation_id!==nav||data.revision!==revision)throw Error('Unexpected seek response revision');
  adoptSeek(data,wanted,captionsWanted);
 }catch(error){
  if(g===generation&&error.name!=='AbortError'){
   const message=error.message,cleanup=stop(),cleanupGeneration=generation;await cleanup;
   if(generation===cleanupGeneration){phase('Error: '+message);seekNotice.textContent='Seek failed. Start a new session to retry.';}
  }
 }
}
seekBack.onclick=()=>seekTo(latestSourcePosition()-10);
seekForward.onclick=()=>seekTo(latestSourcePosition()+10);
seekGo.onclick=()=>seekTo(seekPosition.value);
seekPosition.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();seekTo(seekPosition.value);}});
const beforeSeekDraw=draw;
draw=function(){beforeSeekDraw();updateSeekUI();};
updateSeekUI();
