#!/usr/bin/env python3
"""Install additive 5A.5A caption-selection files; never replace existing code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    target = args.root.expanduser().resolve()
    if source == target or not target.is_dir():
        parser.error('Extract separately and specify the existing checkout root')
    name = 'MANIFEST_5A5A.json'
    raw_manifest = (source/name).read_bytes()
    manifest = json.loads(raw_manifest)
    errors, payload = [], {name: raw_manifest}
    for filename, expected in manifest['sha256'].items():
        data = confined(source, filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            errors.append('Package checksum mismatch: ' + filename)
        payload[filename] = data
    for filename in manifest['required_files']:
        if not confined(target, filename).is_file():
            errors.append('Missing lifecycle prerequisite: ' + filename)
    changes = []
    for filename, data in payload.items():
        path = confined(target, filename)
        if path.exists():
            if not path.is_file() or path.read_bytes() != data:
                errors.append('Refusing to replace existing local file: ' + filename)
        else:
            changes.append(filename)
    if errors:
        raise SystemExit('\n'.join(errors) + '\nNo checkout files changed.')
    print(f'Preflight passed: {len(changes)} new file(s); existing runtime untouched.')
    if not args.apply:
        print('Check only. Add --apply to install.')
        return
    if not changes:
        print('Already applied; no files changed.')
        return
    record = target/'.wapflix-patch-backups'/('5a5a-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    record.mkdir(parents=True)
    (record/'installed-files.json').write_text(json.dumps({'existed': {n:False for n in changes}}, indent=2)+'\n')
    written = []
    try:
        for filename in changes:
            path = confined(target, filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            written.append(path)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(payload[filename])
    except BaseException:
        for path in reversed(written):
            path.unlink(missing_ok=True)
        raise
    print('Installed 5A.5A additions. Rollback record: ' + str(record))
    print('No existing runtime changed; no captions displayed; no Git/service actions performed.')

if __name__ == '__main__':
    main()
