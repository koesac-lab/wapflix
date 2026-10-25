#!/usr/bin/env python3
"""Check/apply staged 5A.4C plus guarded visibility-expectation migrations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def confined(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name:
        raise ValueError('Unsafe path: ' + name)
    path = root/name
    cursor = path
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError('Symlink refused: ' + name)
        cursor = cursor.parent
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes root: ' + name)
    return path


def migrate(data, expected_sha, edits, name):
    text = data.decode()
    if sha(data) == expected_sha:
        for old, new in edits:
            if text.count(old) != 1:
                raise ValueError('Missing unique migration anchor: ' + name)
            text = text.replace(old, new, 1)
        return text.encode()
    reversed_text = text
    for old, new in reversed(edits):
        if reversed_text.count(new) != 1:
            raise ValueError('Unexpected local test version: ' + name)
        reversed_text = reversed_text.replace(new, old, 1)
    if sha(reversed_text.encode()) != expected_sha:
        raise ValueError('Unexpected local test edits: ' + name)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = args.root.expanduser().resolve()
    if source == target or not target.is_dir():
        parser.error('Extract separately and specify an existing checkout root')
    manifest_name = 'MANIFEST_5A4C.json'
    manifest_raw = (source/manifest_name).read_bytes()
    manifest = json.loads(manifest_raw)
    errors, payload = [], {}
    for name, digest in manifest['sha256'].items():
        data = confined(source, name).read_bytes()
        if sha(data) != digest:
            errors.append('Package checksum mismatch: ' + name)
        payload[name] = data
        destination = confined(target, name)
        if destination.exists():
            if not destination.is_file():
                errors.append('Not a regular file: ' + name)
                continue
            before = destination.read_bytes()
            if before == data:
                continue
            expected = manifest['replaces'].get(name)
            if expected is None or blob(before) != expected:
                errors.append('Unexpected local version; refusing overwrite: ' + name)
        elif name in manifest['replaces']:
            errors.append('Missing baseline: ' + name)
    for name, record in manifest['test_migrations'].items():
        try:
            previous = json.loads(confined(target, record['manifest']).read_text())
            expected = previous['sha256'][name]
            payload[name] = migrate(confined(target, name).read_bytes(), expected, record['edits'], name)
        except (OSError, ValueError, KeyError, UnicodeError) as error:
            errors.append('Cannot migrate ' + name + ': ' + str(error))
    for name in manifest['required_files']:
        if not confined(target, name).is_file():
            errors.append('Missing 5A.4B prerequisite: ' + name)
    installed_manifest = confined(target, manifest_name)
    if installed_manifest.exists() and (not installed_manifest.is_file() or installed_manifest.read_bytes() != manifest_raw):
        errors.append('Unexpected existing manifest: ' + manifest_name)
    payload[manifest_name] = manifest_raw
    if errors:
        raise SystemExit('\n'.join(errors) + '\nNo checkout files changed. Keep the successful local 5A.4A/5A.4B versions.')
    changes = [name for name, data in payload.items()
               if not confined(target, name).exists() or confined(target, name).read_bytes() != data]
    print(f'Preflight passed: {len(changes)} file(s) to install/update, including guarded test migrations.')
    if not args.apply:
        print('Check only. Add --apply to write files.')
        return
    if not changes:
        print('Already applied; no files changed.')
        return
    backup = target/'.wapflix-patch-backups'/('5a4c-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
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
            fd, temp = tempfile.mkstemp(prefix='.5a4c-', dir=path.parent)
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
    print('Applied 5A.4C. Backup: ' + str(backup))
    print('No Git action, service restart or real browser/server acceptance performed.')

if __name__ == '__main__':
    main()
