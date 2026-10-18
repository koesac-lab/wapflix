(() => {
'use strict';
const THEMES = [['3310','NOKIA 3310'],['8210','NOKIA 8210'],['6310','NOKIA 6310'],['7110','NOKIA 7110'],['3210','NOKIA 3210']];
const KEY = 'wapflix-handset';
const phone = document.querySelector('.phone');
if (!phone || phone.dataset.handsetReady) return;
const left = document.getElementById('left');
const right = document.getElementById('back');
const keypad = phone.querySelector('.keypad');
if (!left || !right || !keypad) return;
phone.dataset.handsetReady = 'true';
let index = 0;
try { const at = THEMES.findIndex(t => t[0] === localStorage.getItem(KEY)); if (at >= 0) index = at; } catch {}
const oldSoft = phone.querySelector('.softkeys');
const oldNav = phone.querySelector('.nav');
const deck = document.createElement('div');
deck.className = 'handset-controls';
deck.setAttribute('role', 'group');
deck.setAttribute('aria-label', 'Handset controls');
oldSoft.before(deck);
// Retain these exact elements: footer() updates their accessible names.
deck.append(left, right);
oldSoft.remove();
oldNav?.remove();
const stage = document.createElement('div');
stage.className = 'handset-keypad-stage';
keypad.before(stage);
stage.append(keypad);
const cover = document.createElement('button');
cover.type = 'button';
cover.className = 'handset-slider-cover';
cover.innerHTML = '<span class="slider-grip" aria-hidden="true"></span><span class="slider-caption">SLIDE TO CLOSE</span>';
stage.append(cover);
let closed = false;
function setCover(value) {
  closed = value;
  phone.classList.toggle('slider-closed', closed);
  keypad.inert = closed;
  if (closed) keypad.setAttribute('aria-hidden','true'); else keypad.removeAttribute('aria-hidden');
  cover.setAttribute('aria-expanded', String(!closed));
  cover.setAttribute('aria-label', closed ? 'Slide open to reveal keypad' : 'Slide closed to cover keypad');
  cover.querySelector('.slider-caption').textContent = closed ? 'SLIDE TO OPEN' : 'SLIDE TO CLOSE';
}
cover.onclick = () => setCover(!closed);
keypad.id = keypad.id || 'handset-keypad';
cover.setAttribute('aria-controls', keypad.id);
// Dial legends belong on the keys; app shortcuts belong in the help text.
const legends = {'1':'','2':'ABC','3':'DEF','4':'GHI','5':'JKL','6':'MNO','7':'PQRS','8':'TUV','9':'WXYZ','0':'+'};
keypad.querySelectorAll('[data-key]').forEach(button => {
  const value = button.dataset.key;
  if (!(value in legends)) return;
  button.textContent = value;
  if (legends[value]) { const small = document.createElement('small'); small.textContent = legends[value]; button.append(small); }
});
const model = document.createElement('span');
model.className = 'handset-model';
model.setAttribute('aria-hidden','true');
phone.querySelector('.brand')?.append(model);
const picker = document.createElement('label');
picker.className = 'handset-picker';
const pickerText = document.createElement('span');
pickerText.textContent = 'HANDSET';
const selectModel = document.createElement('select');
selectModel.setAttribute('aria-label','Choose handset model');
THEMES.forEach(([id,name]) => { const option = document.createElement('option'); option.value = id; option.textContent = name; selectModel.append(option); });
picker.append(pickerText, selectModel);
phone.after(picker);
const hint = phone.querySelector('.legend');
if (hint) hint.innerHTML = '2 / 8 SCROLL · 5 SELECT · 4 / 6 SEEK<br>1 INFO · 3 SHARE · 0 QUALITY · * HOME · # LIGHT';
function run(action) {
  if (action === 'select') { if (typeof select === 'function') select(); }
  else if (action === 'back') { if (typeof back === 'function') back(); }
  else if (action === 'home') { if (typeof key === 'function') key('*'); }
  else if (typeof key === 'function') key(action);
}
function button(label, className, action, title) {
  const b = document.createElement('button'); b.type = 'button';
  b.className = 'key handset-extra ' + className;
  b.textContent = label; b.setAttribute('aria-label',title);
  if (className === 'handset-call' || className === 'handset-end') {
    b.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M6.6 10.8a15.4 15.4 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1.1-.2 1.2.4 2.5.6 3.8.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.7 21 3 13.3 3 3.7c0-.6.4-1 1-1h3.4c.6 0 1 .4 1 1 0 1.3.2 2.6.6 3.8.1.4 0 .8-.2 1.1z"/></svg>';
  }
  b.onclick = () => run(action); return b;
}
function rocker() {
  const r = document.createElement('div'); r.className = 'handset-rocker handset-extra';
  r.append(button('⌃','handset-up','2','Scroll up'),button('⌄','handset-down','8','Scroll down'));
  return r;
}
function roller() {
  const r = document.createElement('div'); r.className = 'handset-roller handset-extra';
  r.setAttribute('role','group'); r.setAttribute('aria-label','Navi roller: scroll to browse, press to select');
  r.append(button('⌃','roller-up','2','Roll up'),button('','roller-press','select','Press roller to select or play and pause'),button('⌄','roller-down','8','Roll down'));
  let accumulated = 0;
  r.addEventListener('wheel', e => {
    if (e.ctrlKey || e.metaKey || !e.deltaY) return;
    e.preventDefault();
    accumulated += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 100 : 1);
    if (Math.abs(accumulated) >= 24) { run(accumulated > 0 ? '8' : '2'); accumulated = 0; }
  }, {passive:false});
  return r;
}
function apply() {
  const id = THEMES[index][0];
  const focused = document.activeElement;
  const restoreFocus = deck.contains(focused) && focused !== left && focused !== right;
  document.body.classList.remove(...THEMES.map(t => 'handset-' + t[0]));
  document.body.classList.add('handset-' + id);
  phone.dataset.handset = id;
  phone.setAttribute('aria-label', 'WAPFLIX pocket cinema, Nokia ' + id + ' inspired handset');
  deck.querySelectorAll('.handset-extra').forEach(el => el.remove());
  left.className = 'key handset-select'; right.className = 'key handset-back';
  left.type = right.type = 'button';
  const single = id === '3310' || id === '3210';
  deck.className = 'handset-controls ' + (single ? 'controls-navi' : id === '7110' ? 'controls-roller' : 'controls-dual');
  left.textContent = single ? '—' : '−'; right.textContent = single ? 'C' : '−';
  // C really means back. Dual softkeys retain the context-sensitive right action.
  right.onclick = single ? () => run('back') : originalRight;
  right.setAttribute('aria-label', single ? 'Back (C)' : rightContext);
  if (single) deck.append(rocker());
  else {
    deck.append(button('╱','handset-call','select','Select or play and pause'));
    deck.append(id === '7110' ? roller() : rocker());
    deck.append(button('╱','handset-end','home','Return home'));
  }
  cover.hidden = id !== '7110'; setCover(false);
  model.textContent = id;
  selectModel.value = id;
  if (restoreFocus) left.focus({preventScroll:true});
  try { localStorage.setItem(KEY,id); } catch {}
}
const originalRight = right.onclick;
let rightContext = right.getAttribute('aria-label') || 'Back';
new MutationObserver(() => {
  const label = right.getAttribute('aria-label');
  if (label !== 'Back (C)') rightContext = label || 'Back';
  if (['3310','3210'].includes(THEMES[index][0]) && label !== 'Back (C)') right.setAttribute('aria-label','Back (C)');
}).observe(right, {attributes:true,attributeFilter:['aria-label']});
function set(id) { const at = THEMES.findIndex(t => t[0] === id); if (at < 0) return false; index = at; apply(); return true; }
function cycle() { index = (index + 1) % THEMES.length; apply(); return THEMES[index][1]; }
selectModel.onchange = () => set(selectModel.value);
selectModel.addEventListener('keydown', event => event.stopPropagation());
window.wapflixHandset = { cycle, set, current: () => THEMES[index][1] };
apply();
})();
