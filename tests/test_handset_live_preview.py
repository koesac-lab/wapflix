"""5A.3A focused host/routing tests for the live handset preview.

Covers: same-origin composition, capability/CSP nonce, safe routing, both gzip
paths (static .gz omits Content-Encoding, API chunk keeps it), the served
catalogue copy gaining exactly one virtual live entry while the on-disk
catalogue stays intact, and Host/Origin checks remaining enabled.
"""
import json
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import handset_live_preview as hlp  # noqa: E402


class LivePreviewHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preview = hlp.Preview(ROOT, port=0)
        cls.server = hlp.Server(('127.0.0.1', 0), hlp.make_handler(cls.preview))
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, path, method='GET', headers=None, body=None):
        conn = HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    # --- 5A.3A: same-origin composition and capability/CSP ---

    def test_root_serves_handset_with_nonce_and_live_scripts(self):
        status, headers, body = self.request('/')
        self.assertEqual(status, 200)
        html = body.decode()
        self.assertIn(f'nonce="{self.preview.nonce}"', html)
        self.assertIn('handset-live.js', html)
        self.assertIn('stream-source.js', html)
        self.assertIn('wapflixLiveConfig', html)

    def test_capability_is_namespaced_and_not_a_global_token_variable(self):
        _, _, body = self.request('/')
        html = body.decode()
        self.assertIn('window.wapflixLiveConfig=', html)
        # A global token variable would collide with the numeric static-load token.
        self.assertNotIn('window.token', html)
        self.assertNotIn('var token=', html)
        self.assertIn('"token":', html)

    def test_capability_token_is_dynamic_and_not_the_catalogue_nonce(self):
        _, _, body = self.request('/')
        html = body.decode()
        self.assertIn(self.preview.live_token, html)
        self.assertNotEqual(self.preview.live_token, self.preview.nonce)

    def test_csp_allows_the_served_nonce_and_self_scripts_only(self):
        _, headers, _ = self.request('/')
        csp = headers['Content-Security-Policy']
        self.assertIn(f"'nonce-{self.preview.nonce}'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertIn("default-src 'none'", csp)
        self.assertNotIn('unsafe-eval', csp)

    def test_external_bridge_and_adapter_are_served_with_nonce(self):
        for name in ('handset-live.js', 'stream-source.js'):
            status, headers, body = self.request('/' + name)
            self.assertEqual(status, 200, name)
            self.assertIn('javascript', headers['Content-Type'])
            self.assertTrue(body)

    # --- 5A.3A: served catalogue copy with one virtual live entry ---

    def test_served_catalogue_appends_exactly_one_live_entry(self):
        _, _, body = self.request('/assets/catalogue.json')
        served = json.loads(body)
        on_disk = json.loads((ROOT / 'assets' / 'catalogue.json').read_bytes())
        self.assertEqual(len(served), len(on_disk) + 1)
        live = [e for e in served if e.get('id') == hlp.LIVE_ENTRY_ID]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]['playback_type'], 'local-stream')
        self.assertEqual(live[0]['source_identity'], hlp.LIVE_SOURCE_IDENTITY)
        # No fake static variants on the live entry.
        self.assertNotIn('variants', live[0])
        self.assertNotIn('lcd_variants', live[0])

    def test_on_disk_catalogue_is_untouched(self):
        on_disk = json.loads((ROOT / 'assets' / 'catalogue.json').read_bytes())
        self.assertNotIn(hlp.LIVE_ENTRY_ID, [e.get('id') for e in on_disk])
        self.assertEqual(len(on_disk), 2)

    def test_live_entry_is_identified_by_exact_id_not_substring(self):
        _, _, body = self.request('/assets/catalogue.json')
        served = json.loads(body)
        for entry in served:
            if entry.get('id') != hlp.LIVE_ENTRY_ID:
                self.assertNotIn('local-stream', entry.get('id', ''))
                self.assertNotEqual(entry.get('playback_type'), 'local-stream')

    # --- 5A.3A: both gzip paths ---

    def test_static_gz_asset_omits_content_encoding(self):
        catalogue = json.loads((ROOT / 'assets' / 'catalogue.json').read_bytes())
        gz_path = catalogue[0]['variants']['medium']['path']
        status, headers, body = self.request('/' + gz_path)
        self.assertEqual(status, 200)
        self.assertNotIn('Content-Encoding', headers)
        self.assertEqual(headers['Content-Type'], 'application/gzip')
        self.assertEqual(int(headers['Content-Length']), len(body))

    def test_static_json_asset_omits_content_encoding(self):
        catalogue = json.loads((ROOT / 'assets' / 'catalogue.json').read_bytes())
        json_path = catalogue[0]['variants']['medium']['fallback']
        status, headers, _ = self.request('/' + json_path)
        self.assertEqual(status, 200)
        self.assertNotIn('Content-Encoding', headers)

    def test_api_gzip_chunk_retains_content_encoding(self):
        token = self.preview.live_token
        headers = {'X-Wapflix-Test': token, 'Content-Type': 'application/json'}
        status, _, body = self.request('/api/start', 'POST', headers, b'{}')
        self.assertEqual(status, 200)
        start = json.loads(body)
        pulse_headers = dict(headers)
        status, _, body = self.request(
            '/api/pulse', 'POST', pulse_headers,
            json.dumps({'id': start['id'], 'frame': 0, 'paused': False}).encode())
        self.assertEqual(status, 200)
        chunk_headers = dict(headers)
        status, resp_headers, body = self.request(
            '/api/chunk?id=' + start['id'] + '&n=0', 'POST', chunk_headers, b'{}')
        self.assertIn(status, (200, 204))
        if status == 200:
            self.assertEqual(resp_headers.get('Content-Encoding'), 'gzip')
        self.request('/api/navigation/stop', 'POST', headers,
                     json.dumps({'navigation_id': start['navigation_id']}).encode())

    # --- 5A.3A: safe routing and unchanged security boundaries ---

    def test_unknown_paths_are_not_served(self):
        for path in ('/tools/handset_live_preview.py', '/.git/config', '/output/', '/README.md',
                     '/assets/catalogue.json.gz', '/stream-source.js.bak'):
            status, _, _ = self.request(path)
            self.assertEqual(status, 404, path)

    def test_api_requires_the_capability_token(self):
        status, _, body = self.request('/api/start', 'POST', {'Content-Type': 'application/json'}, b'{}')
        self.assertEqual(status, 403)
        self.assertIn('Forbidden', json.loads(body)['error'])

    def test_api_rejects_a_wrong_token(self):
        status, _, _ = self.request('/api/start', 'POST',
                                    {'X-Wapflix-Test': 'wrong', 'Content-Type': 'application/json'}, b'{}')
        self.assertEqual(status, 403)

    def test_api_rejects_a_foreign_origin(self):
        status, _, body = self.request('/api/start', 'POST', {
            'X-Wapflix-Test': self.preview.live_token,
            'Origin': 'http://evil.example',
            'Content-Type': 'application/json',
        }, b'{}')
        self.assertEqual(status, 403)
        self.assertIn('Origin', json.loads(body)['error'])

    def test_invalid_host_header_is_rejected(self):
        # Use a raw socket so HTTPConnection does not inject its own Host header.
        sock = (socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        sock.settimeout(5)
        try:
            sock.connect(('127.0.0.1', self.port))
            sock.sendall(b'GET / HTTP/1.1\r\nHost: evil.example:9999\r\nConnection: close\r\n\r\n')
            resp = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
            status_line = resp.split(b'\r\n', 1)[0]
            self.assertIn(b'403', status_line)
        finally:
            sock.close()

    def test_cors_headers_are_not_emitted(self):
        _, headers, _ = self.request('/')
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_api_response_shapes_match_the_adapter_contract(self):
        headers = {'X-Wapflix-Test': self.preview.live_token, 'Content-Type': 'application/json'}
        _, _, body = self.request('/api/start', 'POST', headers, b'{}')
        start = json.loads(body)
        for field in ('navigation_id', 'id', 'cols', 'rows', 'fps', 'chunk_frames',
                      'source_start', 'range_start', 'range_end', 'state',
                      'ready_frames', 'generated_chunks', 'total_frames', 'captions'):
            self.assertIn(field, start)
        _, _, body = self.request('/api/pulse', 'POST', headers, json.dumps(
            {'id': start['id'], 'frame': 0, 'paused': False}).encode())
        pulse = json.loads(body)
        for field in ('id', 'state', 'ready_frames', 'generated_chunks', 'total_frames', 'source_start'):
            self.assertIn(field, pulse)
        self.request('/api/navigation/stop', 'POST', headers,
                     json.dumps({'navigation_id': start['navigation_id']}).encode())

    def test_pulse_for_an_unknown_session_is_not_found(self):
        headers = {'X-Wapflix-Test': self.preview.live_token, 'Content-Type': 'application/json'}
        status, _, _ = self.request('/api/pulse', 'POST', headers, json.dumps(
            {'id': 'nope', 'frame': 0, 'paused': False}).encode())
        self.assertEqual(status, 404)

    def test_navigation_stop_only_cancels_its_own_navigation(self):
        headers = {'X-Wapflix-Test': self.preview.live_token, 'Content-Type': 'application/json'}
        _, _, body = self.request('/api/start', 'POST', headers, b'{}')
        first = json.loads(body)
        _, _, body = self.request('/api/start', 'POST', headers, b'{}')
        second = json.loads(body)
        self.request('/api/navigation/stop', 'POST', headers,
                     json.dumps({'navigation_id': first['navigation_id']}).encode())
        # The newer navigation still answers pulses.
        status, _, body = self.request('/api/pulse', 'POST', headers, json.dumps(
            {'id': second['id'], 'frame': 0, 'paused': False}).encode())
        self.assertEqual(status, 200)
        self.request('/api/navigation/stop', 'POST', headers,
                     json.dumps({'navigation_id': second['navigation_id']}).encode())


class LivePreviewUnitTests(unittest.TestCase):
    def test_bootstrap_refuses_an_unsupported_index(self):
        with self.assertRaises(ValueError):
            hlp.bootstrap('<html><body></body></html>', 'nonce', 'token')

    def test_bootstrap_injects_config_and_live_script_once(self):
        source = (ROOT / 'index.html').read_text()
        html = hlp.bootstrap(source, 'abc123', 'cap-token').decode()
        self.assertEqual(html.count('handset-live.js'), 1)
        self.assertEqual(html.count('wapflixLiveConfig'), 1)
        self.assertIn('"cap-token"', html)
        self.assertIn('nonce="abc123"', html)

    def test_asset_path_rejects_traversal_and_non_asset_paths(self):
        for value in ('../secret', 'tools/x.py', 'assets/../../etc/passwd', 'assets/a.json?x=1',
                      'assets/a.txt', 'assets\\a.json'):
            with self.assertRaises(ValueError, msg=value):
                hlp.asset_path(value)

    def test_live_entry_has_no_static_variants(self):
        self.assertNotIn('variants', hlp.LIVE_ENTRY)
        self.assertNotIn('lcd_variants', hlp.LIVE_ENTRY)
        self.assertEqual(hlp.LIVE_ENTRY['id'], hlp.LIVE_ENTRY_ID)


if __name__ == '__main__':
    unittest.main(verbosity=2)
