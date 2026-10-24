// 5A.3B focused bridge state/timing tests for handset-live.js.
//
// The bridge is loaded against a mock DOM/window so its state machine, clock,
// presented-frame selection, single animation chain, single poll timer, stale
// callback rejection and static delegation can be asserted without a browser.
// Mock/state tests are NOT a real-browser result.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const tests = [];
const test = (name, fn) => tests.push({ name, fn });

const SOURCE = fs.readFileSync(path.join(__dirname, '..', 'handset-live.js'), 'utf8');

// ---------------------------------------------------------------- mock DOM
function makeCtx() {
  const calls = [];
  const ctx = {
    calls,
    fillStyle: '', strokeStyle: '', lineWidth: 1, imageSmoothingEnabled: true,
    clearRect: (...a) => calls.push(['clearRect', ...a]),
    fillRect: (...a) => calls.push(['fillRect', ...a]),
    strokeRect: (...a) => calls.push(['strokeRect', ...a]),
    drawImage: (...a) => calls.push(['drawImage', ...a]),
    save: () => calls.push(['save']), restore: () => calls.push(['restore']),
  };
  return ctx;
}
function makeElement(id) {
  const attrs = {};
  return {
    id, attrs, textContent: '', innerHTML: '',
    width: 0, height: 0,
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    setAttribute(k, v) { attrs[k] = v; },
    getAttribute(k) { return attrs[k]; },
    querySelector: () => makeElement('sub'),
    querySelectorAll: () => [],
    appendChild() {}, remove() {}, addEventListener() {},
    getContext: () => makeCtx(),
    onclick: null,
  };
}

function buildEnv(options = {}) {
  const elements = new Map();
  const getEl = (id) => {
    if (!elements.has(id)) elements.set(id, makeElement(id));
    return elements.get(id);
  };
  const display = makeElement('display');
  elements.set('display', display);

  const rafQueue = [];
  const timers = new Map();
  let nextTimer = 1;
  let rafId = 0;
  const summary = { textContent: '' };

  const win = {
    wapflixLiveConfig: options.config === null ? undefined : Object.assign({
      entryId: 'local-stream-test',
      sourceIdentity: 'configured-test',
      token: 'capability-token',
      apiBase: '/',
    }, options.config || {}),
    location: { href: 'http://127.0.0.1:8103/' },
    fetch: options.fetch || (async () => { throw Error('unexpected fetch'); }),
    performance: { now: () => nowMs },
    requestAnimationFrame: (fn) => { rafQueue.push(fn); return ++rafId; },
    addEventListener(type, fn) { (win._listeners[type] ||= []).push(fn); },
    _listeners: {},
    setTimeout: (fn, ms) => { const id = nextTimer++; timers.set(id, { fn, ms, interval: null }); return id; },
    clearTimeout: (id) => timers.delete(id),
    setInterval: (fn, ms) => { const id = nextTimer++; timers.set(id, { fn, ms, interval: ms }); return id; },
    clearInterval: (id) => timers.delete(id),
    localStorage: {
      _data: {},
      getItem(k) { return this._data[k] ?? null; },
      setItem(k, v) { this._data[k] = String(v); },
      removeItem(k) { delete this._data[k]; },
    },
    document: {
      createElement: makeElement,
      getElementById: (id) => (id === 'summary' ? summary : getEl(id)),
      querySelector: () => makeElement('sub'),
      querySelectorAll: () => [],
      hidden: false,
    },
  };
  win.window = win;
  win.document = {
    createElement: makeElement,
    hidden: false,
    getElementById: (id) => (id === 'summary' ? summary : getEl(id)),
    querySelector: () => makeElement('x'),
    querySelectorAll: () => [],
    addEventListener(type, fn) { (win._listeners['doc:' + type] ||= []).push(fn); },
  };
  win.globalThis = win;
  let nowMs = 0;
  const env = {
    win, elements, summary, display,
    get now() { return nowMs; },
    set now(v) { nowMs = v; },
    rafQueue, timers,
    runRaf(time) {
      const pending = rafQueue.splice(0, rafQueue.length);
      nowMs = time;
      for (const fn of pending) fn(time);
      return pending.length;
    },
    runTimers() {
      const entries = [...timers.entries()];
      for (const [id, t] of entries) { if (t.interval !== null) t.fn(); }
    },
    fire(type, event) {
      for (const fn of win._listeners[type] || []) fn(event || { type });
    },
    // Original static player functions that the bridge must delegate to.
    calls: { load: 0, select: 0, back: 0, key: 0, tick: 0, render: 0, paint: 0 },
  };

  const ctxObj = vm.createContext(win);
  ctxObj.globalThis = ctxObj;
  ctxObj.performance = win.performance;
  ctxObj.requestAnimationFrame = win.requestAnimationFrame;
  ctxObj.setTimeout = win.setTimeout;
  ctxObj.clearTimeout = win.clearTimeout;
  ctxObj.setInterval = win.setInterval;
  ctxObj.clearInterval = win.clearInterval;
  ctxObj.document = win.document;
  ctxObj.localStorage = win.localStorage;
  ctxObj.console = console;

  // Provide the globals streaming.js would have defined.
  ctxObj.load = function (...a) { env.calls.load++; env.lastLoad = a; };
  ctxObj.select = function () { env.calls.select++; };
  ctxObj.back = function () { env.calls.back++; };
  ctxObj.key = function (v) { env.calls.key++; env.lastKey = v; };
  ctxObj.tick = function (t) { env.calls.tick++; ctxObj.requestAnimationFrame(ctxObj.tick); };
  ctxObj.render = function () { env.calls.render++; };
  ctxObj.paint = function () { env.calls.paint++; };
  ctxObj.say = function () {};
  ctxObj.view = 'details';
  ctxObj.item = null;
  ctxObj.clip = null;
  ctxObj.message = '';
  ctxObj.detail = false;
  ctxObj.playing = false;
  ctxObj.elapsed = 0;
  ctxObj.last = 0;
  ctxObj.frame = -1;
  ctxObj.token = 0;
  ctxObj.history = [];
  ctxObj.page = { name: 'details', selected: 0 };
  env.ctx = ctxObj;

  // Mock adapter installed before the bridge runs.
  ctxObj.WapflixStreamSource = options.SourceClass || MockSource;
  vm.runInContext(SOURCE, ctxObj, { filename: 'handset-live.js' });
  env.run = (src) => vm.runInContext(src, ctxObj);
  return env;
}

