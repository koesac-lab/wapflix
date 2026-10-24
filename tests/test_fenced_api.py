"""R2B.4 real loopback HTTP/FFmpeg gate. No private media required."""
import gzip
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from tools import lcd_stream_fenced_api as api
from tools.start_fence import FenceError, AdmissionFailed

class FenceExtensionTests(unittest.TestCase):
    def setUp(self):
        self.fence = api.NavigationFence()
        self.client = self.fence.open_client()
        self.ticket = self.fence.request(self.client, 1)
        self.owner = self.fence.admit(self.ticket, lambda owner: None)
    def test_update_keeps_owner(self):
        seen = []
        self.fence.update_owner(self.ticket, self.owner, seen.append)
        self.assertEqual(seen, [self.owner])
        self.assertEqual(self.fence.snapshot()['active_owner'], self.owner)
    def test_cancel_blocks_update(self):
        self.fence.cancel(self.client, 1)
        with self.assertRaises(FenceError):
            self.fence.update_owner(self.ticket, self.owner, lambda owner: self.fail('published'))
    def test_newer_intent_blocks_update(self):
        self.fence.request(self.client, 2)
        with self.assertRaises(FenceError):
            self.fence.update_owner(self.ticket, self.owner, lambda owner: self.fail('published'))
    def test_failed_update_retains_owner(self):
        def fail(owner):
            raise RuntimeError('partial publication')
        with self.assertRaises(AdmissionFailed):
            self.fence.update_owner(self.ticket, self.owner, fail)
        self.assertEqual(self.fence.snapshot()['active_owner'], self.owner)
        self.assertEqual(self.fence.cancel(self.client, 1), self.owner)
    def test_foreign_owner_rejected(self):
        with self.assertRaises(FenceError):
            self.fence.update_owner(self.ticket, 'wrong', lambda owner: self.fail('published'))

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and ffprobe required')
class FencedHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.video = Path(cls.temp.name) / 'generated.mkv'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=64x48:rate=8', '-t', '60', '-an', '-c:v', 'ffv1',
            '-threads', '1', str(cls.video)], check=True, timeout=30)
        cls.srt = Path(cls.temp.name) / 'generated.srt'
        cls.srt.write_text('1\n00:00:00,000 --> 00:00:03,000\nFIRST\n\n2\n00:00:03,000 --> 00:00:09,000\nSECOND\n')
    def setUp(self):
        self.app = api.FencedApp(api.FixedSource(self.video, .5, 40, .01),
                                 subtitles=self.srt, monitor=False)
        self.server = api.base.Server(('127.0.0.1', 0), api.make_handler(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.shutdown)
    def shutdown(self):
        self.server.shutdown()
        self.thread.join(2)
        self.app.close()
        self.server.server_close()
    def request(self, method, path, body=None, *, auth=True, headers=None, raw=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=40)
        supplied = {}
        if auth:
            supplied['X-Wapflix-Test'] = self.app.token
        supplied.update(headers or {})
        data = None if method == 'GET' else (json.dumps(body if body is not None else {}) if raw is None else raw)
        try:
            conn.request(method, path, body=data, headers=supplied)
            response = conn.getresponse()
            payload = response.read()
            if response.getheader('Content-Encoding') == 'gzip':
                payload = gzip.decompress(payload)
            if payload and 'application/json' in response.getheader('Content-Type', ''):
                payload = json.loads(payload)
            return response.status, payload, dict(response.getheaders())
        finally:
            conn.close()
    def post(self, path, body=None, **kwargs):
        return self.request('POST', path, body, **kwargs)
    def open(self):
        status, body, _ = self.post('/api/control/open')
        self.assertEqual(status, 200)
        self.assertEqual(body['control_protocol'], 'start-fence-v1')
        return body['control_client_id']
    def start(self, client=None, revision=1):
        client = self.open() if client is None else client
        status, body, _ = self.post('/api/start', {'control_client_id': client, 'start_revision': revision})
        self.assertEqual(status, 200, body)
        return client, body
    def wait_for(self, predicate, seconds=8):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.01)
        self.fail('Timed out waiting for media condition')
    def background(self, callback):
        results = []
        def run():
            try:
                results.append(callback())
            except BaseException as error:
                results.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        return thread, results
    def finish(self, release, thread, results):
        release.set()
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 1)
        if isinstance(results[0], BaseException):
            raise results[0]
        return results[0]

    def test_auth_origin_host_and_missing_identity(self):
        self.assertEqual(self.post('/api/control/open', auth=False)[0], 403)
        self.assertEqual(self.post('/api/control/open', headers={'Host':'evil.example'})[0], 403)
        self.assertEqual(self.post('/api/control/open', headers={'Origin':'http://evil.example'})[0], 403)
        status, result, _ = self.post('/api/start')
        self.assertEqual((status, result['code']), (409, 'fencing_required'))
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])
        self.assertEqual(self.post('/api/start', {'video':'bad'})[0], 400)

    def test_control_bounds_unknown_and_capacity(self):
        client = self.open()
        for revision in (True, -1, 2**53, '1'):
            self.assertEqual(self.post('/api/control/cancel', {'control_client_id':client, 'cancel_through':revision})[0], 400)
        self.assertEqual(self.post('/api/control/cancel', {'control_client_id':'a'*48, 'cancel_through':1})[0], 404)
        for _ in range(31): self.open()
        self.assertEqual(self.post('/api/control/open')[0], 429)
        for raw in ('[]', '{', ' '*4097):
            self.assertEqual(self.post('/api/control/open', raw=raw)[0], 400)

    def test_cancel_before_request_and_cancelled_retry(self):
        client = self.open()
        self.assertEqual(self.post('/api/control/cancel', {'control_client_id':client, 'cancel_through':1})[0], 200)
        status, body, _ = self.post('/api/start', {'control_client_id':client, 'start_revision':1})
        self.assertEqual((status, body['code']), (409, 'cancelled_start'))
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])
        self.start(client, 2)

    def test_chunks_pulse_and_duplicate(self):
        client, meta = self.start()
        def chunk():
            result = self.request('GET', '/api/chunk?id='+meta['id']+'&n=0')
            return result if result[0] == 200 else None
        status, data, headers = self.wait_for(chunk)
        self.assertEqual(headers['Content-Encoding'], 'gzip')
        self.assertEqual(data['layout'], 'lcd-1bit')
        self.assertEqual(data['source_start'], .5)
        self.assertGreater(len(data['frames']), 0)
        self.assertEqual(self.request('GET', '/api/chunk?id='+meta['id']+'&n=0&n=1')[0], 400)
        again = self.start(client, 1)[1]
        self.assertEqual(again['id'], meta['id'])
        pulse = self.post('/api/pulse', {'id':meta['id'], 'frame':0, 'paused':True})
        self.assertEqual(pulse[0], 200)
        for key in ('id','state','error','cols','rows','fps','chunk_frames','source_start',
                    'generated_chunks','ready_frames','total_frames','retained_chunks','first_chunk_seconds','worker_running'):
            self.assertIn(key, pulse[1])
        self.assertEqual(self.post('/api/pulse', {'frame':0})[0], 400)

    def test_seek_preserves_owner_range_and_start_identity(self):
        client, meta = self.start()
        owner = self.app.fence.snapshot()['active_owner']
        old = self.app._owner.candidate.session
        status, result, _ = self.post('/api/seek', {'navigation_id':meta['navigation_id'], 'revision':1, 'position':5.19})
        self.assertEqual(status, 200, result)
        self.assertEqual(result['source_start'], 5.125)
        self.assertEqual(result['navigation_id'], meta['navigation_id'])
        self.assertNotEqual(result['id'], meta['id'])
        self.assertEqual(result['range_start'], .5)
        self.assertEqual(result['range_end'], 40.5)
        self.assertEqual(result['revision'], 1)
        self.assertEqual(result['start_revision'], 1)
        self.assertEqual(result['captions']['cues'][0]['start'], 5.125)
        self.assertEqual(self.app.fence.snapshot()['active_owner'], owner)
        self.assertFalse(old.thread.is_alive())
        again = self.start(client, 1)[1]
        self.assertEqual(again['id'], result['id'])
        self.assertEqual(self.post('/api/pulse', {'id':meta['id']})[0], 404)
        self.assertEqual(self.post('/api/seek', {'navigation_id':meta['navigation_id'], 'revision':1, 'position':2})[0], 409)

    def test_session_stop_and_stale_stop_protection(self):
        client, first = self.start()
        _, fresh = self.start(client, 2)
        self.assertEqual(self.post('/api/stop', {'id':first['id']})[0], 404)
        status, result, _ = self.post('/api/navigation/stop', {'navigation_id':first['navigation_id']})
        self.assertEqual((status, result['superseded']), (200, True))
        self.assertEqual(self.post('/api/stop', {'id':fresh['id']})[0], 200)
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])

    def test_cleanup_failure_is_truthful_and_retryable(self):
        client, meta = self.start()
        candidate = self.app._owner.candidate
        with patch.object(candidate, 'stop', return_value=False):
            status, body, _ = self.post('/api/control/cancel', {'control_client_id':client, 'cancel_through':1})
            self.assertEqual(status, 503)
            self.assertEqual(body['code'], 'cleanup_unconfirmed')
            self.assertTrue(body['fence_recorded'])
            self.assertEqual(body['cleanup'], 'unconfirmed')
            self.assertIsNotNone(self.app.fence.snapshot()['active_owner'])
        self.assertEqual(self.post('/api/control/cancel', {'control_client_id':client, 'cancel_through':1})[0], 200)
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])

    def test_playback_expiry_and_only_matching_pulse_renews(self):
        _, meta = self.start()
        session = self.app._owner.candidate.session
        with session.lock: session.heartbeat = time.monotonic()-16
        self.assertEqual(self.post('/api/pulse', {'id':'wrong'})[0], 404)
        self.assertTrue(self.app.reap_once())
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])
        self.assertFalse(session.thread.is_alive())
        self.assertEqual(self.post('/api/pulse', {'id':meta['id']})[0], 409)

    def test_expired_active_control_handle_can_cancel(self):
        clock = [0.0]
        self.app.fence._clock = lambda: clock[0]
        client, _ = self.start()
        clock[0] = 61
        self.assertEqual(self.post('/api/control/cancel', {'control_client_id':client, 'cancel_through':1})[0], 200)
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])

    def test_cancel_before_start_ack_real_http(self):
        client = self.open()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = self.app.factory.prepare
        candidates = []
        def prepare(spec, ticket):
            candidate = original(spec, ticket)
            candidates.append(candidate)
            entered.set()
            if not release.wait(8): raise TimeoutError('test barrier')
            return candidate
        with patch.object(self.app.factory, 'prepare', side_effect=prepare):
            thread, results = self.background(lambda: self.post('/api/start', {'control_client_id':client,'start_revision':1}))
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.post('/api/control/cancel', {'control_client_id':client,'cancel_through':1})[0], 200)
            finally:
                answer = self.finish(release, thread, results)
        self.assertEqual(answer[0], 409)
        self.assertIsNone(candidates[0].session.stream.process)
        self.assertIsNone(candidates[0].session.thread.ident)

    def test_late_old_start_after_newer_acceptance(self):
        client = self.open()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = self.app.factory.prepare
        def prepare(spec, ticket):
            candidate = original(spec, ticket)
            if ticket.revision == 1:
                entered.set()
                if not release.wait(8): raise TimeoutError('test barrier')
            return candidate
        with patch.object(self.app.factory, 'prepare', side_effect=prepare):
            thread, results = self.background(lambda: self.post('/api/start', {'control_client_id':client,'start_revision':1}))
            try:
                self.assertTrue(entered.wait(5))
                _, fresh = self.start(client, 2)
            finally:
                answer = self.finish(release, thread, results)
        self.assertEqual(answer[0], 409)
        self.assertEqual(self.app._owner.candidate.session.id, fresh['id'])

    def test_stop_during_seek_preparation(self):
        _, meta = self.start()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = api.base.Session
        sessions = []
        def prepare(spec):
            session = original(spec)
            sessions.append(session)
            entered.set()
            if not release.wait(8): raise TimeoutError('test barrier')
            return session
        with patch.object(api.base, 'Session', side_effect=prepare):
            thread, results = self.background(lambda: self.post('/api/seek', {'navigation_id':meta['navigation_id'],'revision':1,'position':3}))
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.post('/api/navigation/stop', {'navigation_id':meta['navigation_id']})[0], 200)
            finally:
                answer = self.finish(release, thread, results)
        self.assertEqual(answer[0], 409)
        self.assertIsNone(sessions[0].stream.process)
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])

    def test_newest_seek_wins(self):
        _, meta = self.start()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = api.base.Session
        def prepare(spec):
            session = original(spec)
            if spec.start == 2:
                entered.set()
                if not release.wait(8): raise TimeoutError('test barrier')
            return session
        with patch.object(api.base, 'Session', side_effect=prepare):
            thread, results = self.background(lambda: self.post('/api/seek', {'navigation_id':meta['navigation_id'],'revision':1,'position':2}))
            try:
                self.assertTrue(entered.wait(5))
                status, fresh, _ = self.post('/api/seek', {'navigation_id':meta['navigation_id'],'revision':2,'position':5})
                self.assertEqual(status, 200, fresh)
            finally:
                answer = self.finish(release, thread, results)
        self.assertEqual(answer[0], 409)
        self.assertEqual(self.app._owner.candidate.session.id, fresh['id'])

    def test_legacy_real_fallback_is_separate(self):
        from tools.lcd_stream_seek_api import SeekApp
        legacy = SeekApp(self.video, .5, 2, no_srt=True)
        self.addCleanup(legacy.close)
        result = legacy.begin()
        self.assertIn('navigation_id', result)
        self.assertNotIn('control_client_id', result)
        self.wait_for(lambda: legacy.current.snapshot()['ready_frames'] > 0)
        self.assertEqual(self.post('/api/start')[1]['code'], 'fencing_required')

    def test_shutdown_fences_pending_start(self):
        client = self.open()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = self.app.factory.prepare
        def prepare(spec, ticket):
            candidate = original(spec, ticket)
            entered.set()
            if not release.wait(8): raise TimeoutError('test barrier')
            return candidate
        with patch.object(self.app.factory, 'prepare', side_effect=prepare):
            thread, results = self.background(lambda: self.post('/api/start', {'control_client_id':client,'start_revision':1}))
            try:
                self.assertTrue(entered.wait(5))
                self.app.close()
            finally:
                answer = self.finish(release, thread, results)
        self.assertEqual(answer[0], 409)
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])

    def test_replacement_cleanup_failure_never_publishes_new_worker(self):
        client, meta = self.start()
        candidate = self.app._owner.candidate
        owner = self.app.fence.snapshot()['active_owner']
        with patch.object(candidate, 'stop', return_value=False):
            status, result, _ = self.post('/api/start', {'control_client_id':client,'start_revision':2})
            self.assertEqual((status, result['code']), (503, 'cleanup_unconfirmed'))
            self.assertEqual(self.app.fence.snapshot()['active_owner'], owner)
            self.assertEqual(self.app._owner.candidate.session.id, meta['id'])
        self.assertEqual(self.post('/api/control/cancel', {'control_client_id':client,'cancel_through':2})[0], 200)

    def test_seek_partial_publish_retains_owner_until_cancel(self):
        client, meta = self.start()
        owner = self.app.fence.snapshot()['active_owner']
        with patch.object(api.NavigationCandidate, 'publish', side_effect=RuntimeError('partial publish')):
            status, result, _ = self.post('/api/seek', {'navigation_id':meta['navigation_id'],'revision':1,'position':3})
        self.assertEqual((status, result['code']), (503, 'admission_failed_cleanup_required'))
        self.assertEqual(self.app.fence.snapshot()['active_owner'], owner)
        self.assertEqual(self.post('/api/control/cancel', {'control_client_id':client,'cancel_through':1})[0], 200)
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])

    def test_source_failure_is_sanitized_and_does_not_reserve_owner(self):
        client = self.open()
        with patch.object(self.app.factory, 'prepare', side_effect=RuntimeError('/private/source token=secret')):
            status, result, _ = self.post('/api/start', {'control_client_id':client,'start_revision':1})
        self.assertEqual(status, 503)
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('/private', json.dumps(result))
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])

    def test_control_lease_renewal_and_expiry_sweep(self):
        clock = [0.0]
        self.app.fence._clock = lambda: clock[0]
        _, meta = self.start()
        clock[0] = 50
        self.assertEqual(self.post('/api/pulse', {'id':meta['id']})[0], 200)
        clock[0] = 61
        self.assertFalse(self.app.reap_once())
        clock[0] = 111
        self.assertTrue(self.app.reap_once())
        self.assertIsNone(self.app.fence.snapshot()['active_owner'])

if __name__ == '__main__':
    unittest.main()
