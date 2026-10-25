import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE=Path(__file__).resolve().parents[1]/'tools/deployment_inventory.py'
spec=importlib.util.spec_from_file_location('deployment_inventory',MODULE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for name in ('media','cache','state'):(self.root/name).mkdir()
        (self.root/'media/clip.bin').write_bytes(b'test media')
        (self.root/'media/identity').write_bytes(b'fixture disk identity')
        self.digest=hashlib.sha256(b'fixture disk identity').hexdigest()
    def tearDown(self):self.temp.cleanup()
    def args(self,*extra):return m.parser().parse_args(['--root',str(self.root),*extra])
    def run_report(self,*extra):
        return m.collect(self.args(*extra),runner=lambda argv:{'status':'observed','value':'fixture version'})
    def test_missing_values_are_named_not_guessed(self):
        r=self.run_report();self.assertIn('input_required:runtime_uid',r['pending'])
        self.assertIn('input_required:media_root',r['pending']);self.assertIsNone(r['operator_inputs']['memory_limit_bytes'])
    def test_always_distinguishes_observation_from_deployment_readiness(self):
        r=self.run_report();self.assertFalse(r['deployment_ready']);self.assertFalse(r['phase6_0_complete'])
        self.assertIn('evidence_required:representative_source_peak_memory_and_headroom',r['pending'])
    def test_storage_observation_is_read_only(self):
        before=sorted(str(p) for p in self.root.rglob('*'))
        r=self.run_report('--media-root',str(self.root/'media'),'--source','clip.bin')
        self.assertEqual(r['source']['status'],'stat_only');self.assertFalse(r['source']['content_read'])
        self.assertEqual(before,sorted(str(p) for p in self.root.rglob('*')))
    def test_missing_storage_is_not_created(self):
        r=self.run_report('--cache-root',str(self.root/'missing'))
        self.assertEqual(r['storage']['cache']['status'],'unavailable');self.assertFalse((self.root/'missing').exists())
    def test_relative_storage_path_is_rejected(self):
        with self.assertRaises(ValueError):self.run_report('--cache-root','relative')
    def test_empty_directory_not_media_identity(self):
        r=self.run_report('--media-root',str(self.root/'media'))
        self.assertEqual(r['media_identity']['status'],'not_verified');self.assertIn('media_identity_not_verified',r['pending'])
    def test_sentinel_matches_expected_identity(self):
        r=self.run_report('--media-root',str(self.root/'media'),'--sentinel','identity','--sentinel-sha256',self.digest)
        self.assertEqual(r['media_identity']['status'],'matched');self.assertNotIn('media_identity_not_verified',r['pending'])
    def test_wrong_sentinel_is_reported(self):
        r=self.run_report('--media-root',str(self.root/'media'),'--sentinel','identity','--sentinel-sha256','0'*64)
        self.assertIn('media_identity_mismatch',r['pending'])
    def test_sentinel_read_is_bounded(self):
        (self.root/'media/identity').write_bytes(b'x'*4097)
        r=self.run_report('--media-root',str(self.root/'media'),'--sentinel','identity','--sentinel-sha256',self.digest)
        self.assertEqual(r['media_identity']['status'],'invalid_or_unavailable')
    def test_source_traversal_is_refused(self):
        r=self.run_report('--media-root',str(self.root/'media'),'--source','../secret')
        self.assertIn('source_invalid_or_unavailable',r['pending'])
    def test_source_symlink_escape_is_refused(self):
        (self.root/'outside').write_text('private');(self.root/'media/link').symlink_to(self.root/'outside')
        r=self.run_report('--media-root',str(self.root/'media'),'--source','link')
        self.assertIn('source_invalid_or_unavailable',r['pending'])
    def test_overlapping_roots_are_reported(self):
        r=self.run_report('--media-root',str(self.root/'media'),'--cache-root',str(self.root/'media'))
        self.assertIn('storage_roots_overlap:media:cache',r['pending'])
    def test_exact_origins_normalise_trailing_slash(self):
        self.assertEqual(m.origin('https://example.invalid:8443/'),'https://example.invalid:8443')
        self.assertEqual(m.origin('http://[::1]:8103'),'http://[::1]:8103')
    def test_origins_refuse_credentials_wildcards_paths_and_bad_ports(self):
        import argparse
        for value in ['http://user:password@example.invalid','https://*.invalid','https://example.invalid/path','https://example.invalid?q=x','https://example.invalid#x','ftp://example.invalid','https://example.invalid:99999',' http://example.invalid']:
            with self.subTest(value=value),self.assertRaises(argparse.ArgumentTypeError):m.origin(value)
    def test_numeric_values_require_positive_integers(self):
        import argparse
        for value in ['0','-1']:
            with self.assertRaises(argparse.ArgumentTypeError):m.positive(value)
    def test_all_interface_publish_requires_explicit_input_and_warns(self):
        self.assertEqual(self.run_report()['operator_inputs']['publish_addresses'],[])
        r=self.run_report('--publish-address','0.0.0.0')
        self.assertIn('all_interfaces_selected_explicitly_not_public_authentication',r['warnings'])
    def test_version_queries_are_fixed_no_probe_or_daemon_calls(self):
        calls=[]
        m.collect(self.args(),runner=lambda a:calls.append(a) or {'status':'missing'})
        self.assertIn(['ffprobe','-version'],calls)
        self.assertIn(['docker','compose','version'],calls)
        self.assertFalse(any('info' in a or 'ps' in a or '-show_format' in a for a in calls))
    def test_missing_tools_have_named_pending_items(self):
        r=m.collect(self.args(),runner=lambda a:{'status':'missing'})
        self.assertIn('version_unavailable:ffmpeg',r['pending']);self.assertIn('version_unavailable:compose',r['pending'])
    def test_mount_parser_decodes_spaces_and_selects_deepest(self):
        text='1 0 0:1 / / rw - ext4 /dev/a rw\n2 1 0:2 / /mnt/my\\040disk rw - xfs /dev/b rw'
        mount=m.mount_for(Path('/mnt/my disk/media'),m.mounts(text));self.assertEqual(mount['filesystem'],'xfs')
    def test_meminfo_values_are_bytes(self):
        self.assertEqual(m.memory('MemTotal: 1024 kB\nMemAvailable: 512 kB')['MemTotal_bytes'],1048576)
    def test_frozen_source_mismatch_is_explicit(self):
        r=self.run_report();self.assertFalse(r['frozen_sources']['stream-source.js']['matches'])
        self.assertIn('frozen_contract_mismatch:stream-source.js',r['pending'])
    def test_command_timeout_is_nonfatal(self):
        import subprocess
        with patch.object(m.subprocess,'run',side_effect=subprocess.TimeoutExpired(['fixture'],5)):
            self.assertEqual(m.command(['fixture'])['status'],'unavailable_or_timeout')

if __name__=='__main__':unittest.main()
