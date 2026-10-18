import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from srt import parse_srt, parse_srt_text

class SrtTests(unittest.TestCase):
    def test_multiline_absolute_time(self):
        cue = parse_srt_text("1\n00:02:01,000 --> 00:02:03,500\nHello\nworld").cues[0]
        self.assertEqual(cue.as_dict(), {"start": 121, "end": 123.5, "text": "Hello\nworld"})
    def test_bom_crlf_markup(self):
        result = parse_srt_text("\ufeff1\r\n00:00:00,500 --> 00:00:01,500\r\n<I>Hello</I><br/>World")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.cues[0].text, "Hello\nWorld")
    def test_invalid_times_reported(self):
        for value in ("00:61:00,000", "00:00:00,9999", "nan"):
            self.assertEqual(len(parse_srt_text(f"1\n{value} --> 00:00:01,000\nText").errors), 1)
        self.assertEqual(len(parse_srt_text("1\n00:00:02,000 --> 00:00:01,000\nText").errors), 1)
    def test_sort_overlap_and_separator(self):
        result = parse_srt_text("2\n00:00:02,000 --> 00:00:04,000\nB\n \n1\n00:00:01,000 --> 00:00:03,000\nA")
        self.assertEqual([cue.text for cue in result.cues], ["A", "B"])
    def test_empty_and_malformed(self):
        self.assertEqual(parse_srt_text("").cues, [])
        self.assertEqual(len(parse_srt_text("1\nno timing\nText").errors), 1)
        self.assertEqual(len(parse_srt_text("1\n00:00:01,000 --> 00:00:02,000").errors), 1)
    def test_encodings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.srt"
            for encoding in ("utf-8-sig", "utf-16", "cp1252"):
                path.write_bytes("1\n00:00:01,000 --> 00:00:02,000\nCafé".encode(encoding))
                self.assertEqual(parse_srt(path).cues[0].text, "Café")

if __name__ == "__main__":
    unittest.main()
