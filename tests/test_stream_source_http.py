"""R2C real Node-fetch + HTTP + FFmpeg integration gate."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from tools.lcd_m4_factory import FixedSource
from tools.lcd_stream_fenced_api import FencedApp, make_handler
from tools.lcd_stream_control_api import ControlOnlyApp, make_handler as control_handler
from tools.lcd_stream_server import Server

@unittest.skipUnless(all(shutil.which(tool) for tool in ('node', 'ffmpeg', 'ffprobe')),
                     'Node 18+ with fetch, FFmpeg and ffprobe required')
class StreamSourceHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.video = Path(cls.temp.name) / 'generated.mkv'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=64x48:rate=8', '-t', '30', '-an', '-c:v', 'ffv1',
            '-threads', '1', str(cls.video)], check=True, timeout=30)

    def run_case(self, case, control_only=False):
        app = ControlOnlyApp() if control_only else FencedApp(
            FixedSource(self.video, .5, 12, .01), no_srt=True)
        server = Server(('127.0.0.1', 0), (control_handler if control_only else make_handler)(app))
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
        thread.start()
        try:
            environment = dict(os.environ, WAPFLIX_TEST_BASE=f'http://127.0.0.1:{server.server_port}/',
                               WAPFLIX_TEST_TOKEN=app.token)
            client = Path(__file__).with_name('stream_source_http_client.cjs')
            result = subprocess.run(['node', str(client), case], env=environment,
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS combined adapter/server ' + case, result.stdout)
            if not control_only:
                self.assertIsNone(app.fence.snapshot()['active_owner'])
        finally:
            server.shutdown()
            thread.join(2)
            app.close()
            server.server_close()

    def test_real_frames_and_scoped_stop(self):
        self.run_case('normal')
    def test_stop_before_delayed_handler_dispatch(self):
        self.run_case('dispatch')
    def test_timeout_then_newer_start_late_old_handler(self):
        self.run_case('timeout')
    def test_stop_after_admission_before_acknowledgement(self):
        self.run_case('ack')
    def test_control_only_is_not_silently_downgraded(self):
        self.run_case('control-only', control_only=True)

if __name__ == '__main__':
    unittest.main()
