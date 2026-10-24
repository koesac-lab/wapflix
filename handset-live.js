(() => {
'use strict';
// 5A.3 local-only bridge: on-demand stream inside the existing handset.
// Depends on: index.html inline bootstrap, player.js, streaming.js,
// theme.js, sharing.js, stream-source.js (WapflixStreamSource). Loaded last so
// it sees the global `render`/`load`/`select`/`back`/`key`/`tick` defined by
// streaming.js. The bridge redefines those globals for live mode and delegates
// static playback unchanged.

const LIVE_ENTRY_ID = 'local-stream-test';
const STARTUP_TARGET_SECONDS = 4;   // contiguous footage target at startup
const POLL_INTERVAL_MS = 250;      // established heartbeat cadence

// Capability/config injected by server bootstrap into namespaced object.
const cfg = window.wapflixLiveConfig || {};

// Self-contained drawing layer mirrors the phone palette exactly. The existing
// index.html helpers (text/center/wrap/seconds/ink/ctx) are closure-local,
// so this bridge owns the small pixel/text helpers it needs rather than
// depending on them. Font metrics match #25371e monospace glyph boxes.
const $ = id => document.getElementById(id);
const canvas = $('display');
const ctx = canvas.getContext('2d');
const INK = '#25371e';
const CANVAS_W = 240, CANVAS_H = 224;

// Offscreen image buffer (same pattern as static player).
const imgCanvas = document.createElement('canvas');
const imgCtx = imgCanvas.getContext('2d');

function text(value, x, y) {
  ctx.fillStyle = INK;
  for (const ch of String(value)) {
    const bits = GLYPHS[ch] || GLYPHS[ch.toUpperCase()];
    if (bits) for (let r = 0; r < 7; r++) {
      const mask = parseInt(bits.slice(r * 2, r * 2 + 2), 16);
      for (let c = 0; c < 5; c++) if (mask & (16 >> c)) ctx.fillRect(x + c, y + r, 1, 1);
    }
    x += 6;
  }
}
function center(s, y) { text(s, Math.max(2, Math.floor((CANVAS_W - s.length * 6) / 2)), y); }
function wrap(s, width = 37) {
  const lines = []; let line = '';
  for (const w of String(s).split(/\s+/)) {
    if ((line + ' ' + w).trim().length > width && line) { lines.push(line); line = ''; }
    line += (line ? ' ' : '') + w;
  }
  if (line) lines.push(line); return lines;
}
const seconds = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

const GLYPHS = {A:'0E11111F111111',B:'1E11111E11111E',C:'0E11101010110E',D:'1E11111111111E',E:'1F10101E10101F',F:'1F10101E101010',G:'0E11101711110F',H:'1111111F111111',I:'0E04040404040E',J:'0702020212120C',K:'11121418141211',L:'1010101010101F',M:'111B1515111111',N:'11191513111111',O:'0E11111111110E',P:'1E11111E101010',Q:'0E11111115120D',R:'1E11111E141211',S:'0F10100E01011E',T:'1F040404040404',U:'1111111111110E',V:'11111111110A04',W:'11111115151B11',X:'11110A040A1111',Y:'11110A04040404',Z:'1F01020408101F',
    '0':'0E11131519110E','1':'040C040404040E','2':'0E11010204081F','3':'1E01010601011E','4':'02060A121F0202','5':'1F10101E01011E','6':'0E10101E11110E','7':'1F010204080808','8':'0E11110E11110E','9':'0E11110F01010E','.':'00000000000C0C',',':'000000000C0C08',':':'000C0C000C0C00',';':'000C0C000C0C08','!':'04040404040004','?':'0E110102040004','-':'0000001F000000','_':'0000000000001F','/':'01010204081010','\\':'10100804020101','|':'04040404040404','[':'0E08080808080E',']':'0E02020202020E','(':'02040808080402',')':'08040202020408','<':'01020408040201','>':'10080402040810','+':'0004041F040400','=':'00001F001F0000','*':'00150E1F0E1500','#':'0A1F0A0A1F0A00',"'":'04040800000000','"':'0A0A1400000000','@':'0E11171517100F','&':'0C12140C15120D','%':'19190204081313','~':'00000916000000','^':'040A1100000000'};

function header() {
  ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
  ctx.fillStyle = INK;
  for (let i = 0; i < 4; i++) ctx.fillRect(2 + i * 4, 12 - i * 3, 3, 3 + i * 3);
  text('WAPFLIX', 83, 3); text('WAP', 29, 3);
  ctx.strokeStyle = INK; ctx.lineWidth = 1;
  ctx.strokeRect(214.5, 2.5, 20, 10);
  ctx.fillRect(235, 5, 2, 5); ctx.fillRect(217, 5, 14, 5);
  ctx.fillRect(0, 19, CANVAS_W, 204);
}
function footer(left, right) {
  ctx.fillStyle = INK;
  ctx.fillRect(0, 207, CANVAS_W, 1);
  text(left, 3, 214);
  text(right, CANVAS_W - 3 - right.length * 6, 214);
  $('left').setAttribute('aria-label', left);
  $('back').setAttribute('aria-label', right);
}
function drawScene(hex, cols, rows) {
  ctx.imageSmoothingEnabled = false;
  // Scale to fit within 240x224 preserving aspect ratio, nearest neighbour.
  const native = cols === 240 && rows === 224;
  const lcd = cols === 240 && rows === 135;
  const width = lcd ? 240 : native ? cols : cols * 6;
  const height = lcd ? 224 : native ? rows : rows * 8;
  const fit = Math.min(CANVAS_W / width, CANVAS_H / height);
  const scale = lcd && fit >= 1 ? Math.floor(fit) : fit;
  const w = Math.round(width * scale), h = Math.round(height * scale);
  // Decode chosen hex-msb frame - standalone pixel loop, same palette.
  ctx.fillStyle = INK;
  if (imgCanvas.width !== cols || imgCanvas.height !== rows) {
    imgCanvas.width = cols; imgCanvas.height = rows;
    imgCtx.clearRect(0, 0, cols, rows);
  }
  for (let b = 0; b < hex.length; b += 2) {
    const value = parseInt(hex.slice(b, b + 2), 16);
    for (let bit = 0; bit < 8; bit++) {
      const px = (b / 2) * 8 + bit;
      if (px < cols * rows && (value & (128 >> bit))) {
        const x = (px % cols), y = Math.floor(px / cols);
        imgCtx.fillRect(x, y, 1, 1);
      }
    }
  }
  ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
  if (native) {
    ctx.drawImage(imgCanvas, Math.floor((CANVAS_W - width) / 2), Math.floor((CANVAS_H - height) / 2), width, height);
  } else {
    const offX = Math.floor((CANVAS_W - w) / 2), offY = Math.floor((CANVAS_H - h) / 2);
    ctx.drawImage(imgCanvas, offX, offY, w, h);
  }
}

// ---- Capture original globals BEFORE we replace them ----
const _origLoad = window.load;
const _origSelect = window.select;
const _origBack = window.back;
const _origKey = window.key;
const _origTick = window.tick;
const _origRender = window.render;
const _origPaint = window.paint;

// ---- Adapter wrapper around WapflixStreamSource ----
class StreamBridge {
  constructor(token, baseUrl) {
    this.adapter = new WapflixStreamSource({
      token, baseUrl, timeoutMs: 10000,
      fetchImpl: window.fetch.bind(window),
    });
    this._generation = 0;
    this._state = 'idle';           // idle|starting|buffering|playing|paused|ended|error|stopping
    this._resumeState = 'buffering'; // state to restore when leaving 'paused'
    this._relPosition = 0;
    this._sourceStart = 0;
    this._totalDuration = null;
    this._presentedFrame = null;
    this._clockStart = 0;
    this._rafScheduled = false;
    this._pollTimer = null;
    this._metadata = null;
  }
  get active() { return ['starting', 'buffering', 'playing', 'paused'].includes(this._state); }
  isLivePlaying() { return this._state === 'playing'; }
  get framed() { return this._presentedFrame !== null; }

  _validateEntry(entry) {
    return entry && typeof entry.id === 'string' && entry.id === LIVE_ENTRY_ID;
  }

  async pause() {
    if (!this.active) return;
    if (this._state === 'paused') return;
    this._resumeState = this._state; // buffering | playing
    this._state = 'paused';
    this._generation++;
    this._announce('PAUSED');
    this._renderFooter(performance.now());
  }

  async resume() {
    if (this._state !== 'paused') return;
    this._generation++;
    this._state = this._resumeState || 'playing';
    this._scheduleRaf();
    this._renderFooter(performance.now());
    this._announce('PLAYING');
  }

  async play(entry) {
    if (!this._validateEntry(entry)) return;
    if (this.active) return; // in-flight guard
    this._generation++;
    this._resetClock();
    this._presentedFrame = null;
    try {
      this.adapter._invalidate('starting');
      this._state = 'starting';
      const meta = await this.adapter.start();
      this._metadata = meta;
      this._sourceStart = meta.source_start;
      this._totalDuration = meta.range_end - meta.source_start;
      this._state = 'buffering';
      this._clockStart = performance.now();
      this._spawnPoll();
      this._scheduleRaf();
      this._announce('BUFFERING');
    } catch (err) {
      this._state = 'error';
      throw err;
    }
  }

  async stop() {
    if (!this.active) return;
    if (['starting', 'stopping'].includes(this._state)) return; // leave immediately, no late respawn
    this._generation++;
    this._cancelPoll();
    this._cancelRaf();
    this._state = 'stopping';
    try { await this.adapter.stop(); } catch (_) {}
    this._invalidateStale();
    this._state = 'idle';
    this._metadata = null;
  }

  async backToDetails() {
    await this.stop();
    // streaming.js back() from 'player' goes to page.name (details).
    // We are in 'live' mode; simulate by restoring previous view.
    // The captured previous view is stored when live started.
    leavePlayerToDetails();
  }

  async backToHome() {
    await this.stop();
    const ev = new Event('pagehide');
    window.dispatchEvent(ev);
  }

  _resetClock() { this._relPosition = 0; this._clockStart = 0; }
  _invalidateStale() { this._cancelPoll(); this._cancelRaf(); }
  _spawnPoll() {
    this._cancelPoll();
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      if (!this.active) return;
      try {
        const status = await this.adapter.poll({
          sourceTime: this._sourceStart + this._relPosition,
          paused: this._state === 'paused',
        });
        const g = this._generation;
        if (!status) { this._scheduleRaf(); return; }
        if (g !== this._generation) return;
        if (['complete','error','stopped'].includes(status.state)) { this._handleTerminal(status); return; }
        this._checkTailThroughEOF(status);
        if (this._state === 'buffering') this._state = 'playing';
        this._scheduleRaf();
      } catch (err) {
        if (this._generation === this.adapter._generation) {
          this._state = 'error';
        }
        this._cancelRaf();
        this._cancelPoll();
      }
    };
    this._pollTimer = setInterval(tick, POLL_INTERVAL_MS);
  }
  _cancelPoll() { if (this._pollTimer) clearInterval(this._pollTimer); this._pollTimer = null; }
  _checkTailThroughEOF(status) {
    if (this.adapter._status?.total_frames != null) {
      this._totalDuration = (this.adapter._status.total_frames || 0) / this.adapter._fps;
    }
    if (['complete', 'stopped'].includes(status.state)) {
      this._handleTerminal(status);
    }
  }
  _handleTerminal(status) {
    this._cancelPoll();
    this._cancelRaf();
    if (status.state === 'stopped') {
      this._state = 'idle';
      return;
    }
    this._state = 'ended';
  }
  _scheduleRaf() {
    if (this._rafScheduled) return;
    this._rafScheduled = true;
    requestAnimationFrame(t => this._raf(t));
  }
  _cancelRaf() { this._rafScheduled = false; }
  _raf(now) {
    this._rafScheduled = false;
    if (!this.framed && this._state !== 'playing') {
      if (this._state === 'buffering') {
        this._renderFooter(now);
        this._scheduleRaf();
      }
      return;
    }
    this._advance(now);
    this._scheduleRaf();
  }
  _advance(now) {
    // The clock only runs while playing. Paused and buffering hold the position.
    if (this._state === 'playing') {
      if (this._clockStart === 0) this._clockStart = now;
      this._relPosition += (now - this._clockStart) / 1000;
      if (this._totalDuration != null) {
        this._relPosition = Math.min(this._relPosition, this._totalDuration);
      }
    }
    this._clockStart = now;
    const frame = this.adapter.frameAt(this._sourceStart + this._relPosition);
    if (frame) {
      this._presentedFrame = frame;
      drawScene(frame.hex, frame.cols, frame.rows);
      this._drawInfoBar(now);
    } else {
      // Underflow: hold the last presented picture, keep the relative position.
      // Never rewind past the start and never advance past available data.
      const bufferedEnd = this.adapter.bufferedUntil(this._sourceStart + this._relPosition);
      if (bufferedEnd != null && bufferedEnd > this._sourceStart) {
        const maxRel = bufferedEnd - this._sourceStart;
        if (this._relPosition > maxRel) this._relPosition = maxRel;
      }
      this._state = this._state === 'playing' ? 'buffering' : this._state;
    }
    this._renderFooter(now);
  }
  _drawInfoBar(now) {
    ctx.fillStyle = INK;
    ctx.fillRect(2, 160, CANVAS_W - 4, 2);
    text(`${seconds(Math.max(0, this._relPosition))}/${seconds(this._totalDuration)}`, 3, 155);
    text(`SRC ${this._sourceStart.toFixed(2)}`, 3, 178);
  }
  _renderFooter(now) {
    let left = 'PLAY', right = 'BACK';
    if (this._state === 'playing') { left = 'STOP'; right = 'BACK'; }
    else if (this._state === 'paused') { left = 'PAUSE'; right = 'BACK'; }
    else if (this._state === 'buffering') { left = 'BUFFERING'; right = 'BACK'; }
    else if (this._state === 'ending' || this._state === 'ended') { left = 'ENDED'; right = 'BACK'; }
    else if (this._state === 'error') { left = 'ERROR'; right = 'BACK'; }
    else if (this._state === 'starting') { left = 'CONNECT'; right = 'BACK'; }
    footer(left, right);
  }
  _announce(msg) { try { $('summary').textContent = msg; } catch (_) {} }
}

// ---- Player integration hooks ----
let bridge = null;
let _capturedView = null;
let _capturedItem = null;

function ensureBridge() {
  if (bridge) return bridge;
  if (!cfg.token || !cfg.token.length) return null;
  bridge = new StreamBridge(cfg.token, cfg.apiBase || '/');
  return bridge;
}

function isLiveEntry(entry) {
  return entry && typeof entry.id === 'string' && entry.id === LIVE_ENTRY_ID;
}

function leavePlayerToDetails() {
  // Restore to details view without writing static resume records.
  const b = ensureBridge();
  if (b) {
    b._generation++;
    b._cancelPoll();
    b._cancelRaf();
    b._state = 'idle';
    b._metadata = null;
  }
  // streaming.js uses global 'view', 'item', 'clip', 'message', 'detail', 'token', 'playing', etc.
  // We captured 'details' and the entry when live started.
  window.view = 'details';
  window.item = _capturedItem;
  window.clip = null;
  window.message = '';
  window.detail = false;
  window.playing = false;
  window.elapsed = 0;
  window.last = 0;
  window.frame = -1;
  window.token++;
  try { localStorage.removeItem('wapflix-static-resume'); } catch (_) {}
  window.render();
  try { window.say(); } catch (_) {}
}

function leavePlayerToHome() {
  const b = ensureBridge();
  if (b) {
    b._generation++;
    b._cancelPoll();
    b._cancelRaf();
    b._state = 'idle';
    b._metadata = null;
  }
  window.history = [];
  window.page = {name: 'home', selected: 0};
  window.view = 'home';
  window.item = null;
  window.clip = null;
  window.message = '';
  window.detail = false;
  window.playing = false;
  window.elapsed = 0;
  window.last = 0;
  window.frame = -1;
  window.token++;
  try { localStorage.removeItem('wapflix-static-resume'); } catch (_) {}
  window.render();
  try { window.say(); } catch (_) {}
}

// Override globals with live-aware versions
window.load = function (selected, keep = false, options = {}) {
  const b = ensureBridge();
  if (b && !keep && isLiveEntry(selected)) {
    // Capture return screen (details) before switching to live
    _capturedView = window.view; // should be 'details'
    _capturedItem = window.item;
    // Invalidate the static-load token so any in-flight static callbacks are rejected.
    window.token++;
    b.play(selected);
    return;
  }
  _origLoad(selected, keep, options);
};

window.select = function () {
  const b = ensureBridge();
  if (b && b.active && b.isLivePlaying()) {
    b.stop().then(() => leavePlayerToDetails());
    return;
  }
  _origSelect();
};

window.back = function () {
  const b = ensureBridge();
  if (b && b.active && (b.isLivePlaying() || b._state === 'starting' || b._state === 'buffering')) {
    b.backToDetails();
    return;
  }
  _origBack();
};

window.key = function (value) {
  const b = ensureBridge();
  if (b && b.active && (b.isLivePlaying() || b._state === 'buffering' || b._state === 'paused')) {
    if (value === '5') {
      if (b._state === 'paused') {
        // Currently paused → resume
        b.resume().then(() => {});
      } else {
        // Currently playing or buffering → pause
        b.pause().then(() => {});
      }
      return;
    }
    handleLiveKey(value);
    return;
  }
  _origKey(value);
};

// Replace tick with bridge step when live; otherwise keep original chain.
window.tick = function (time) {
  const b = ensureBridge();
  if (b && b.active) {
    b._clockStart = time;
    if (b.framed) b._advance(time);
    requestAnimationFrame(window.tick);
    return;
  }
  _origTick(time);
};

// Replace render/paint so live mode draws its own scene.
window.render = function () {
  const b = ensureBridge();
  if (b && b.active && (b._state === 'playing' || b._state === 'buffering' || b._state === 'starting')) {
    header();
    if (b.framed) {
      // Frame already drawn by _advance in tick; just ensure footer
      b._renderFooter(performance.now());
    } else {
      // Buffering/starting: show message
      const msg = b._state === 'buffering' ? 'BUFFERING' : 'CONNECTING...';
      center(msg, 100);
      b._renderFooter(performance.now());
    }
    return;
  }
  _origRender();
};
window.paint = function () {
  const b = ensureBridge();
  if (b && b.active && b.isLivePlaying()) { return; }
  _origPaint();
};

// ---- Live key handling (input-origin/action matrix) ----
function handleLiveKey(v) {
  // Numeric key matrix: exact digits map to live behaviour; others say unavailable.
  // Per plan: Select/5=Stop, Back=Stop+return, *=Stop+Home, #=backlight (delegate),
  // 4/6=Seek unavailable, 0=Quality unavailable, 2=Caption unavailable,
  // 7=ASCII/LCD switch unavailable, Info/sharing=Do not enter static handlers.
  const announce = (msg) => { try { $('summary').textContent = msg; } catch (_) {} };
  switch (v) {
    case '5': bridge.stop().then(() => leavePlayerToDetails()); break;
    case '0': announce('Quality unavailable in live mode.'); break;
    case '2': announce('Caption toggle unavailable in live mode.'); break;
    case '4': announce('Seek unavailable in live mode.'); break;
    case '6': announce('Seek unavailable in live mode.'); break;
    case '7': announce('LCD/ASCII switch unavailable in live mode.'); break;
    case '*': bridge.backToHome(); break;
    case '#': _origKey('#'); break; // delegate backlight
    default: announce('Control ' + v + ' unavailable in live mode.');
  }
}

// ---- Page hide/unload stops live immediately ----
window.addEventListener('visibilitychange', e => {
  if (document.hidden) {
    const b = ensureBridge();
    if (b && b.active) {
      b.stop().then(() => leavePlayerToDetails());
    }
  }
});
window.addEventListener('pagehide', () => {
  const b = ensureBridge();
  if (b && b.active) {
    b.stop().then(() => leavePlayerToDetails());
  }
});

// Initialise the bridge object when capabilities allow.
ensureBridge();
})();