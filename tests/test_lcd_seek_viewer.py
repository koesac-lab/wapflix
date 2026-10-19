from pathlib import Path
from types import SimpleNamespace
import unittest
from tools.lcd_stream_seek_viewer import seek_html, make_app_class

SOURCE='<!doctype html><style></style><button id="captions"></button><canvas id="screen"></canvas><script nonce="__TOKEN__">let captionSession=null,painted=-1;function renderCaptions(){}function bufferedEnd(){}</script>'

class InjectionTests(unittest.TestCase):
    def test_controls_and_nonce_preserved(self):
        result=seek_html(SOURCE)
        self.assertEqual(result.count('id="seekControls"'),1)
        self.assertEqual(result.count('<script'),1)
        self.assertIn('nonce="__TOKEN__"',result)
        self.assertIn('id="seekPosition"',result)
        self.assertIn('id="seekBack"',result)
        self.assertIn('id="seekForward"',result)
        self.assertNotIn('id="seekControls"',SOURCE)
    def test_guarded_injection(self):
        with self.assertRaises(ValueError): seek_html(seek_html(SOURCE))
        with self.assertRaises(ValueError): seek_html(SOURCE.replace('captionSession','changed'))
        with self.assertRaises(ValueError): seek_html(SOURCE+SOURCE)
    def test_backend_constructor_forwarded(self):
        class Backend:
            def __init__(self,*args,**kwargs): self.html=SOURCE;self.args=args;self.kwargs=kwargs;self.closed=False
            def close(self): self.closed=True
        App=make_app_class(SimpleNamespace(SeekApp=Backend))
        app=App('source.mp4',start=30)
        self.assertEqual(app.args,('source.mp4',));self.assertEqual(app.kwargs,{'start':30})
        self.assertIn('id="seekControls"',app.html);self.assertFalse(app.closed)
    def test_incompatible_viewer_closes_backend(self):
        instances=[]
        class Backend:
            def __init__(self): self.html='unsupported';self.closed=False;instances.append(self)
            def close(self): self.closed=True
        with self.assertRaises(ValueError): make_app_class(SimpleNamespace(SeekApp=Backend))()
        self.assertTrue(instances[0].closed)

if __name__=='__main__': unittest.main()
