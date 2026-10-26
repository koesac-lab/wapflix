#!/usr/bin/env python3
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from tools.chunk_cache import PersistentChunkCache


class PersistentChunkCacheTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state', max_bytes=1024)
            identity = PersistentChunkCache.identity('video.mkv', 0, 60, 120, 54, 8)
            self.assertTrue(cache.put(identity, 0, gzip.compress(b'abc')))
            self.assertEqual(cache.get(identity, 0), b'abc')

    def test_identity_separates_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state')
            first = PersistentChunkCache.identity('a.mkv', 0, 60, 120, 54, 8)
            second = PersistentChunkCache.identity('b.mkv', 0, 60, 120, 54, 8)
            self.assertNotEqual(first, second)
            self.assertTrue(cache.put(first, 0, gzip.compress(b'first')))
            self.assertIsNone(cache.get(second, 0))

    def test_ceiling_evicts_oldest_unprotected_chunk(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state', max_bytes=10)
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            self.assertTrue(cache.put(identity, 0, gzip.compress(b'12345')))
            self.assertTrue(cache.put(identity, 1, gzip.compress(b'67890')))
            self.assertTrue(cache.put(identity, 2, gzip.compress(b'abcde')))
            self.assertIsNone(cache.get(identity, 0))
            self.assertEqual(cache.get(identity, 2), b'abcde')

    def test_active_window_is_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state', max_bytes=8)
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            self.assertTrue(cache.put(identity, 0, gzip.compress(b'12345')))
            self.assertFalse(cache.put(identity, 1, gzip.compress(b'67890'), protected_indices={0}))
            self.assertEqual(cache.get(identity, 0), b'12345')

    def test_oversized_chunk_is_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state', max_bytes=4)
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            self.assertFalse(cache.put(identity, 0, gzip.compress(b'12345')))
            self.assertIsNone(cache.get(identity, 0))

    def test_missing_chunk_returns_none(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state')
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            self.assertIsNone(cache.get(identity, 99))

    def test_state_file_records_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'cache'
            state = Path(directory) / 'state'
            cache = PersistentChunkCache(root, state, max_bytes=100)
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            cache.put(identity, 0, gzip.compress(b'12345'))
            recorded = json.loads((state / 'cache-state.json').read_text())
            self.assertEqual(recorded['total_bytes'], 5)
            self.assertEqual(recorded['max_bytes'], 100)

    def test_corrupt_chunk_is_quarantined(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'cache'
            state = Path(directory) / 'state'
            cache = PersistentChunkCache(root, state)
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            path = root / identity / 'chunk-000000.json.gz'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'not gzip')
            self.assertIsNone(cache.get(identity, 0))
            self.assertFalse(path.exists())
            self.assertTrue(any(cache.quarantine.iterdir()))

    def test_startup_removes_abandoned_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'cache'
            state = Path(directory) / 'state'
            root.mkdir()
            temporary = root / 'identity' / '.chunk-abc.tmp'
            temporary.parent.mkdir()
            temporary.write_bytes(b'partial')
            PersistentChunkCache(root, state)
            self.assertFalse(temporary.exists())

    def test_startup_counts_orphan_published_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'cache'
            state = Path(directory) / 'state'
            identity = 'a' * 24
            path = root / identity / 'chunk-000000.json.gz'
            path.parent.mkdir(parents=True)
            path.write_bytes(gzip.compress(b'orphan'))
            cache = PersistentChunkCache(root, state)
            self.assertEqual(cache.stats()['total_bytes'], len(path.read_bytes()))


if __name__ == '__main__':
    unittest.main()
