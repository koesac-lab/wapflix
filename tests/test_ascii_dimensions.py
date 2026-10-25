#!/usr/bin/env python3
import unittest

from tools.lcd_chunker import resolve_ascii_dimensions

class AsciiDimensionTests(unittest.TestCase):
    def test_auto_dimensions_when_unset(self):
        self.assertEqual(resolve_ascii_dimensions(), (None, None))

    def test_valid_dimensions_are_returned(self):
        self.assertEqual(resolve_ascii_dimensions(120, 54), (120, 54))

    def test_width_without_height_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_ascii_dimensions(width=120)

    def test_height_without_width_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_ascii_dimensions(height=54)

    def test_non_integer_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            resolve_ascii_dimensions(120.0, 54)

    def test_width_bounds_are_enforced(self):
        with self.assertRaises(ValueError):
            resolve_ascii_dimensions(7, 54)
        with self.assertRaises(ValueError):
            resolve_ascii_dimensions(241, 54)

    def test_height_bounds_are_enforced(self):
        with self.assertRaises(ValueError):
            resolve_ascii_dimensions(120, 1)
        with self.assertRaises(ValueError):
            resolve_ascii_dimensions(120, 201)

if __name__ == '__main__':
    unittest.main()