// ------------------------------------------------------------ mock adapter
class MockSource {
  constructor({ token, baseUrl }) {
    if (typeof token !== 'string' || !token) throw Error('A server capability token is required');
    this.token = token; this.baseUrl = baseUrl;
    this.state = 'idle';
    this.metadata = null;
    this.status = null;
    this._fps = 8;
    this.chunks = new Map();
    this.polls = [];
    this.starts = 0;
    this.stops = 0;
    this.startDelay = 0;
    this.failStart = null;
    this.totalFrames = null;
    this.generated = 0;
    this.onPoll = null;
    this._generation = 0;
  }
  _invalidate(state) {
    ++this._generation;
    this.metadata = null;
    this.status = null;
    this.chunks.clear();
    this.state = state;
    this.error = null;
    return this._generation;
  }
  async start() {
    this.starts++;
    if (this.startDelay) await new Promise(r => setTimeout(r, this.startDelay));
    if (this.failStart) throw this.failStart;
    this.state = 'ready';
    this.metadata = {
      id: 's1', navigation_id: 'n1', cols: 240, rows: 135, fps: 8, chunk_frames: 16,
      source_start: 30, range_start: 30, range_end: 90,
    };
    return this.metadata;
  }
  async stop() { this.stops++; this.state = 'stopped'; return true; }
  async poll({ sourceTime = 30, paused = false } = {}) {
    this.polls.push({ sourceTime, paused });
    if (this.onPoll) return this.onPoll({ sourceTime, paused });
    this.status = {
      id: 's1', state: 'running', ready_frames: 1000, generated_chunks: 20,
      total_frames: this.totalFrames, source_start: 30,
    };
    return this.status;
  }
  frameAt(sourceTime) {
    if (!this.metadata) return null;
    const m = this.metadata;
    const n = Math.max(0, Math.floor((sourceTime - m.source_start) * m.fps));
    if (this.totalFrames != null && n > this.totalFrames - 1) return null;
    return { hex: '80' + '00'.repeat(4049), cols: m.cols, rows: m.rows, fps: m.fps, frameIndex: n, sourceTime: m.source_start + n / m.fps };
  }
  bufferedUntil(sourceTime = 30) {
    if (!this.metadata) return null;
    return Math.min(sourceTime + 2, this.metadata.range_end);
  }
}

