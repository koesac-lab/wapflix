(() => {
'use strict';
const STORE = 'wapflix-state-v1';
let state = { progress: {}, list: [], autoplayNext: true };
try {
  const saved = JSON.parse(localStorage.getItem(STORE) || 'null');
  if (saved && typeof saved === 'object') {
    state = { ...state, ...saved };
    state.progress = saved.progress && typeof saved.progress === 'object' ? saved.progress : {};
    state.list = Array.isArray(saved.list) ? saved.list : [];
  }
} catch (error) {}
let saveTimer = 0;
function persist() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => { try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (error) {} }, 200);
}
const playerRender = render, baseKey = key, baseSelect = select, baseBack = back, baseLoad = load, baseTick = tick;
let homeIndex = 0, seriesListIndex = 0, seriesAction = 0, detailAction = 0, optionIndex = 0, returnView = 'episodes', ended = null, lastSave = 0;
const allItems = () => groups.flatMap(entry => entry.items);
const findItem = id => allItems().find(entry => entry.id === id);
const inList = id => state.list.includes(id);
const duration = () => clip ? clip.frames.length / clip.fps : 0;
function toggleList(id) {
  const at = state.list.indexOf(id);
  if (at >= 0) state.list.splice(at, 1); else state.list.unshift(id);
  persist();
}
function remember() {
  if (!item || !clip) return;
  const total = duration();
  if (elapsed > 3 && elapsed < total - 2) {
    state.progress[item.id] = { elapsed: Math.floor(elapsed), at: Date.now(), duration: total };
    persist();
  } else if (elapsed >= total - 2) {
    delete state.progress[item.id];
    persist();
  }
}
function resumeEntries() {
  return Object.entries(state.progress)
    .map(([id, saved]) => { const found = findItem(id); return found ? { item: found, ...saved } : null; })
    .filter(entry => entry && entry.elapsed > 3 && entry.elapsed < entry.duration - 2)
    .sort((a, b) => b.at - a.at);
}
const seriesGroups = () => groups.filter(entry => entry.items.some(candidate => candidate.series));
const originalGroup = () => groups.findIndex(entry => !entry.items.some(candidate => candidate.series));
function homeItems() {
  const items = resumeEntries().slice(0, 3).map(entry => ({ kind: 'resume', item: entry.item, elapsed: entry.elapsed, duration: entry.duration }));
  if (seriesGroups().length) items.push({ kind: 'series' });
  const original = originalGroup();
  if (original >= 0) items.push({ kind: 'original', group: original });
  items.push({ kind: 'mylist' }, { kind: 'options' });
  return items;
}
function homeLabel(entry) {
  if (entry.kind === 'resume') return entry.item.episode_title || entry.item.title;
  if (entry.kind === 'series') return 'SERIES';
  if (entry.kind === 'original') return 'ORIGINAL TRANSMISSIONS';
  if (entry.kind === 'mylist') return 'MY LIST (' + state.list.length + ')';
  return 'OPTIONS';
}
function episodeLabel(entry) {
  const title = entry.episode_title || entry.title;
  return (entry.episode ? 'E' + String(entry.episode).padStart(2, '0') + ' ' : '') + title;
}
function menuItem(label, n, selected, suffix = '') {
  const y = 30 + n * 16;
  const room = suffix ? 34 - suffix.length : 37;
  const line = (selected ? '> ' : '  ') + String(label).slice(0, room);
  if (selected) {
    ctx.fillStyle = ink;
    ctx.fillRect(0, y - 4, 240, 15);
    ctx.save();
    ctx.globalCompositeOperation = 'destination-out';
    text(line, 5, y);
    if (suffix) text(suffix, 237 - suffix.length * 6, y);
    ctx.restore();
  } else {
    text(line, 5, y);
    if (suffix) text(suffix, 237 - suffix.length * 6, y);
  }
}
function progressBar(x, y, width, fraction) {
  ctx.strokeStyle = ink;
  ctx.strokeRect(x + 0.5, y + 0.5, width - 1, 5);
  ctx.fillRect(x + 1, y + 1, Math.max(0, Math.round((width - 2) * Math.min(1, fraction))), 4);
}
function homeRender() {
  header();
  center('POCKET CINEMA', 24);
  const items = homeItems();
  homeIndex = Math.min(homeIndex, Math.max(0, items.length - 1));
  items.forEach((entry, n) => {
    const selected = n === homeIndex;
    if (entry.kind === 'resume') menuItem(homeLabel(entry), n, selected, Math.round(entry.elapsed / entry.duration * 100) + '%');
    else menuItem(homeLabel(entry), n, selected);
  });
  footer('OPEN', 'OPTIONS');
}
function seriesListRender() {
  header();
  center('SERIES', 24);
  const list = seriesGroups();
  if (!list.length) { center('NO SERIES YET', 100); footer('BACK', 'BACK'); return; }
  seriesListIndex = Math.min(seriesListIndex, list.length - 1);
  list.forEach((entry, n) => menuItem(entry.name, n, n === seriesListIndex, entry.items.length + ' EP'));
  footer('OPEN', 'BACK');
}
function seriesActions() {
  const resume = resumeEntries().find(entry => groups[group].items.some(candidate => candidate.id === entry.item.id));
  return [resume ? 'RESUME' : 'PLAY', 'EPISODES'];
}
function seriesRender() {
  header();
  const current = groups[group];
  center(current.name.slice(0, 38), 24);
  center('SEASON ' + String(current.items[0].season || 1).padStart(2, '0') + ' / ' + current.items.length + ' EPISODES', 38);
  wrap(current.items[0].description || '', 38).slice(0, 3).forEach((line, n) => text(line, 5, 56 + n * 11));
  const resume = resumeEntries().find(entry => current.items.some(candidate => candidate.id === entry.item.id));
  if (resume) text('NEXT: ' + (resume.item.episode_title || resume.item.title).slice(0, 30), 5, 96);
  const actions = seriesActions();
  seriesAction = Math.min(seriesAction, actions.length - 1);
  actions.forEach((label, n) => menuItem(label, n + 5, n === seriesAction));
  footer('SELECT', 'BACK');
}
function episodesRender() {
  header();
  const current = groups[group];
  center(current.name.slice(0, 38), 24);
  const items = current.items;
  index = Math.min(index, items.length - 1);
  const start = Math.floor(index / 6) * 6;
  items.slice(start, start + 6).forEach((entry, n) => {
    const selected = start + n === index;
    const saved = state.progress[entry.id];
    let suffix = '';
    if (saved) {
      if (saved.elapsed >= saved.duration - 2) suffix = 'SEEN';
      else if (saved.elapsed > 3) suffix = Math.round(saved.elapsed / saved.duration * 100) + '%';
    }
    menuItem(episodeLabel(entry), n, selected, suffix);
    if (selected && saved && saved.elapsed > 3 && saved.elapsed < saved.duration - 2) progressBar(5, 30 + n * 16 + 10, 230, saved.elapsed / saved.duration);
  });
  text((index + 1) + '/' + items.length, 3, 193);
  footer('DETAILS', 'BACK');
}
function mylistRender() {
  header();
  center('MY LIST', 24);
  const items = state.list.map(findItem).filter(Boolean);
  if (!items.length) {
    center('NOTHING SAVED YET', 90);
    text('OPEN A TRANSMISSION AND', 5, 110);
    text('CHOOSE ADD TO MY LIST.', 5, 122);
    footer('BACK', 'BACK');
    return;
  }
  index = Math.min(index, items.length - 1);
  items.forEach((entry, n) => menuItem(episodeLabel(entry), n, n === index));
  footer('DETAILS', 'BACK');
}
function detailActions() {
  const saved = state.progress[item.id];
  return [saved && saved.elapsed > 3 && saved.elapsed < saved.duration - 2 ? 'RESUME' : 'PLAY', inList(item.id) ? 'REMOVE FROM MY LIST' : 'ADD TO MY LIST'];
}
function detailsRender() {
  header();
  center((item.episode_title || item.title).slice(0, 38), 24);
  wrap(item.description || '', 37).slice(0, 6).forEach((line, n) => text(line, 5, 42 + n * 11));
  const saved = state.progress[item.id];
  if (saved && saved.elapsed > 3 && saved.elapsed < saved.duration - 2) {
    progressBar(5, 118, 230, saved.elapsed / saved.duration);
    text(seconds(saved.elapsed) + ' / ' + seconds(saved.duration), 5, 128);
  }
  const actions = detailActions();
  detailAction = Math.min(detailAction, actions.length - 1);
  actions.forEach((label, n) => menuItem(label, n + 5, n === detailAction));
  footer('SELECT', 'BACK');
}
function optionsRender() {
  header();
  center('OPTIONS', 24);
  const rows = ['AUTOPLAY NEXT: ' + (state.autoplayNext ? 'ON' : 'OFF'), 'CONNECTION: ' + labels[quality], 'BACKLIGHT: ' + (lit ? 'ON' : 'OFF'), 'ABOUT WAPFLIX'];
  optionIndex = Math.min(optionIndex, rows.length - 1);
  rows.forEach((label, n) => menuItem(label, n + 2, n === optionIndex));
  footer('SELECT', 'BACK');
}
function endedRender() {
  header();
  center('TRANSMISSION ENDED', 40);
  if (ended && ended.next) {
    center('NEXT UP', 70);
    wrap(ended.next.episode_title || ended.next.title, 30).slice(0, 2).forEach((line, n) => center(line, 84 + n * 11));
    center('STARTING IN ' + Math.max(0, ended.remaining) + '...', 120);
    footer('PLAY NOW', 'CANCEL');
  } else {
    center('THANKS FOR WATCHING', 90);
    footer('REPLAY', 'EPISODES');
  }
}
function streamRender() {
  if (view === 'home') return homeRender();
  if (view === 'serieslist') return seriesListRender();
  if (view === 'series') return seriesRender();
  if (view === 'episodes') return episodesRender();
  if (view === 'mylist') return mylistRender();
  if (view === 'details') return detailsRender();
  if (view === 'options') return optionsRender();
  if (view === 'ended') return endedRender();
  header();
  center('POCKET CINEMA', 90);
  footer('BACK', 'BACK');
}
render = function() {
  if (view === 'player') return playerRender();
  streamRender();
};
function nextEpisode() {
  if (!item || !groups[group]) return null;
  const items = groups[group].items, at = items.findIndex(entry => entry.id === item.id);
  return at >= 0 && at + 1 < items.length ? items[at + 1] : null;
}
function startEnded(time) {
  remember();
  const next = nextEpisode();
  ended = next && state.autoplayNext ? { at: time, remaining: 5, next } : { at: 0, remaining: 0, next: null };
  view = 'ended';
  render();
  announce(next && state.autoplayNext ? 'Transmission ended. Next episode starting soon.' : 'Transmission ended.');
}
select = function() {
  if (!groups.length) return baseSelect();
  if (view === 'home') {
    const entry = homeItems()[homeIndex];
    if (!entry) return;
    if (entry.kind === 'resume') { returnView = 'home'; load(entry.item, false, { resume: true, autoplay: true }); return; }
    if (entry.kind === 'series') { view = 'serieslist'; seriesListIndex = 0; render(); announce('Series.'); return; }
    if (entry.kind === 'original') { group = entry.group; index = 0; view = 'episodes'; render(); announce(groups[group].name); return; }
    if (entry.kind === 'mylist') { view = 'mylist'; index = 0; render(); announce('My list.'); return; }
    view = 'options'; optionIndex = 0; render(); announce('Options.'); return;
  }
  if (view === 'serieslist') {
    const list = seriesGroups();
    if (!list.length) { back(); return; }
    group = groups.indexOf(list[seriesListIndex]);
    index = 0; view = 'series'; render(); announce(groups[group].name); return;
  }
  if (view === 'series') {
    const actions = seriesActions();
    seriesAction = Math.min(seriesAction, actions.length - 1);
    if (seriesAction === 0) {
      const resume = resumeEntries().find(entry => groups[group].items.some(candidate => candidate.id === entry.item.id));
      returnView = 'series';
      load(resume ? resume.item : groups[group].items[0], false, { resume: !!resume, autoplay: true });
      return;
    }
    view = 'episodes'; index = 0; render(); announce('Episodes.'); return;
  }
  if (view === 'episodes' || view === 'mylist') {
    const source = view === 'episodes' ? groups[group].items : state.list.map(findItem).filter(Boolean);
    const selected = source[index];
    if (!selected) return;
    item = selected; returnView = view; view = 'details'; detailAction = 0;
    render(); announce(selected.title); return;
  }
  if (view === 'details') {
    const actions = detailActions();
    detailAction = Math.min(detailAction, actions.length - 1);
    if (detailAction === 0) {
      const saved = state.progress[item.id];
      load(item, false, { resume: !!(saved && saved.elapsed > 3 && saved.elapsed < saved.duration - 2), autoplay: true });
      return;
    }
    toggleList(item.id);
    render(); announce(inList(item.id) ? 'Added to my list.' : 'Removed from my list.'); return;
  }
  if (view === 'options') {
    if (optionIndex === 0) { state.autoplayNext = !state.autoplayNext; persist(); }
    else if (optionIndex === 1) { quality = (quality + 1) % 3; }
    else if (optionIndex === 2) {
      lit = !lit;
      $('lcd').classList.toggle('dim', !lit);
      document.querySelector('[data-key="#"]').setAttribute('aria-pressed', String(lit));
    } else { previous = 'home'; view = 'about'; render(); announce('About pocket cinema.'); return; }
    render(); return;
  }
  if (view === 'ended') {
    const next = ended && ended.next;
    ended = null;
    load(next || item, false, { autoplay: true });
    return;
  }
  baseSelect();
};
back = function() {
  if (!groups.length) return baseBack();
  if (view === 'player') { remember(); ended = null; }
  if (view === 'home') { previous = 'home'; view = 'about'; render(); announce('About pocket cinema.'); return; }
  if (view === 'serieslist' || view === 'options' || view === 'mylist') { view = 'home'; render(); announce('Home.'); return; }
  if (view === 'series') { view = 'serieslist'; render(); announce('Series.'); return; }
  if (view === 'episodes') {
    if (groups[group].items.some(candidate => candidate.series)) { view = 'series'; render(); announce(groups[group].name); }
    else { view = 'home'; render(); announce('Home.'); }
    return;
  }
  if (view === 'details') { view = returnView; render(); announce(view === 'home' ? 'Home.' : 'Back.'); return; }
  if (view === 'ended') { ended = null; view = 'episodes'; render(); announce('Episodes.'); return; }
  baseBack();
  if (returnView === 'home') { view = 'home'; render(); announce('Home.'); return; }
  if (returnView === 'series') { view = 'series'; render(); announce(groups[group]?.name || 'Series.'); return; }
  if (returnView === 'mylist') { view = 'mylist'; render(); announce('My list.'); return; }
};
key = function(value) {
  if (value === '*') {
    if (!groups.length) return;
    ++token; setPlaying(false); clip = null; ended = null; view = 'home'; homeIndex = 0;
    render(); announce('Home.'); return;
  }
  if (view !== 'player' && (value === '4' || value === '6')) return;
  const up = value === '2', down = value === '8';
  if (view === 'home' && (up || down)) {
    const items = homeItems();
    homeIndex = (homeIndex + (up ? -1 : 1) + items.length) % items.length;
    render(); announce(homeLabel(items[homeIndex])); return;
  }
  if (view === 'serieslist' && (up || down)) {
    const list = seriesGroups();
    if (!list.length) return;
    seriesListIndex = (seriesListIndex + (up ? -1 : 1) + list.length) % list.length;
    render(); announce(list[seriesListIndex].name); return;
  }
  if (view === 'series' && (up || down)) {
    const actions = seriesActions();
    seriesAction = (seriesAction + (up ? -1 : 1) + actions.length) % actions.length;
    render(); return;
  }
  if ((view === 'episodes' || view === 'mylist') && (up || down)) {
    const source = view === 'episodes' ? groups[group].items : state.list.map(findItem).filter(Boolean);
    if (!source.length) return;
    index = Math.min(index, source.length - 1);
    index = (index + (up ? -1 : 1) + source.length) % source.length;
    render(); announce(source[index].title); return;
  }
  if (view === 'details' && (up || down)) {
    const actions = detailActions();
    detailAction = (detailAction + (up ? -1 : 1) + actions.length) % actions.length;
    render(); return;
  }
  if (view === 'options' && (up || down)) {
    optionIndex = (optionIndex + (up ? -1 : 1) + 4) % 4;
    render(); return;
  }
  baseKey(value);
};
load = function(selected, keep = false, options = {}) {
  ended = null;
  const pending = baseLoad(selected, keep);
  return Promise.resolve(pending).then(() => {
    if (view !== 'player' || item !== selected || !clip) return;
    if (options.resume) {
      const saved = state.progress[selected.id];
      if (saved) elapsed = Math.min(saved.elapsed, duration() - 0.001);
    }
    if (options.autoplay) {
      setPlaying(true);
      announce('Playing ' + (selected.episode_title || selected.title) + '.');
    }
    paint();
  });
};
tick = function(time) {
  baseTick(time);
  if (view === 'player' && clip && playing && time - lastSave > 2000) { remember(); lastSave = time; }
  if (view === 'player' && clip && !playing && elapsed >= duration() - 0.001 && message === '' && !ended) startEnded(time);
  if (ended && ended.at) {
    const remaining = Math.max(0, 5 - Math.floor((time - ended.at) / 1000));
    if (remaining !== ended.remaining) { ended.remaining = remaining; render(); }
    if (remaining === 0) {
      const next = ended.next;
      ended = null;
      view = 'player';
      load(next, false, { autoplay: true });
    }
  }
};
view = 'home';
render();
announce('Pocket cinema home. Use up and down, then select.');
})();
