"""R2B.1 real loopback HTTP tests; no media input or FFmpeg required."""
import http.client
import json
import threading
import unittest
from unittest.mock import patch
from tools import lcd_stream_control_api as control
from tools.start_fence import StartFence, FenceError, MAX_REVISION

class ControlHTTPTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.fence = StartFence(clock=lambda: self.now)
        self.app = control.ControlOnlyApp(fence=self.fence)
        self.server = control.base.Server(('127.0.0.1', 0), control.make_handler(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.shutdown)

    def shutdown(self):
        self.server.shutdown()
        self.thread.join(2)
        self.server.server_close()
        owner = self.fence.close()
        if owner:
            self.fence.finish(owner)  # injected unit fixture, never a runtime worker

    def post(self, path, body=None, *, auth=True, headers=None, raw=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=2)
        supplied = {'Content-Type': 'application/json'}
        if auth:
            supplied['X-Wapflix-Test'] = self.app.token
        supplied.update(headers or {})
        try:
            conn.request('POST', path, body=raw if raw is not None else json.dumps(body if body is not None else {}), headers=supplied)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def open(self):
        status, body = self.post('/api/control/open')
        self.assertEqual(status, 200)
        self.assertEqual(body['control_protocol'], 'start-fence-v1')
        self.assertEqual(body['control_lease_seconds'], 60)
        self.assertRegex(body['control_client_id'], r'^[0-9a-f]{48}$')
        return body['control_client_id']

    def cancel(self, client, revision):
        return self.post('/api/control/cancel', {'control_client_id': client, 'cancel_through': revision})

    def test_cancel_before_start_and_repeated_cancel(self):
        client = self.open()
        for revision in (0, 4, 4, 2):
            self.assertEqual(self.cancel(client, revision), (200, {'fence_recorded': True, 'cleanup': 'not_required'}))
        with self.assertRaises(FenceError) as caught:
            self.fence.request(client, 4)
        self.assertEqual(caught.exception.code, 'cancelled_start')
        self.fence.check(self.fence.request(client, 5))

    def test_unknown_expired_and_capacity(self):
        self.assertEqual(self.cancel('a'*48, 0)[0], 404)
        client = self.open()
        self.now = 61
        self.assertEqual(self.cancel(client, 1)[1]['code'], 'control_client_gone')
        for _ in range(32):
            self.open()
        self.assertEqual(self.post('/api/control/open')[0], 429)
        self.now = 122
        self.open()

    def test_field_and_body_bounds(self):
        client = self.open()
        for value in (-1, MAX_REVISION+1, True, False, 1.5, '1', None):
            with self.subTest(value=value):
                self.assertEqual(self.cancel(client, value)[0], 400)
        self.assertEqual(self.cancel(client, MAX_REVISION)[0], 200)
        for value in ('a', 'A'*48, 'g'*48, None, [], 12):
            self.assertEqual(self.cancel(value, 0)[0], 400)
        for raw in ('[]', '{', 'null', '"x"', ' '*4097):
            self.assertEqual(self.post('/api/control/open', raw=raw)[0], 400)
        self.assertEqual(self.post('/api/control/open', {'video': '/tmp/no'})[0], 400)

    def test_security_and_no_unauthorized_registration(self):
        self.assertEqual(self.post('/api/control/open', auth=False)[0], 403)
        self.assertEqual(self.post('/api/control/open', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.post('/api/control/open', headers={'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.fence.snapshot()['clients'], 0)
        origin = 'http://127.0.0.1:' + str(self.server.server_port)
        self.assertEqual(self.post('/api/control/open', headers={'Origin': origin})[0], 200)
        self.assertEqual(self.post('/api/control/open', {'token': self.app.token}, auth=False)[0], 200)

    def test_start_and_other_media_routes_never_prepare(self):
        with patch.object(control.base, 'LCDStream', side_effect=AssertionError('probe')), patch.object(control.base, 'Session', side_effect=AssertionError('worker')):
            for body in ({}, {'control_client_id': self.open(), 'start_revision': 1}, {'video': '/tmp/no'}):
                status, result = self.post('/api/start', body)
                self.assertEqual(status, 409)
                self.assertEqual(result['code'], 'fenced_admission_unavailable')
            for path in ('/api/seek', '/api/pulse', '/api/stop', '/api/navigation/stop'):
                self.assertEqual(self.post(path)[0], 404)

    def test_expired_active_owner_retained_and_stale_cancel_safe(self):
        client = self.open()
        ticket = self.fence.request(client, 2)
        owner = self.fence.admit(ticket, lambda ident: None)
        self.assertEqual(self.cancel(client, 1)[0], 200)
        self.assertEqual(self.fence.snapshot()['active_owner'], owner)
        self.now = 61
        status, result = self.cancel(client, 2)
        self.assertEqual(status, 503)
        self.assertEqual(result, {'error': 'Owner cleanup unavailable', 'code': 'cleanup_unconfirmed', 'fence_recorded': True, 'cleanup': 'unconfirmed'})
        self.assertEqual(self.fence.snapshot()['active_owner'], owner)

    def test_concurrent_registration_is_bounded(self):
        results = []
        lock = threading.Lock()
        def register():
            result = self.post('/api/control/open')[0]
            with lock:
                results.append(result)
        threads = [threading.Thread(target=register) for _ in range(12)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(4)
        self.assertEqual(results, [200]*12)
        self.assertEqual(self.fence.snapshot()['clients'], 12)

if __name__ == '__main__':
    unittest.main()