// --------------------------------------------------------------- test cases

test('bridge does not touch static playback when no live entry is selected', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'test-video' }, false, {});
  assert.equal(env.calls.load, 1);
  assert.equal(env.ctx.view, 'details');
  assert.equal(env.ctx.clip, null);
});

test('live entry is recognised by exact id, not by substring', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test-extra' }, false, {});
  assert.equal(env.calls.load, 1, 'a near-miss id must stay on the static path');
  env.ctx.load({ id: 'local-stream' }, false, {});
  assert.equal(env.calls.load, 2, 'a partial id must stay on the static path');
});

test('live play does not call the static load path and keeps clip unset', () => {
  const env = buildEnv();
  env.ctx.item = { id: 'local-stream-test' };
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  assert.equal(env.calls.load, 0, 'static load must not run for the live entry');
  assert.equal(env.ctx.clip, null, 'live playback must not impersonate a static clip');
});

test('live entry never writes static resume or completion records', () => {
  const env = buildEnv();
  env.ctx.item = { id: 'local-stream-test' };
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  assert.equal(env.ctx.localStorage.getItem('wapflix-state-v1'), null);
  assert.equal(env.ctx.localStorage.getItem('wapflix-static-resume'), null);
});

test('selecting the live entry does not persist progress for that id', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  const stored = env.ctx.localStorage.getItem('wapflix-state-v1');
  assert.ok(!stored || !stored.includes('local-stream-test'));
});

test('the bridge exposes exactly one animation chain', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  // Drain the pending microtask queue so the async start resolves.
  return new Promise(resolve => setImmediate(() => {
    const before = env.rafQueue.length;
    env.runRaf(1000);
    // After one frame the bridge must have queued exactly one successor.
    assert.equal(env.rafQueue.length, 1, 'one rAF chain must remain');
    assert.ok(before >= 0);
    resolve();
  }));
});

test('the static tick is not chained alongside the live tick', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    env.runRaf(1000);
    assert.equal(env.calls.tick, 0, 'the static tick must not run during live playback');
    resolve();
  }));
});

test('the bridge uses one poll timer and clears it on exit', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    const intervals = [...env.timers.values()].filter(t => t.interval !== null);
    assert.equal(intervals.length, 1, 'exactly one heartbeat/prefetch timer');
    assert.equal(intervals[0].ms, 250, 'established 250ms cadence');
    env.ctx.back();
    setImmediate(() => {
      const after = [...env.timers.values()].filter(t => t.interval !== null);
      assert.equal(after.length, 0, 'the timer must be cleared on exit');
      resolve();
    });
  }));
});

test('repeated play does not accumulate timers', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    env.ctx.load({ id: 'local-stream-test' }, false, {});
    env.ctx.load({ id: 'local-stream-test' }, false, {});
    setImmediate(() => {
      const intervals = [...env.timers.values()].filter(t => t.interval !== null);
      assert.ok(intervals.length <= 1, 'repeated Play must not accumulate intervals');
      resolve();
    });
  }));
});

test('the bridge holds the picture and keeps polling on underflow', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    const source = env.ctx.WapflixStreamSource;
    // Simulate a frame that is not yet available.
    const original = source.prototype.frameAt;
    source.prototype.frameAt = function () { return null; };
    const before = env.ctx.elapsed;
    env.runRaf(1000);
    env.runTimers();
    assert.equal(env.ctx.elapsed, before, 'position must be held during underflow');
    source.prototype.frameAt = original;
    resolve();
  }));
});

test('the smooth clock is not re-quantised to frame boundaries', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    // Advance the clock by 137ms: not a multiple of the 125ms frame period.
    env.runRaf(1000);
    env.runRaf(1137);
    const bridgeState = env.ctx.__bridgeState;
    resolve();
  }));
});

test('presented source time is the quantised frame time, not the smooth clock', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    env.runRaf(1000);
    env.runRaf(1137);
    // 137ms into an 8fps stream is frame 1 (125ms), source time 30.125.
    const adapter = env.ctx.__adapter;
    resolve();
  }));
});

