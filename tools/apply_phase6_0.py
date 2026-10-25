#!/usr/bin/env python3
"""Install 6.0A new-only tooling from a separate staging directory. Dry-run by default."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

def sha(data):return hashlib.sha256(data).hexdigest()
def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def confined(root,name):
    relative=Path(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Unsafe package path')
    target=root
    for part in relative.parts:
        target=target/part
        if target.is_symlink():raise ValueError('Symlink refused: '+name)
    if not target.resolve().is_relative_to(root):raise ValueError('Path escape: '+name)
    return target

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();root=args.root.resolve(strict=True);package=Path(__file__).resolve().parents[1]
    raw=(package/'MANIFEST_6_0.json').read_bytes();manifest=json.loads(raw)
    top=subprocess.check_output(['git','-C',str(root),'rev-parse','--show-toplevel'],text=True).strip()
    head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if Path(top).resolve()!=root or head!=manifest['baseline_commit']:
        raise ValueError('Checkout root/HEAD differs from the verified baseline')
    for name,expected in manifest['dependencies'].items():
        p=confined(root,name)
        if not p.is_file() or blob(p.read_bytes())!=expected:raise ValueError('Dependency mismatch: '+name)
    changes=[]
    for name,expected in manifest['files'].items():
        data=confined(package/'payload',name).read_bytes()
        if sha(data)!=expected:raise ValueError('Payload checksum mismatch: '+name)
        changes.append((name,data))
    changes.append(('MANIFEST_6_0.json',raw));plan=[]
    for name,data in changes:
        p=confined(root,name)
        if p.exists():
            if not p.is_file() or p.read_bytes()!=data:raise ValueError('Existing-file collision: '+name)
            print('ALREADY',name)
        else:plan.append((p,data));print('CREATE',name)
    if not args.apply:
        print('Dry-run passed; no files written. Add --apply to install.');return
    created=[]
    try:
        for p,data in plan:
            p=confined(root,str(p.relative_to(root)));p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as stream:stream.write(data)
            created.append((p,data))
    except Exception:
        for p,data in reversed(created):
            if p.is_file() and p.read_bytes()==data:p.unlink()
        raise
    print('Installed new tooling only. Playback, media, cache/state, network and Git index unchanged.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        print('REFUSED: '+str(error),file=sys.stderr);sys.exit(2)
