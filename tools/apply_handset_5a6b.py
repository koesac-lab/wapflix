#!/usr/bin/env python3
"""Guarded Wapflix 5A.6B installer. Dry-run by default. Standard library only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

MANIFEST = 'MANIFEST_5A6B.json'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def confined(root, name):
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or '..' in relative.parts:
        raise ValueError('Unsafe path: ' + name)
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Symlink refused: ' + str(path))
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path outside root: ' + name)
    return path

def read(path):
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError('Expected regular file: ' + str(path))
    return path.read_bytes()

def atomic(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.wapflix-5a6b-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def restore(root, backup, records):
    for record in reversed(records):
        target = confined(root, record['path'])
        if record['existed']:
            data = confined(backup / 'before', record['path']).read_bytes()
            if sha(data) != record['before_sha256']:
                raise ValueError('Damaged backup: ' + record['path'])
            atomic(target, data, record['mode'])
        elif target.exists():
            target.unlink()

def rollback(root, backup, apply):
    if not backup.is_relative_to(root / '.wapflix-patch-backups'):
        raise ValueError('Rollback must use this checkout\'s patch-backup directory')
    relative = str(backup.relative_to(root))
    backup = confined(root, relative)
    state = json.loads((backup / 'state.json').read_text())
    if state.get('patch') != '5A.6B' or state.get('root') != str(root):
        raise ValueError('Backup belongs to another patch or checkout')
    records = state['records']
    for record in records:
        current = read(confined(root, record['path']))
        digest = None if current is None else sha(current)
        if digest not in (record['after_sha256'], record['before_sha256']):
            raise ValueError('Refusing to overwrite edits since install: ' + record['path'])
        if record['existed']:
            original = confined(backup / 'before', record['path']).read_bytes()
            if sha(original) != record['before_sha256']:
                raise ValueError('Backup checksum mismatch: ' + record['path'])
        print('RESTORE', record['path'])
    if apply:
        restore(root, backup, records)
        print('Rollback complete. No Git commands were run.')
    else:
        print('Rollback dry-run passed; add --apply to restore.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if args.rollback:
        rollback(root, args.rollback.resolve(strict=True), args.apply)
        return
    package = Path(__file__).resolve().parents[1]
    manifest_bytes = (package / MANIFEST).read_bytes()
    manifest = json.loads(manifest_bytes)
    top = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], text=True).strip()
    if Path(top).resolve() != root:
        raise ValueError('--root must be the Git checkout root')
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if head != manifest['baseline_commit']:
        raise ValueError('HEAD differs from verified baseline: ' + head)
    for name, expected in manifest['dependencies'].items():
        data = read(confined(root, name))
        if data is None or blob(data) != expected:
            raise ValueError('Dependency baseline mismatch: ' + name)
    changes = []
    for name, record in manifest['files'].items():
        source = confined(package / 'payload', name)
        data = source.read_bytes()
        if sha(data) != record['sha256']:
            raise ValueError('Payload checksum mismatch: ' + name)
        changes.append((name, data, record['before_blob']))
    changes.append((MANIFEST, manifest_bytes, None))
    plan = []
    for name, data, expected in changes:
        target = confined(root, name)
        current = read(target)
        if current == data:
            print('ALREADY', name)
            continue
        if expected is None:
            if current is not None:
                raise ValueError('New-file collision: ' + name)
        elif current is None or blob(current) != expected:
            raise ValueError('Source baseline mismatch: ' + name)
        plan.append((name, data, current, target.stat().st_mode & 0o777 if current is not None else 0o644))
        print('WRITE', name)
    if not plan:
        print('Already installed; no changes.')
        return
    if not args.apply:
        print('Dry-run passed. No files written. Add --apply after stopping the preview.')
        return
    backup_name = '.wapflix-patch-backups/5a6b-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    backup = confined(root, backup_name)
    backup.mkdir(parents=True, exist_ok=False)
    records = []
    for name, data, current, mode in plan:
        if current is not None:
            saved = confined(backup / 'before', name)
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(current)
        records.append({'path': name, 'existed': current is not None, 'mode': mode,
            'before_sha256': None if current is None else sha(current), 'after_sha256': sha(data)})
    (backup / 'state.json').write_text(json.dumps({'patch':'5A.6B','root':str(root),'records':records}, indent=2) + '\n')
    written = []
    try:
        for (name, data, current, mode), record in zip(plan, records):
            target = confined(root, name)
            if read(target) != current:
                raise ValueError('File changed during installation: ' + name)
            atomic(target, data, mode)
            written.append(record)
    except Exception:
        restore(root, backup, written)
        raise
    print('Installed. Backup: ' + str(backup))
    print('No commit, push, server start, or deletion of old archives was performed.')

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        sys.exit(2)
