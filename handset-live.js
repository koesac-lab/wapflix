/* 5A.3B recovery. Loaded last by the opt-in fenced host only. */
(() => {
'use strict';
const cfg = window.wapflixLiveConfig;
if (!cfg?.token) return;
const ENTRY = 'local-stream-test';
const originals = {load, select, back, key, tick, render, paint};
const adapter = new WapflixStreamSource({token: cfg.token, baseUrl: cfg.apiBase || '/'});
const surface = document.createElement('canvas');
const pixels = surface.getContext('2d');
let generation = 0, state = 'idle', metadata = null, status = null;
let position = 0, presented = null, clock = null, timer = null, pendingPoll = null;
let duration = 0, launch = null, cleanup = null, cleanupError = null, errorText = '';
const live = () => view === 'live-player';
const active = () => ['starting', 'buffering', 'playing'].includes(state);
const current = g => g === generation && live();
const sourceTime = () => metadata.source_start + position;
const clearPoll = () => { if (timer !== null) clearInterval(timer); timer = null; };
function release() {
  if (cleanup) return cleanup;
  const operation = Promise.resolve(adapter.stop());
  cleanup = operation;
  operation.then(() => { if (cleanup === operation) { cleanup = null; cleanupError = null; } },
    error => { if (cleanup === operation) { cleanup = null; cleanupError = error; } });
  return operation;
}
function terminal(next, message) {
  const g = generation;
  state = next; errorText = message || ''; clock = null; clearPoll();
  render(); announce(message || 'TRANSMISSION ENDED');
  release().catch(() => {
    if (current(g)) { render(); announce('Cleanup unconfirmed. Back is available; next Start must confirm cleanup.'); }
  });
}
function fail(error) {
  const label = error.name === 'TimeoutError' ? 'TRANSPORT TIMEOUT' :
    error.code === 'client_expired' ? 'SESSION EXPIRED' : 'SESSION ENDED - RESTART';
  terminal('error', label + ': ' + error.message);
}
function available() {
  if (!metadata) return false;
  const at = sourceTime();
  if (!adapter.frameAt(at)) return false;
  const end = adapter.bufferedUntil(at);
  const target = presented ? metadata.chunk_frames / metadata.fps : 4;
  return end != null && (end - at >= target - 1e-7 ||
    (status?.state === 'complete' && end >= metadata.source_start + duration - 1e-7));
}
async function poll(g) {
  if (!current(g) || !metadata || !active() || pendingPoll !== null) return;
  const ticket = {}; pendingPoll = ticket;
  try {
    const next = await adapter.poll({sourceTime: sourceTime(), paused: false});
    if (!current(g) || !active() || !next) return;
    if (next.state === 'error' || next.state === 'stopped') throw Error(next.error || 'Session ended');
    status = next;
    if (next.state === 'complete') duration = Math.min(metadata.range_end - metadata.source_start, next.total_frames / metadata.fps);
    if (state === 'buffering' && available()) {
      state = 'playing'; clock = null;
      presented = adapter.frameAt(sourceTime()); render(); announce('PLAYING');
    }
  } catch (error) { if (current(g) && active()) fail(error); }
  finally { if (pendingPoll === ticket) pendingPoll = null; }
}
async function start(entry) {
  if (live() && active()) return;
  const g = ++generation;
  launch = live() && launch ? launch : {view: !['player', 'ended'].includes(view) ? view : 'details', item: entry};
  ++token; setPlaying(false); clip = null; message = ''; detail = false;
  item = entry; view = 'live-player'; last = 0; frame = -1;
  position = 0; presented = null; metadata = null; status = null;
  duration = 0; clock = null; pendingPoll = null; cleanupError = null; errorText = '';
  clearPoll(); state = 'starting'; render(); announce('CONNECTING');
  try {
    // start() itself enforces release/fencing. Never use private adapter methods.
    const meta = await adapter.start();
    if (!current(g) || state !== 'starting' || !meta) return;
    metadata = meta; duration = meta.range_end - meta.source_start;
    state = 'buffering'; render(); announce('BUFFERING');
    timer = setInterval(() => { void poll(g); }, 250);
    void poll(g);
  } catch (error) { if (current(g)) fail(error); }
}
function exit(home = false) {
  if (!live()) return cleanup || Promise.resolve();
  const g = ++generation; clearPoll(); pendingPoll = null; clock = null; state = 'stopping';
  ++token; setPlaying(false); clip = null; message = ''; detail = false; last = 0; frame = -1;
  const target = launch;
  // Restore immediately, including during unacknowledged Start. Adapter Stop
  // records the out-of-band fence; its late completion never changes navigation.
  view = target?.view || 'details'; item = target?.item || item;
  state = 'idle'; metadata = null; status = null; presented = null;
  if (home) originals.key('*'); else { render(); }
  const operation = release();
  operation.catch(error => { if (g === generation && !live()) announce('STOP CLEANUP UNCONFIRMED: ' + error.message); });
  return operation;
}
function drawPicture() {
  if (!presented) return;
  const {hex, cols, rows} = presented;
  if (surface.width !== cols || surface.height !== rows) { surface.width = cols; surface.height = rows; }
  pixels.clearRect(0, 0, cols, rows); pixels.fillStyle = ink;
  for (let b = 0; b < hex.length; b += 2) {
    const value = parseInt(hex.slice(b, b + 2), 16);
    for (let bit = 0; bit < 8; bit++) {
      const n = b * 4 + bit;
      if (n < cols * rows && (value & (128 >> bit))) pixels.fillRect(n % cols, Math.floor(n / cols), 1, 1);
    }
  }
  const fit = Math.min(240 / cols, 200 / rows);
  const scale = fit >= 1 ? Math.floor(fit) : fit;
  const w = Math.round(cols * scale), h = Math.round(rows * scale);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(surface, Math.floor((240 - w) / 2), Math.floor((200 - h) / 2), w, h);
}
function drawFooter() {
  // Local exception to the static single-Navi SELECT policy; transparent LCD.
  ctx.fillStyle = ink; ctx.fillRect(0, 207, 240, 1);
  const label = active() ? 'STOP' : 'BACK';
  text(label, 3, 214); text('BACK', 213, 214);
  $('left').setAttribute('aria-label', label);
  $('back').setAttribute('aria-label', 'BACK');
}
render = function() {
  if (!live()) return originals.render();
  ctx.clearRect(0, 0, 240, 224); drawPicture();
  if (state === 'starting') center('CONNECTING...', 90);
  else if (state === 'buffering') {
    // Status outside the picture area preserves the held image exactly.
    if (!presented) center('BUFFERING', 90);
    else text('BUFFERING', 3, 193);
  } else if (state === 'ended') {
    text('TRANSMISSION ENDED', 3, 193);
  } else if (state === 'error') {
    ctx.clearRect(0, 0, 240, 190);
    wrap(errorText, 36).slice(0, 10).forEach((line, n) => center(line, 35 + n * 12));
  }
  if (cleanupError) text('CLEANUP UNCONFIRMED', 3, 181);
  drawFooter();
};
paint = function() { if (live()) render(); else return originals.paint(); };
tick = function(now) {
  if (!live()) return originals.tick(now);
  // The bootstrap already owns one animation chain. Do not create another.
  if (state === 'playing') {
    const delta = clock === null ? 0 : Math.max(0, (now - clock) / 1000);
    clock = now;
    const candidate = Math.min(duration, position + delta);
    const end = adapter.bufferedUntil(sourceTime());
    if (end == null || metadata.source_start + candidate >= end - 1e-7) {
      // Never move the clock/picture beyond available data during underflow.
      if (status?.state === 'complete' && candidate >= duration - 1e-7 &&
          end != null && end >= metadata.source_start + duration - 1e-7) {
        presented = adapter.frameAt(metadata.source_start + (status.total_frames - 1) / metadata.fps) || presented;
        position = duration; terminal('ended');
      } else { state = 'buffering'; clock = null; render(); announce('BUFFERING'); }
    } else {
      const next = adapter.frameAt(metadata.source_start + candidate);
      if (next) { position = candidate; presented = next; render(); }
      else { state = 'buffering'; clock = null; render(); announce('BUFFERING'); }
    }
  } else clock = null;
  requestAnimationFrame(tick);
};
load = function(entry, keep = false, options = {}) {
  if (entry?.id === ENTRY && entry.playback_type === 'local-stream') return start(entry);
  if (!live()) { ++generation; return originals.load(entry, keep, options); }
  const operation = exit(), g = generation;
  return operation.then(() => {
    if (g !== generation || live()) return;
    return originals.load(entry, keep, options);
  }, () => { announce('Stop cleanup failed. Static load cancelled; retry explicitly.'); });
};
select = function() { if (live()) { void exit().catch(() => {}); return; } ++generation; return originals.select(); };
back = function() { if (live()) { void exit().catch(() => {}); return; } ++generation; return originals.back(); };
key = function(value) {
  if (!live()) { ++generation; return originals.key(value); }
  if (value === '5') return select();
  if (value === '*') { void exit(true).catch(() => {}); return; }
  if (value === '#') return originals.key(value);
  const labels = {'0':'Quality', '1':'Info', '2':'Caption toggle', '3':'Sharing', '4':'Seek', '6':'Seek', '7':'LCD/ASCII switch'};
  announce((labels[value] || 'Control ' + value) + ' unavailable in live mode.');
};
// Intercept input origins before the old document numeric mapping.
function controlEvent(event) {
  if (!live()) return;
  const target = event.target.closest?.('.handset-up,.handset-down,.roller-up,.roller-down,.handset-roller,.nav [data-key]');
  if (!target) return;
  if (event.type === 'wheel' && (event.ctrlKey || event.metaKey)) return;
  event.preventDefault(); event.stopImmediatePropagation();
  if (event.type === 'wheel') { announce('Navigation unavailable in live mode.'); return; }
  if (target.classList?.contains('roller-press') || target.dataset?.key === '5' ||
      event.target.closest?.('.roller-press')) select();
  else announce('Navigation unavailable in live mode.');
}
document.addEventListener('click', controlEvent, true);
document.addEventListener('wheel', controlEvent, {capture:true, passive:false});
document.addEventListener('keydown', event => {
  if (!live() || !event.key.startsWith('Arrow') || event.altKey || event.ctrlKey || event.metaKey ||
      event.target.closest?.('dialog,.handset-tools')) return;
  event.preventDefault(); event.stopImmediatePropagation();
  announce('Navigation unavailable in live mode.');
}, true);
document.addEventListener('visibilitychange', () => { if (document.hidden && live()) void exit().catch(() => {}); });
window.addEventListener('pagehide', () => { if (live()) void exit().catch(() => {}); });
// Read-only diagnostic snapshot: no capability or mutable adapter is exposed.
window.wapflixLive = Object.freeze({snapshot: () => Object.freeze({state, generation,
  position, presentedSourceTime: presented?.sourceTime ?? null,
  presentedFrameIndex: presented?.frameIndex ?? null, duration,
  pollTimer: timer !== null, cleanupPending: cleanup !== null,
  cleanupUnconfirmed: cleanupError !== null})});
})();
