"""5A.5B publication/constructor isolation tests; no HTTP or converter is started."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1]/'tools'/'handset_fenced_preview.py'
TREE = ast.parse(SOURCE.read_text())
NODES = [n for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in ('publish_live','HandsetHost')]

class HostCaptionTests(unittest.TestCase):
    def fixture(self, missing=()):
        requested, apps = [], []
        class Preview:
            def __init__(self, root, allowed_hosts):
                self.root = Path('/fixture'); self.allowed_hosts = set(allowed_hosts); self.nonce = 'same-nonce'
                self.routes = {'/': (b'<body><script src="./sharing.js" defer></script></body>','text/html'),
                    '/assets/catalogue.json': (b'[{"id":"static-test"}]','application/json')}
        def confined(root, name):
            requested.append(name)
            if name in missing: raise ValueError('Missing required asset')
            return root/name
        class App:
            def __init__(self, *args, **kwargs):
                self.token = 'secret-token'; self.closed = False; apps.append(self)
            def close(self): self.closed = True
        namespace = {'json':json,'static':SimpleNamespace(Preview=Preview,confined=confined),
                     'fenced':SimpleNamespace(FencedApp=App)}
        exec(compile(ast.Module(body=NODES,type_ignores=[]),str(SOURCE),'exec'),namespace)
        return namespace, requested, apps

    def test_live_script_order_reuses_selector_before_ui_before_bridge(self):
        ns, requested, apps = self.fixture(); h = ns['HandsetHost']('root',None,enable_live=True)
        html = h.preview.routes['/'][0].decode()
        names = ['sharing.js','stream-source.js','live-captions.js','handset-captions.js','handset-live.js']
        self.assertEqual(sorted(names,key=html.index),names)
        self.assertEqual(html.count('src="./live-captions.js"'),1)
        self.assertEqual(html.count('src="./handset-captions.js"'),1)

    def test_new_assets_are_allowlisted_only_for_live_mode(self):
        ns, requested, apps = self.fixture(); static = ns['HandsetHost']('root',None)
        self.assertNotIn('/live-captions.js',static.preview.routes)
        self.assertNotIn('/handset-captions.js',static.preview.routes)
        live = ns['HandsetHost']('root',None,enable_live=True)
        self.assertIn('/live-captions.js',live.preview.routes)
        self.assertIn('/handset-captions.js',live.preview.routes)

    def test_missing_selector_stops_before_backend_creation(self):
        ns, requested, apps = self.fixture(['live-captions.js'])
        with self.assertRaises(ValueError): ns['HandsetHost']('root',None,enable_live=True)
        self.assertEqual(apps,[])

    def test_missing_ui_stops_before_backend_creation(self):
        ns, requested, apps = self.fixture(['handset-captions.js'])
        with self.assertRaises(ValueError): ns['HandsetHost']('root',None,enable_live=True)
        self.assertEqual(apps,[])

    def test_static_mode_does_not_require_unused_caption_assets(self):
        ns, requested, apps = self.fixture(['live-captions.js','handset-captions.js'])
        h = ns['HandsetHost']('root',None)
        self.assertNotIn('live-captions.js',requested)
        self.assertNotIn(b'wapflixLiveConfig',h.preview.routes['/'][0])

    def test_capability_nonce_and_catalogue_boundaries_are_preserved(self):
        ns, requested, apps = self.fixture(); h = ns['HandsetHost']('root',None,enable_live=True)
        html = h.preview.routes['/'][0].decode(); catalogue = h.preview.routes['/assets/catalogue.json'][0]
        self.assertIn('nonce="same-nonce"',html); self.assertIn("'nonce-same-nonce'",h.csp())
        self.assertIn('secret-token',html); self.assertNotIn(b'secret-token',catalogue)
        self.assertNotIn(b'variants',catalogue)

    def test_live_entry_description_matches_new_controls(self):
        ns, requested, apps = self.fixture(); h = ns['HandsetHost']('root',None,enable_live=True)
        description = json.loads(h.preview.routes['/assets/catalogue.json'][0])[-1]['description']
        self.assertIn('pauses/resumes',description); self.assertIn('2 toggles captions',description)

    def test_caption_scripts_do_not_add_csp_inline_exceptions(self):
        ns, requested, apps = self.fixture(); h = ns['HandsetHost']('root',None,enable_live=True)
        self.assertNotIn("'unsafe-inline'",h.csp().split('style-src')[0])
        self.assertIn("connect-src 'self'",h.csp())

if __name__ == '__main__': unittest.main()
