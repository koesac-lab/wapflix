#!/usr/bin/env python3
"""Apply 5A.5B from staging: verified source transforms plus new caption files."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def confined(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name: raise ValueError('Unsafe path: '+name)
    path = root/name
    cursor = path
    while cursor != root:
        if cursor.is_symlink(): raise ValueError('Symlink refused: '+name)
        cursor = cursor.parent
    if not path.resolve().is_relative_to(root): raise ValueError('Path escapes root: '+name)
    return path


def transformed(raw, record, name):
    text = raw.decode()
    if blob(raw) == record['before']:
        for old, new in record['edits']:
            if text.count(old) != 1: raise ValueError('Missing unique transform anchor: '+name)
            text = text.replace(old,new,1)
        return text.encode()
    reverse = text
    for old, new in reversed(record['edits']):
        if reverse.count(new) != 1: raise ValueError('Unexpected local version: '+name)
        reverse = reverse.replace(new,old,1)
    if blob(reverse.encode()) != record['before']: raise ValueError('Unexpected local edits: '+name)
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]; target = args.root.expanduser().resolve()
    if source == target or not target.is_dir(): parser.error('Extract separately and specify the checkout root')
    name = 'MANIFEST_5A5B.json'; raw_manifest = (source/name).read_bytes(); manifest = json.loads(raw_manifest)
    errors, payload = [], {name:raw_manifest}
    for filename, expected in manifest['sha256'].items():
        raw = confined(source,filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected: errors.append('Package checksum mismatch: '+filename)
        payload[filename] = raw
        dest = confined(target,filename)
        if dest.exists() and (not dest.is_file() or dest.read_bytes() != raw): errors.append('Conflicting existing new file: '+filename)
    for filename, record in manifest['patches'].items():
        try: payload[filename] = transformed(confined(target,filename).read_bytes(),record,filename)
        except (OSError,ValueError,UnicodeError) as error: errors.append(str(error))
    for filename, expected in manifest['requires'].items():
        p = confined(target,filename)
        if not p.is_file() or blob(p.read_bytes()) != expected: errors.append('Required selector version differs: '+filename)
    dest_manifest = confined(target,name)
    if dest_manifest.exists() and (not dest_manifest.is_file() or dest_manifest.read_bytes() != raw_manifest): errors.append('Conflicting existing manifest: '+name)
    if errors: raise SystemExit('\n'.join(errors)+'\nNo checkout files changed.')
    changes = [n for n,raw in payload.items() if not confined(target,n).exists() or confined(target,n).read_bytes() != raw]
    print(f'Preflight passed: {len(changes)} file(s) to install/update.')
    if not args.apply:
        print('Check only. Add --apply to write files.'); return
    if not changes:
        print('Already applied; no files changed.'); return
    backup = target/'.wapflix-patch-backups'/('5a5b-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(parents=True); existed, written = {}, []
    for n in changes:
        p = confined(target,n); existed[n] = p.exists()
        if existed[n]:
            saved = backup/n; saved.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,saved)
    (backup/'installed-files.json').write_text(json.dumps({'existed':existed},indent=2)+'\n')
    try:
        for n in changes:
            p = confined(target,n); p.parent.mkdir(parents=True,exist_ok=True)
            fd,temp = tempfile.mkstemp(prefix='.5a5b-',dir=p.parent)
            try:
                with os.fdopen(fd,'wb') as handle: handle.write(payload[n])
                os.chmod(temp,0o644); os.replace(temp,p); written.append(n)
            finally:
                if os.path.exists(temp): os.unlink(temp)
    except BaseException:
        for n in reversed(written):
            p = confined(target,n)
            if existed[n]: shutil.copy2(backup/n,p)
            else: p.unlink(missing_ok=True)
        raise
    print('Applied 5A.5B. Backup: '+str(backup))
    print('No commit, service restart, media/SRT changes or browser acceptance performed.')

if __name__ == '__main__': main()
