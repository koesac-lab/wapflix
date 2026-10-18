"""Small dependency-free SRT parser; times remain episode-relative."""
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str
    def as_dict(self):
        return {"start": self.start, "end": self.end, "text": self.text}

@dataclass(frozen=True)
class SubtitleParseResult:
    cues: list
    errors: list
    encoding: str = "text"

STAMP = re.compile(r"^(\d{2,}):(\d{2}):(\d{2}),(\d{3})$")

def timestamp(value):
    match = STAMP.fullmatch(value.strip())
    if not match:
        raise ValueError("expected HH:MM:SS,mmm")
    hours, minutes, seconds, millis = map(int, match.groups())
    if minutes > 59 or seconds > 59:
        raise ValueError("minutes and seconds must be 00-59")
    return hours * 3600 + minutes * 60 + seconds + millis / 1000

def parse_srt_text(raw):
    raw = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n[ \t]*\n+", raw.strip()) if raw.strip() else []
    cues, errors = [], []
    for number, block in enumerate(blocks, 1):
        lines = block.strip().split("\n")
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        try:
            if not lines or "-->" not in lines[0]:
                raise ValueError("missing timing arrow")
            left, right = lines[0].split("-->", 1)
            start, end = timestamp(left), timestamp(right.strip().split()[0])
            if end <= start:
                raise ValueError("end must be after start")
            text = re.sub(r"<br\s*/?>", "\n", "\n".join(lines[1:]), flags=re.I)
            text = re.sub(r"</?(?:i|b|u|font)\b[^>]*>", "", text, flags=re.I).strip()
            if not text:
                raise ValueError("empty text")
            cues.append(SubtitleCue(start, end, text))
        except (ValueError, IndexError) as error:
            errors.append(f"cue {number}: {error}")
    return SubtitleParseResult(sorted(cues, key=lambda cue: (cue.start, cue.end)), errors)

def parse_srt(path):
    path = Path(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("SRT exceeds 8 MiB limit")
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text, encoding = data.decode("utf-16"), "utf-16"
    else:
        try:
            text, encoding = data.decode("utf-8-sig"), "utf-8-sig"
        except UnicodeDecodeError:
            text, encoding = data.decode("cp1252"), "cp1252"
    result = parse_srt_text(text)
    return SubtitleParseResult(result.cues, result.errors, encoding)
