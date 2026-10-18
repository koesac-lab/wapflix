#!/usr/bin/env python3
"""Validate all files before adding them to a WAPFLIX checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ALLOWED = {"tools/diagnose.py", "tools/srt.py", "tests/test_diagnose.py", "tests/test_srt.py", "docs/BENCHMARKING.md"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    bundle = Path(__file__).resolve().parent
    if not (root/'index.html').is_file() or not (root/'tools/build.py').is_file():
        raise ValueError("run from the WAPFLIX checkout root, or use --root")
    manifest = json.loads((bundle/'MANIFEST.json').read_text())
    if set(manifest) != ALLOWED:
        raise ValueError("unexpected manifest file list")
    pending, errors, unchanged = [], [], []
    for relative, digest in sorted(manifest.items()):
        source = bundle/'payload'/relative
        if not source.is_file() or source.is_symlink():
            errors.append(f"missing/unsafe payload: {relative}")
            continue
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            errors.append(f"checksum mismatch: {relative}")
            continue
        target = root/relative
        chain = [target, *target.parents]
        if any(path.is_symlink() for path in chain if path != root and root in path.parents):
            errors.append(f"symlink target/parent refused: {relative}")
        elif target.exists():
            if target.is_file() and target.read_bytes() == data:
                unchanged.append(relative)
            else:
                errors.append(f"existing differing file; not overwritten: {relative}")
        elif target.parent.exists() and not target.parent.is_dir():
            errors.append(f"parent is not a directory: {relative}")
        else:
            pending.append((target, data))
    if errors:
        raise ValueError('\n'.join(errors))
    for target, _ in pending:
        print(f"{'ADD' if args.apply else 'WOULD ADD'} {target.relative_to(root)}")
    for relative in unchanged:
        print(f"UNCHANGED {relative}")
    if args.apply:
        for target, data in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(data)
        print(f"Applied {len(pending)} files; {len(unchanged)} already identical.")
    else:
        print("Check passed. No checkout files changed. Use --apply to install.")

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        raise SystemExit(2)
