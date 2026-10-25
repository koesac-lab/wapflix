"""Dependency-free served-route publication checks, not backend/HTTP tests."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tools' / 'handset_fenced_preview.py'
tree = ast.parse(SOURCE.read_text())
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'publish_live')
namespace = {'json': json}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'), namespace)
publish_live = namespace['publish_live']

class PublicationTests(unittest.TestCase):
    def preview(self):
        return SimpleNamespace(nonce='nonce-for-test', routes={
            '/': (b'<body><script src="./sharing.js" defer></script></body>', 'text/html'),
            '/assets/catalogue.json': (b'[{"id":"test-video","variants":{}}]', 'application/json')})

    def test_live_entry_only_in_served_copy_without_static_variants(self):
        preview = self.preview()
        original = preview.routes['/assets/catalogue.json'][0]
        publish_live(preview, 'secret')
        entries = json.loads(preview.routes['/assets/catalogue.json'][0])
        self.assertEqual(entries[0], json.loads(original)[0])
        live = entries[-1]
        self.assertEqual(live['id'], 'local-stream-test')
        self.assertEqual(live['playback_type'], 'local-stream')
        self.assertEqual(live['source_identity'], 'configured-test')
        self.assertNotIn('variants', live)
        self.assertNotIn('secret', preview.routes['/assets/catalogue.json'][0].decode())

    def test_bootstrap_order_and_namespaced_config(self):
        preview = self.preview()
        publish_live(preview, 'secret')
        html = preview.routes['/'][0].decode()
        self.assertLess(html.index('sharing.js'), html.index('stream-source.js'))
        self.assertLess(html.index('stream-source.js'), html.index('handset-live.js'))
        self.assertIn('nonce="nonce-for-test"', html)
        self.assertIn('window.wapflixLiveConfig={"token":"secret","apiBase":"/"}', html)
        self.assertNotIn('var token', html)

    def test_capability_cannot_break_out_of_inline_script(self):
        preview = self.preview()
        token = '</script><script>alert("x")</script>&'
        publish_live(preview, token)
        html = preview.routes['/'][0].decode()
        self.assertNotIn(token, html)
        encoded = html.split('window.wapflixLiveConfig=', 1)[1].split(';</script>', 1)[0]
        self.assertEqual(json.loads(encoded)['token'], token)
        self.assertIn('\\u003c', encoded)

    def test_duplicate_reserved_id_fails_before_mutation(self):
        preview = self.preview()
        preview.routes['/assets/catalogue.json'] = (b'[{"id":"local-stream-test"}]', 'application/json')
        before = dict(preview.routes)
        with self.assertRaises(ValueError):
            publish_live(preview, 'secret')
        self.assertEqual(preview.routes, before)

    def test_invalid_bootstrap_fails_before_mutation(self):
        for html in (b'<body>', b'</body></body>'):
            preview = self.preview()
            preview.routes['/'] = (html, 'text/html')
            before = dict(preview.routes)
            with self.assertRaises(ValueError):
                publish_live(preview, 'secret')
            self.assertEqual(preview.routes, before)

    def test_republishing_cannot_duplicate_scripts_or_entry(self):
        preview = self.preview()
        publish_live(preview, 'secret')
        before = dict(preview.routes)
        with self.assertRaises(ValueError):
            publish_live(preview, 'secret')
        self.assertEqual(preview.routes, before)

if __name__ == '__main__':
    unittest.main()
