#!/usr/bin/env python3
"""Apply the staged 5A.3B package to a compatible Wapflix checkout."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import os


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def confined(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name:
        raise ValueError('Unsafe package path: ' + name)
    path = root / name
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError('Symlink path refused: ' + name)
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes root: ' + name)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Wapflix checkout root')
    parser.add_argument('--apply', action='store_true', help='Write files after successful preflight; default checks only')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = args.root.expanduser().resolve()
    if target == source:
        parser.error('Extract to a separate staging directory, not the checkout itself')
    manifest = json.loads((source / 'MANIFEST_5A3B.json').read_text())
    errors, payload, changes = [], {}, []
    for name, expected in manifest['sha256'].items():
        item = confined(source, name)
        data = item.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
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
            baseline = manifest['replaces'].get(name)
            if baseline is None or blob(old) != baseline:
                errors.append('Unexpected local version; refusing overwrite: ' + name)
        elif name in manifest['replaces']:
            errors.append('Missing baseline file: ' + name)
        changes.append(name)
    for name, expected in manifest['requires'].items():
        item = confined(target, name)
        if not item.is_file() or blob(item.read_bytes()) != expected:
            errors.append('Required baseline differs or is missing: ' + name)
    for name in manifest['required_files']:
        if not confined(target, name).is_file():
            errors.append('Missing fenced-stack prerequisite: ' + name)
    if errors:
        raise SystemExit('\n'.join(errors) + '\nNo checkout files changed. Reconcile differences before applying.')
    print('Preflight passed: ' + str(len(changes)) + ' file(s) to install; ' + str(len(payload)-len(changes)) + ' already current.')
    if not args.apply:
        print('Check only. Add --apply to install.')
        return
    if not changes:
        print('Already applied; no files changed.')
        return
    backup = target / '.wapflix-patch-backups' / ('5a3b-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(parents=True)
    existed, written = {}, []
    for name in changes:
        destination = confined(target, name)
        existed[name] = destination.exists()
        if existed[name]:
            saved = backup / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved)
    (backup / 'installed-files.json').write_text(json.dumps({'existed': existed}, indent=2) + '\n')
    try:
        for name in changes:
            destination = confined(target, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix='.5a3b-', dir=destination.parent)
            try:
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(payload[name])
                os.chmod(temp, 0o644)
                os.replace(temp, destination)
                written.append(name)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
    except BaseException:
        for name in reversed(written):
            destination = confined(target, name)
            if existed[name]:
                shutil.copy2(backup / name, destination)
            else:
                destination.unlink(missing_ok=True)
        raise
    print('Applied 5A.3B. Backup: ' + str(backup))
    print('No git commit, service restart, media conversion or browser acceptance was performed.')

if __name__ == '__main__':
    main()
