#!/usr/bin/env python3
"""Fetch actual English captions for the agreed YouTube test; no video download."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from srt import parse_srt
from wapflix_captions import english_track

URL='https://www.youtube.com/watch?v=dQw4w9WgXcQ'
DEFAULT=Path.home()/'.local/share/wapflix/test-media/dQw4w9WgXcQ/source.youtube.en.srt'

def run_ytdlp(arguments):
    try:
        result=subprocess.run(['yt-dlp','--ignore-config','--no-playlist','--socket-timeout','30',*arguments],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('yt-dlp timed out; no successful caption download was recorded') from error
    if result.returncode:
        raise RuntimeError('yt-dlp failed:\n'+result.stderr[-6000:])
    if result.stderr.strip():print(result.stderr[-3000:],file=sys.stderr)
    return result.stdout

def fetch(output,refresh=False):
    output=Path(output).expanduser()
    if output.is_symlink():raise ValueError('Refusing a symlink output')
    provenance=output.with_suffix('.json')
    if output.exists() and not refresh:
        if not provenance.is_file():raise ValueError('Existing SRT lacks provenance; use --refresh to fetch an actual YouTube track')
        record=json.loads(provenance.read_text())
        if record.get('video_id')!='dQw4w9WgXcQ' or record.get('sha256')!=hashlib.sha256(output.read_bytes()).hexdigest():
            raise ValueError('Existing SRT/provenance mismatch; use --refresh to fetch a fresh track')
        parsed=parse_srt(output)
        if not parsed.cues:raise ValueError('Existing SRT contains no valid cues')
        print(json.dumps({'cached':True,'path':str(output),'cue_count':len(parsed.cues),
                          'language':record['language'],'track_type':record['track_type']}))
        return record
    for tool in ('yt-dlp','ffmpeg'):
        if not shutil.which(tool):raise ValueError(f'{tool} is required on PATH')
    metadata=json.loads(run_ytdlp(['--skip-download','--dump-single-json',URL]))
    if metadata.get('id')!='dQw4w9WgXcQ':raise ValueError('Unexpected video metadata; refusing to save captions')
    language,kind=english_track(metadata)
    print(f'Selected English track {language} ({"uploaded" if kind=="subtitles" else "automatic"}).',file=sys.stderr)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.caption-fetch-',dir=output.parent) as folder:
        stage=Path(folder)
        options=['--skip-download','--sub-langs',language,'--sub-format','vtt/best','--convert-subs','srt',
                 '-o',str(stage/'source.%(ext)s')]
        options+=['--write-subs','--no-write-auto-subs'] if kind=='subtitles' else ['--no-write-subs','--write-auto-subs']
        run_ytdlp([*options,URL])
        candidates=list(stage.glob('*.srt'))
        if len(candidates)!=1:raise ValueError('yt-dlp did not produce exactly one SRT. No successful download was recorded.')
        candidate=candidates[0]
        parsed=parse_srt(candidate)
        if not parsed.cues:raise ValueError('Downloaded SRT contains no valid cues')
        data=candidate.read_bytes()
        record={'video_id':'dQw4w9WgXcQ','source_url':URL,'language':language,'track_type':kind,
                'downloaded_at_utc':datetime.now(timezone.utc).isoformat(),
                'cue_count':len(parsed.cues),'parse_error_count':len(parsed.errors),
                'sha256':hashlib.sha256(data).hexdigest()}
        staged_record=stage/'provenance.json';staged_record.write_text(json.dumps(record,indent=2)+'\n')
        if refresh:
            # Preserve a previous copy for manual recovery before replacing it.
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            for old in (output,provenance):
                if old.exists():shutil.copy2(old,old.with_name(old.name+'.backup-'+stamp))
        elif output.exists() or provenance.exists():
            raise ValueError('Output appeared during download; refusing to overwrite it')
        os.replace(candidate,output);os.replace(staged_record,provenance)
    print(json.dumps({'cached':False,'path':str(output),'cue_count':record['cue_count'],
                      'parse_error_count':record['parse_error_count'],'language':language,'track_type':kind}))
    return record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT)
    parser.add_argument('--refresh',action='store_true',help='fetch anew, preserving backups of old files')
    args=parser.parse_args();fetch(args.output,args.refresh)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError) as error:
        print(f'Subtitle fetch stopped: {error}',file=sys.stderr);raise SystemExit(2)
