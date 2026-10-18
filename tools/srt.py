"""Small, defensive SRT subtitle parser for the local ASCII tuning lab."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


class SubtitleError(ValueError):
    """Raised when an SRT file cannot be safely parsed."""


@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class SubtitleParseResult:
    cues: tuple[SubtitleCue, ...]
    errors: tuple[str, ...]
    encoding: str


_TIMESTAMP = re.compile(r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})$")
_TAG = re.compile(r"</?(?:i|b|u|font)\b[^>]*>", re.IGNORECASE)
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _seconds(value: str) -> float:
    match = _TIMESTAMP.fullmatch(value.strip())
    if not match:
        raise SubtitleError("expected HH:MM:SS,mmm timestamp")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def _decode(data: bytes) -> tuple[str, str]:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "utf-16"
    try:
        return data.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        return data.decode("cp1252"), "cp1252"


def parse_srt(path: Path, *, max_bytes: int = 8 * 1024 * 1024) -> SubtitleParseResult:
    path = Path(path)
    if not path.is_file():
        raise SubtitleError(f"Subtitle file not found: {path}")
    if path.stat().st_size > max_bytes:
        raise SubtitleError("Subtitle file is too large")
    text, encoding = _decode(path.read_bytes())
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[SubtitleCue] = []
    errors: list[str] = []
    for number, block in enumerate(re.split(r"\n[ \t]*\n+", text.strip()), 1):
        lines = [line for line in block.strip().split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].strip().isdigit():
            lines = lines[1:]
        if len(lines) < 2:
            errors.append(f"cue {number}: missing timing or text")
            continue
        try:
            start_text, end_text = lines[0].split("-->", 1)
            start = _seconds(start_text)
            end = _seconds(end_text.strip().split()[0])
            body = _TAG.sub("", _BREAK.sub("\n", "\n".join(lines[1:])))
            body = "\n".join(line.strip() for line in body.split("\n") if line.strip())
            if end <= start:
                raise SubtitleError("end time must be after start time")
            if not body:
                raise SubtitleError("cue has no readable text")
            cues.append(SubtitleCue(start, end, body))
        except (SubtitleError, ValueError, IndexError) as exc:
            errors.append(f"cue {number}: {exc}")
    return SubtitleParseResult(tuple(sorted(cues, key=lambda cue: (cue.start, cue.end))),
                               tuple(errors), encoding)


def cues_for_window(result: SubtitleParseResult, start: float, end: float) -> tuple[SubtitleCue, ...]:
    """Return cues overlapping [start, end), rebased to the preview window."""
    if end <= start:
        raise SubtitleError("preview end must be after preview start")
    selected = []
    for cue in result.cues:
        if cue.end <= start or cue.start >= end:
            continue
        selected.append(SubtitleCue(
            start=max(0.0, cue.start - start),
            end=min(end - start, cue.end - start),
            text=cue.text,
        ))
    return tuple(selected)
