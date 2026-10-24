"""R2B.3 generated-media integration tests, no downloaded/private media."""
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from tools import lcd_stream_server as base
from tools.lcd_m4_factory import FixedSource, M4Factory
from tools.start_coordinator import StartCoordinator
from tools.start_fence import FenceError

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and ffprobe required')
class RealFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.video = Path(cls.directory.name) / 'generated.mkv'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=64x48:rate=8', '-t', '60', '-an', '-c:v', 'ffv1',
            '-threads', '1', str(cls.video)], check=True, timeout=30)
        cls.subtitle = Path(cls.directory.name) / 'generated.srt'
        cls.subtitle.write_text('1\n00:00:00,000 --> 00:00:02,000\nFIRST\n\n2\n00:00:02,000 --> 00:00:04,000\nSECOND\n')

    def setUp(self):
        self.spec = FixedSource(self.video, start=.5, seconds=40, delay=.02)
        self.factory = M4Factory(self.spec, subtitles=self.subtitle)
        self.coordinator = StartCoordinator(self.factory)
        self.addCleanup(self.coordinator.close)
        self.client = self.coordinator.fence.open_client()
        self.created = []
        original = self.factory.prepare
        def track(spec, ticket):
            candidate = original(spec, ticket)
            self.created.append(candidate)
            return candidate
        self.factory.prepare = track

    def start(self, revision=1):
        return self.coordinator.start(self.client, revision, self.spec)

    def wait_for(self, predicate, seconds=8):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.01)
        self.fail('Timed out waiting for generated-media condition')

    def chunk(self, session):
        with session.lock:
            return session.chunks.get(0)

    def test_prepare_probes_once_without_converter_or_thread(self):
        ticket = self.coordinator.fence.request(self.client, 1)
        with patch.object(base, 'LCDStream', wraps=base.LCDStream) as stream:
            candidate = self.factory.prepare(self.spec, ticket)
            self.assertEqual(stream.call_count, 1)
        self.assertIsNone(candidate.session.stream.process)
        self.assertIsNone(candidate.session.thread.ident)
        self.assertTrue(candidate.stop())

    def test_real_chunk_and_metadata_and_duplicate(self):
        metadata = self.start()
        session = self.created[0].session
        self.wait_for(lambda: self.chunk(session) is not None)
        chunk = json.loads(gzip.decompress(self.chunk(session)))
        self.assertEqual(chunk['layout'], 'lcd-1bit')
        self.assertEqual(chunk['source_start'], .5)
        self.assertEqual(chunk['fps'], 8)
        self.assertGreater(len(chunk['frames']), 0)
        self.assertEqual(len(bytes.fromhex(chunk['frames'][0])), chunk['cols']*chunk['rows']//8)
        self.assertEqual(metadata['range_start'], .5)
        self.assertEqual(metadata['range_end'], 40.5)
        self.assertEqual(metadata['revision'], 0)
        self.assertEqual(metadata['start_revision'], 1)
        self.assertEqual(metadata['captions']['timebase'], 'source')
        self.assertEqual(metadata['captions']['cues'][0]['start'], .5)
        again = self.start()
        self.assertEqual(again['id'], metadata['id'])
        self.assertEqual(again['navigation_id'], metadata['navigation_id'])
        self.assertEqual(len(self.created), 1)
        pulse = session.pulse(0, True)
        for key in ('ready_frames', 'total_frames', 'generated_chunks', 'retained_chunks', 'worker_running'):
            self.assertIn(key, pulse)

    def test_cancel_after_real_preparation_never_launches_converter(self):
        prepared, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = self.factory.prepare
        def blocked(spec, ticket):
            candidate = original(spec, ticket)
            prepared.set()
            if not release.wait(5):
                raise TimeoutError('test preparation barrier')
            return candidate
        self.factory.prepare = blocked
        errors = []
        def run():
            try:
                self.start()
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        try:
            self.assertTrue(prepared.wait(5))
            self.coordinator.cancel(self.client, 1)
        finally:
            release.set()
            thread.join(6)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], FenceError)
        self.assertEqual(errors[0].code, 'cancelled_start')
        candidate = self.created[0]
        self.assertIsNone(candidate.session.stream.process)
        self.assertIsNone(candidate.session.thread.ident)

    def test_replacement_reaps_real_worker_before_next_publish(self):
        self.start()
        old = self.created[0]
        self.wait_for(lambda: self.chunk(old.session) is not None)
        self.assertIsNotNone(old.session.stream.process)
        self.assertIsNone(old.session.stream.process.poll(), 'Old converter must be running for this replacement test')
        original = self.factory.prepare
        def prepare(spec, ticket):
            candidate = original(spec, ticket)
            publish = candidate.publish
            def checked(owner):
                self.assertFalse(old.session.thread.is_alive())
                self.assertIsNotNone(old.session.stream.process.poll())
                publish(owner)
            candidate.publish = checked
            return candidate
        self.factory.prepare = prepare
        fresh = self.start(2)
        self.assertNotEqual(fresh['id'], old.session.id)
        self.assertTrue(old.session.stop_event.is_set())
        self.wait_for(lambda: self.chunk(self.created[-1].session) is not None)

    def test_real_cancel_reaps_process_and_releases_owner(self):
        self.start()
        session = self.created[0].session
        self.wait_for(lambda: self.chunk(session) is not None)
        self.assertEqual(self.coordinator.cancel(self.client, 1)['cleanup'], 'confirmed')
        self.assertFalse(session.thread.is_alive())
        self.assertIsNotNone(session.stream.process.poll())
        self.assertIsNone(self.coordinator.fence.snapshot()['active_owner'])

    def test_fixed_source_rejects_request_override(self):
        other = FixedSource(self.video, start=2, seconds=2)
        with self.assertRaises(ValueError):
            self.coordinator.start(self.client, 1, other)
        self.assertEqual(self.created, [])

    def test_invalid_source_probe_failure_leaves_no_owner(self):
        bad = M4Factory(FixedSource(self.video.with_name('missing.mkv')), no_srt=True)
        coordinator = StartCoordinator(bad)
        self.addCleanup(coordinator.close)
        client = coordinator.fence.open_client()
        with self.assertRaises(ValueError):
            coordinator.start(client, 1, bad.spec)
        self.assertIsNone(coordinator.fence.snapshot()['active_owner'])

    def test_completed_tail_retains_navigation_until_explicit_stop(self):
        factory = M4Factory(FixedSource(self.video, start=.5, seconds=1.25), no_srt=True)
        coordinator = StartCoordinator(factory)
        self.addCleanup(coordinator.close)
        client = coordinator.fence.open_client()
        candidates = []
        original = factory.prepare
        def track(spec, ticket):
            candidate = original(spec, ticket)
            candidates.append(candidate)
            return candidate
        factory.prepare = track
        metadata = coordinator.start(client, 1, factory.spec)
        session = candidates[0].session
        self.wait_for(lambda: session.snapshot()['state'] == 'complete')
        self.assertGreater(session.snapshot()['total_frames'], 0)
        self.assertLess(session.snapshot()['total_frames'], 16)
        self.assertIsNotNone(coordinator.fence.snapshot()['active_owner'])
        again = coordinator.start(client, 1, factory.spec)
        self.assertEqual(again['navigation_id'], metadata['navigation_id'])
        self.assertFalse(again['captions']['track_found'])
        coordinator.cancel(client, 1)
        self.assertIsNone(coordinator.fence.snapshot()['active_owner'])

class ConfigTests(unittest.TestCase):
    def test_invalid_configuration(self):
        for kwargs in ({'start': True}, {'seconds': 0}, {'seconds': 121}, {'delay': 6}, {'start': float('nan')}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                FixedSource('unused.mkv', **kwargs)

if __name__ == '__main__':
    unittest.main()
