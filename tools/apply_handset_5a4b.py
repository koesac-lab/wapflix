#!/usr/bin/env python3
"""Apply staged 5A.4B over the locally tested 5A.4A bridge."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def confined(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name:
        raise ValueError('Unsafe path: ' + name)
    path = root / name
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError('Symlink refused: ' + name)
        cursor = cursor.parent
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes root: ' + name)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = args.root.expanduser().resolve()
    if target == source or not target.is_dir():
        parser.error('Extract to staging and specify an existing checkout root')
    manifest = json.loads((source/'MANIFEST_5A4B.json').read_text())
    errors, payload, changes = [], {}, []
    for name, digest in manifest['sha256'].items():
        data = confined(source, name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            errors.append('Package checksum mismatch: ' + name)
        payload[name] = data
        destination = confined(target, name)
        if destination.exists():
            if not destination.is_file():
                errors.append('Not a regular file: ' + name)
                continue
            old = destination.read_bytes()
            if old == data:
                continue
            expected = manifest['replaces'].get(name)
            if expected is None or blob(old) != expected:
                errors.append('Unexpected local version; refusing overwrite: ' + name)
        elif name in manifest['replaces']:
            errors.append('Missing 5A.4A baseline: ' + name)
        changes.append(name)
    for name, digest in manifest['requires'].items():
        item = confined(target, name)
        if not item.is_file() or blob(item.read_bytes()) != digest:
            errors.append('Required baseline differs: ' + name)
    for name in manifest['required_files']:
        if not confined(target, name).is_file():
            errors.append('Missing prerequisite: ' + name)
    if errors:
        raise SystemExit('\n'.join(errors) + '\nNo checkout files changed. Keep the applied 5A.4A files; do not reset to older main.')
    print(f'Preflight passed: {len(changes)} file(s) to install.')
    if not args.apply:
        print('Check only. Add --apply to write files.')
        return
    if not changes:
        print('Already applied; no files changed.')
        return
    backup = target/'.wapflix-patch-backups'/('5a4b-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(parents=True)
    existed, written = {}, []
    for name in changes:
        path = confined(target, name)
        existed[name] = path.exists()
        if existed[name]:
            saved = backup/name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
    (backup/'installed-files.json').write_text(json.dumps({'existed': existed}, indent=2)+'\n')
    try:
        for name in changes:
            path = confined(target, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix='.5a4b-', dir=path.parent)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(payload[name])
                os.chmod(temp, 0o644)
                os.replace(temp, path)
                written.append(name)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
    except BaseException:
        for name in reversed(written):
            path = confined(target, name)
            if existed[name]:
                shutil.copy2(backup/name, path)
            else:
                path.unlink(missing_ok=True)
        raise
    print('Applied 5A.4B. Backup: ' + str(backup))
    print('No commit, service restart or browser acceptance performed.')

if __name__ == '__main__':
    main()
