"""R2B.3 real M4 session factory; deliberately not an HTTP entry point.

Reuses Session/LCDStream and CaptionApp.caption_data, not a synthetic converter.
Session construction (one ffprobe, existing 30s timeout) happens in prepare.
No App/SeekApp is instantiated: their legacy monitor/begin paths must not bypass
coordinator ownership. HTTP, playback lease routing and seek continuity are R2B.4.
"""
from dataclasses import dataclass
import math
from pathlib import Path
import secrets
from types import SimpleNamespace
from . import lcd_stream_server as base
from . import lcd_stream_captions as captions
from . import srt

@dataclass(frozen=True)
class FixedSource:
    video: Path
    start: float = 30
    seconds: float = 60
    delay: float = 0

    def __post_init__(self):
        object.__setattr__(self, 'video', Path(self.video).expanduser().resolve())
        for name in ('start', 'seconds', 'delay'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('Invalid fixed-source ' + name)
        if self.start < 0 or not 0 < self.seconds <= 120 or not 0 <= self.delay <= 5:
            raise ValueError('Invalid fixed-source window/delay')

class M4Factory:
    def __init__(self, spec, *, subtitles=None, no_srt=False):
        if type(spec) is not FixedSource:
            raise ValueError('A fixed immutable source configuration is required')
        if subtitles is not None and no_srt:
            raise ValueError('Choose subtitles or no_srt, not both')
        self._spec = spec
        path = captions.find_subtitles(spec.video, subtitles, no_srt)
        parsed = srt.parse_srt(path) if path is not None else None
        # Existing SubtitleParseResult/Cue objects are frozen, with tuple fields.
        self._track = parsed

    @property
    def spec(self):
        return self._spec

    def prepare(self, immutable_spec, ticket):
        if type(immutable_spec) is not FixedSource or immutable_spec != self._spec:
            raise ValueError('Start cannot replace the server-configured source/window')
        # A frozen value object is used instead of mutable SeekApp.start/seconds.
        # The real Session constructor probes once but neither starts its thread
        # nor opens a converter. All of this runs outside coordinator/core locks.
        session = base.Session(self._spec)
        return M4Candidate(session, self._spec, self._track, ticket)

class M4Candidate:
    def __init__(self, session, spec, track, ticket):
        self.session = session
        self.spec = spec
        self._track = track
        self._ticket = ticket
        self.owner_id = None
        self.navigation_id = secrets.token_hex(16)
        self._published = False

    def publish(self, owner_id):
        # Admission callback: identity assignment + thread scheduling only.
        # The existing Session.work performs Popen in its own worker thread.
        if self._published or self.session.stop_event.is_set():
            raise RuntimeError('Candidate already published or stopped')
        self.owner_id = owner_id
        self._published = True
        self.session.thread.start()

    def snapshot(self):
        if not self._published:
            raise RuntimeError('Candidate not admitted')
        result = self.session.snapshot()
        result.update(
            captions=captions.CaptionApp.caption_data(SimpleNamespace(parsed=self._track), self.session),
            navigation_id=self.navigation_id, revision=0,
            range_start=self.spec.start,
            range_end=self.spec.start + self.session.stream.seconds,
            seek_position=self.session.stream.start, seek_mode='restart',
            control_protocol='start-fence-v1',
            control_client_id=self._ticket.client,
            start_revision=self._ticket.revision)
        return result

    def stop(self):
        # Session.stop uses the inherited terminate/kill/join budgets. Never
        # release core ownership on an exception or an unconfirmed process exit.
        self.session.stop()
        process = self.session.stream.process
        if self.session.thread.is_alive() or (process is not None and process.poll() is None):
            raise RuntimeError('Real converter cleanup unconfirmed')
        return True