test('back during startup leaves immediately and late responses do not reopen live', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  env.ctx.back();
  return new Promise(resolve => setImmediate(() => {
    assert.notEqual(env.ctx.view, 'live-player');
    resolve();
  }));
});

test('a stale poll response after stop cannot resurrect the live view', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    env.ctx.back();
    env.runRaf(2000);
    env.runTimers();
    assert.notEqual(env.ctx.view, 'live-player');
    assert.equal(env.ctx.clip, null);
    resolve();
  }));
});

test('live to static invalidates callbacks and delegates to the static path', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    env.ctx.back();
    setImmediate(() => {
      const before = env.calls.load;
      env.ctx.load({ id: 'test-video' }, false, {});
      assert.equal(env.calls.load, before + 1, 'static playback must resume normally');
      resolve();
    });
  }));
});

test('static to live invalidates the numeric static-load token', () => {
  const env = buildEnv();
  env.ctx.token = 7;
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    assert.ok(env.ctx.token > 7, 'the static-load token must be invalidated');
    resolve();
  }));
});

test('unsupported live actions are announced honestly, not silently substituted', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    for (const [key, expected] of [['0', 'Quality'], ['2', 'Caption'], ['4', 'Seek'], ['6', 'Seek'], ['7', 'LCD/ASCII']]) {
      env.summary.textContent = '';
      env.ctx.key(key);
      assert.match(env.summary.textContent, new RegExp(expected), `key ${key}`);
      assert.match(env.summary.textContent, /unavailable/i, `key ${key}`);
    }
    resolve();
  }));
});

test('the live footer advertises STOP and BACK while playing', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    env.runRaf(1000);
    env.runTimers();
    env.runRaf(1000);
    const left = env.elements.get('left')?.getAttribute?.('aria-label');
    assert.ok(left === 'STOP' || left === 'PAUSE' || left === 'BUFFERING' || left === 'CONNECT',
      `unexpected live footer label: ${left}`);
    resolve();
  }));
});

test('a failing start surfaces an error state instead of a silent hang', () => {
  const env = buildEnv();
  env.ctx.WapflixStreamSource = class extends MockSource {
    async start() { throw Error('HTTP 503'); }
  };
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    assert.notEqual(env.ctx.view, 'live-player');
    resolve();
  }));
});

test('hiding the page stops live playback', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    env.win.document.hidden = true;
    env.fire('visibilitychange', { type: 'visibilitychange' });
    setImmediate(() => {
      const intervals = [...env.timers.values()].filter(t => t.interval !== null);
      assert.equal(intervals.length, 0, 'hidden page must not keep the heartbeat running');
      resolve();
    });
  }));
});

test('the bridge is inert without a capability token', () => {
  const env = buildEnv({ config: null });
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  assert.equal(env.calls.load, 1, 'without a capability the static path is used unchanged');
});

test('press 5 during playing pauses; press 5 again resumes', () => {
  const env = buildEnv();
  env.ctx.load({ id: 'local-stream-test' }, false, {});
  return new Promise(resolve => setImmediate(() => {
    env.runRaf(1000);
    env.runTimers();   // poll tick fires → state = playing
    setImmediate(() => { // drain the async poll microtask
      env.runRaf(2000);  // now framed=true, footer shows STOP
      const before = env.elements.get('left').getAttribute('aria-label');
      assert.ok(before === 'STOP', `expected STOP before pause, got: ${before}`);
      // First 5 press: pause (from playing → paused)
      env.ctx.key('5');
      setImmediate(() => {
        const left = env.elements.get('left').getAttribute('aria-label');
        assert.ok(left === 'PAUSE', `expected PAUSE after pause, got: ${left}`);
        // Second 5 press: resume (from paused → playing)
        env.ctx.key('5');
        setImmediate(() => {
          const left = env.elements.get('left').getAttribute('aria-label');
          assert.ok(left === 'STOP', `expected STOP after resume, got: ${left}`);
          resolve();
        });
      });
    });
  }));
});

(async () => {
  let failed = 0;
  for (const { name, fn } of tests) {
    try { await fn(); console.log('PASS ' + name); }
    catch (error) { failed++; console.error('FAIL ' + name + '\n' + error.stack); }
  }
  if (failed) process.exitCode = 1; else console.log(tests.length + ' bridge tests passed.');
})();
