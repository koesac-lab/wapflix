"""Caption timing and YouTube English-track selection helpers."""
import html
import math
import re
from srt import parse_srt

def english_track(metadata):
    priority={'en':0,'en-orig':1,'en-US':2,'en-GB':3}
    for kind in ('subtitles','automatic_captions'):
        tracks=metadata.get(kind) or {}
        candidates=[language for language,formats in tracks.items()
                    if re.fullmatch(r'en(?:[-_][A-Za-z0-9_-]+)?',language) and formats]
        if candidates:
            language=min(candidates,key=lambda value:(priority.get(value,4),value))
            return language,kind
    raise ValueError('No English subtitle track found. No substitute captions were generated.')

def load_captions(path,start,seconds):
    if not math.isfinite(start) or start<0 or not math.isfinite(seconds) or seconds<=0:
        raise ValueError('Invalid extract timing')
    parsed=parse_srt(path)
    if not parsed.cues:raise ValueError('SRT contains no valid cues; inspect subtitle download/parser errors')
    cues=[]
    for cue in parsed.cues:
        if cue.end<=start or cue.start>=start+seconds:continue
        text=html.unescape(cue.text)
        # Deduplicate identical lines, without attempting to rewrite rolling auto captions.
        text='\n'.join(dict.fromkeys(text.splitlines())).strip()
        if text:cues.append({'start':max(0.0,cue.start-start),'end':min(seconds,cue.end-start),'text':text})
    return {'cues':cues,'source_cue_count':len(parsed.cues),'selected_cue_count':len(cues),
            'parse_error_count':len(parsed.errors),'encoding':getattr(parsed,'encoding','unknown'),
            'source_start_seconds':start,'extract_seconds':seconds}
