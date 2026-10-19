#!/usr/bin/env python3
"""Exercise M4A restart-seeking, then stop its session. Close the viewer first."""
import argparse
import gzip
import http.client
import json
import math
import re
import time
from urllib.parse import urlencode,urlsplit

def run(url):
    parsed=urlsplit(url)
    if parsed.scheme!='http' or not parsed.hostname or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('Use a direct HTTP server URL, such as http://127.0.0.1:8101')
    token=None;navigation=None;session=None
    def request(path,body=None):
        connection=http.client.HTTPConnection(parsed.hostname,parsed.port or 80,timeout=10)
        headers={'X-Wapflix-Test':token} if token else {}
        if body is not None: headers['Content-Type']='application/json'
        try:
            connection.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
            response=connection.getresponse();raw=response.read()
            if response.getheader('Content-Encoding')=='gzip': raw=gzip.decompress(raw)
            if not 200<=response.status<300: raise RuntimeError(f'HTTP {response.status}: '+raw.decode(errors='replace'))
            if response.status==204: return None
            return raw.decode() if response.getheader('Content-Type','').startswith('text/html') else json.loads(raw)
        finally: connection.close()
    try:
        page=request('/');match=re.search(r'<script nonce="([0-9a-f]+)"',page)
        if not match: raise ValueError('Could not find the local viewer capability token')
        token=match.group(1);data=request('/api/start',{});session=data['id']
        navigation=data.get('navigation_id')
        if not navigation: raise ValueError('This is not the M4A API server; start tools/lcd_stream_seek_api.py')
        lo,hi=data['range_start'],data['range_end']
        if hi-lo<1: raise ValueError('Choose an extract at least one second long')
        forward=lo+min(10,(hi-lo)/2);back=lo
        for revision,target in enumerate((forward,back,forward),1):
            data=request('/api/seek',dict(navigation_id=navigation,revision=revision,position=target));session=data['id']
            deadline=time.monotonic()+8
            while True:
                status=request('/api/pulse',dict(id=session,frame=0,paused=False))
                if status['state'] in ('error','stopped'): raise RuntimeError(status.get('error') or status['state'])
                chunk=request('/api/chunk?'+urlencode(dict(id=session,n=0)))
                if chunk is not None: break
                if time.monotonic()>deadline: raise RuntimeError('Timed out waiting for first seek chunk')
                time.sleep(.05)
            expected=lo+math.floor((target-lo)*8)/8
            if chunk['source_start']!=expected or data['captions']['timebase']!='source': raise RuntimeError('Seek timeline mismatch')
            print(json.dumps(dict(event='seek-ok',revision=revision,requested=target,source_start=chunk['source_start'],frames=len(chunk['frames']),caption_cues=data['captions']['selected_cue_count'])),flush=True)
    finally:
        if navigation: request('/api/navigation/stop',dict(navigation_id=navigation))
        elif session: request('/api/stop',dict(id=session))
    print(json.dumps(dict(event='m4a-complete',seeks=3,session_stopped=True)),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',default='http://127.0.0.1:8101');args=p.parse_args();run(args.url)

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError) as error:
        raise SystemExit('Seek smoke test failed: '+str(error))
