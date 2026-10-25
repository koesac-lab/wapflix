#!/usr/bin/env python3
"""Bounded, identity-scoped persistent cache for generated LCD chunks."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path


class PersistentChunkCache:
    """Persist gzip-packed chunks beneath root, bounded by max_bytes."""

    def __init__(self, root, state_root, max_bytes=32 * 1024 * 1024):
        self.root = Path(root)
        self.state_root = Path(state_root)
        self.max_bytes = int(max_bytes)
        if self.max_bytes < 0:
            raise ValueError('Cache ceiling must be non-negative')
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._total = self._scan()
        self._write_state()

    def _scan(self):
        total = 0
        for path in self.root.rglob('chunk-*.json.gz'):
            try:
                total += path.stat().st_size
            except OSError:
                pass
        return total

    @staticmethod
    def identity(video, start, seconds, cols, rows, fps):
        payload = json.dumps(
            [str(Path(video).expanduser().resolve()), start, seconds, cols, rows, fps],
            sort_keys=True,
            separators=(',', ':'),
        ).encode()
        return hashlib.sha256(payload).hexdigest()[:24]

    def _stream_dir(self, identity):
        if not identity or not identity.isalnum() or len(identity) != 24:
            raise ValueError('Invalid cache identity')
        return self.root / identity

    @staticmethod
    def _chunk_path(stream_dir, index):
        return stream_dir / f'chunk-{int(index):06}.json.gz'

    def _write_state(self):
        entries = sum(1 for _ in self.root.rglob('chunk-*.json.gz'))
        state = {
            'version': 1,
            'max_bytes': self.max_bytes,
            'total_bytes': self._total,
            'entries': entries,
            'updated_at': time.time(),
        }
        path = self.state_root / 'cache-state.json'
        fd, temporary = tempfile.mkstemp(dir=self.state_root, prefix='.cache-state-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(json.dumps(state, sort_keys=True, separators=(',', ':')).encode())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _entries(self):
        entries = []
        for path in self.root.rglob('chunk-*.json.gz'):
            try:
                relative = path.relative_to(self.root)
                identity = relative.parts[0]
                index = int(path.name.split('-')[1].split('.')[0])
                stat = path.stat()
                entries.append((stat.st_mtime, stat.st_size, identity, index, path))
            except (OSError, ValueError, IndexError):
                continue
        entries.sort(key=lambda item: (item[0], item[4].as_posix()))
        return entries

    def put(self, identity, index, data, protected_indices=frozenset()):
        if self.max_bytes <= 0 or not isinstance(data, (bytes, bytearray)):
            return False
        data = bytes(data)
        if len(data) > self.max_bytes:
            return False
        stream_dir = self._stream_dir(identity)
        target = self._chunk_path(stream_dir, index)
        protected = {int(value) for value in protected_indices}
        with self._lock:
            try:
                existing = target.stat().st_size if target.exists() else 0
            except OSError:
                existing = 0
            projected = self._total - existing + len(data)
            if projected > self.max_bytes:
                for _, size, entry_identity, entry_index, path in self._entries():
                    if projected <= self.max_bytes:
                        break
                    if path == target:
                        continue
                    if entry_identity == identity and entry_index in protected:
                        continue
                    try:
                        path.unlink()
                        self._total -= size
                        projected -= size
                    except OSError:
                        continue
            if projected > self.max_bytes:
                return False
            try:
                stream_dir.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(dir=stream_dir, prefix='.chunk-', suffix='.tmp')
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(data)
                os.replace(temporary, target)
                self._total = projected
            except OSError:
                return False
            self._write_state()
            return True

    def get(self, identity, index):
        try:
            path = self._chunk_path(self._stream_dir(identity), index)
            return path.read_bytes()
        except (OSError, ValueError):
            return None

    def stats(self):
        with self._lock:
            return {'max_bytes': self.max_bytes, 'total_bytes': self._total}
