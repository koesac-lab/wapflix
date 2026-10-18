import unittest
from tools.phone_video import scene

class PhoneSceneTests(unittest.TestCase):
    def test_native_dimensions_and_clean_frames(self):
        for theme in ('pods', 'hotel'):
            for season in (1, 2, 11):
                for episode in (1, 5, 10):
                    for t in (0, 1.5, 7.75, 8, 12, 15.75, 16, 23.875):
                        frame = scene(theme, season, episode, t)
                        lines = frame.splitlines()
                        self.assertEqual(len(lines), 25)
                        self.assertTrue(all(len(line) == 40 for line in lines))
                        for banner in ('24-SECOND', 'FICTIONAL', 'WAPFLIX', 'TRANSMISSION', 'FEELINGS'):
                            self.assertNotIn(banner, frame)
    def test_each_scene_has_motion(self):
        for theme in ('pods', 'hotel'):
            for phase in (0, 8, 16):
                frames = {scene(theme, 1, 1, phase+n/4) for n in range(24)}
                self.assertGreater(len(frames), 2)

if __name__ == '__main__':
    unittest.main()
