#!/usr/bin/env python3
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
            self.assertTrue(cache.put(identity, 0, b'abc'))
            self.assertEqual(cache.get(identity, 0), b'abc')

    def test_identity_separates_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state')
            first = PersistentChunkCache.identity('a.mkv', 0, 60, 120, 54, 8)
            second = PersistentChunkCache.identity('b.mkv', 0, 60, 120, 54, 8)
            self.assertNotEqual(first, second)
            self.assertTrue(cache.put(first, 0, b'first'))
            self.assertIsNone(cache.get(second, 0))

    def test_ceiling_evicts_oldest_unprotected_chunk(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state', max_bytes=10)
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            self.assertTrue(cache.put(identity, 0, b'12345'))
            self.assertTrue(cache.put(identity, 1, b'67890'))
            self.assertTrue(cache.put(identity, 2, b'abcde'))
            self.assertIsNone(cache.get(identity, 0))
            self.assertEqual(cache.get(identity, 2), b'abcde')

    def test_active_window_is_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state', max_bytes=10)
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            self.assertTrue(cache.put(identity, 0, b'12345'))
            self.assertFalse(cache.put(identity, 1, b'67890', protected_indices={0}))
            self.assertEqual(cache.get(identity, 0), b'12345')

    def test_oversized_chunk_is_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = PersistentChunkCache(Path(directory) / 'cache', Path(directory) / 'state', max_bytes=4)
            identity = cache.identity('video.mkv', 0, 60, 120, 54, 8)
            self.assertFalse(cache.put(identity, 0, b'12345'))
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
            cache.put(identity, 0, b'12345')
            recorded = json.loads((state / 'cache-state.json').read_text())
            self.assertEqual(recorded['total_bytes'], 5)
            self.assertEqual(recorded['max_bytes'], 100)


if __name__ == '__main__':
    unittest.main()
