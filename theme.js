/* WAPFLIX handset housings v6. No external fonts, images or dependencies. */
(() => {
'use strict';
const THEMES = [['3310','NOKIA 3310'],['8210','NOKIA 8210'],['6310','NOKIA 6310'],['7110','NOKIA 7110'],['3210','NOKIA 3210']];
const KEY = 'wapflix-handset';
const phone = document.querySelector('.phone');
const left = document.getElementById('left'), right = document.getElementById('back');
const keypad = phone?.querySelector('.keypad');
const oldSoft = phone?.querySelector('.softkeys');
if (!phone || !left || !right || !keypad || !oldSoft || phone.dataset.handsetReady) return;
phone.dataset.handsetReady = 'true';
let index = 0;
try { const at = THEMES.findIndex(t => t[0] === localStorage.getItem(KEY)); if (at >= 0) index = at; } catch {}
const originalRight = right.onclick;
let rightContext = right.getAttribute('aria-label') || 'Back';
const singleNavi = () => ['3310','3210'].includes(THEMES[index][0]);
const deck = document.createElement('div');
deck.className = 'handset-controls';
deck.setAttribute('role','group'); deck.setAttribute('aria-label','Handset controls');
oldSoft.before(deck); deck.append(left,right); oldSoft.remove();
phone.querySelector('.nav')?.remove();
const head = document.createElement('div'); head.className = 'handset-head';
const speaker = phone.querySelector('.speaker'), brand = phone.querySelector('.brand'), bezel = phone.querySelector('.bezel');
if (speaker && brand && bezel) {
  speaker.before(head); head.append(speaker,brand,bezel,deck);
  brand.textContent = 'NOKIA'; brand.setAttribute('aria-hidden','true');
}
const stage = document.createElement('div'); stage.className = 'handset-keypad-stage';
keypad.before(stage); stage.append(keypad); keypad.id ||= 'handset-keypad';
const cover = document.createElement('button'); cover.type = 'button';
cover.className = 'handset-slider-cover'; cover.setAttribute('aria-controls',keypad.id);
cover.innerHTML = '<span class="slider-grip" aria-hidden="true"></span><span class="slider-caption sr"></span><span class="slider-mic" aria-hidden="true"></span>';
stage.append(cover);
const microphone = document.createElement('span'); microphone.className = 'handset-microphone'; microphone.setAttribute('aria-hidden','true'); phone.append(microphone);
const antenna = document.createElement('span'); antenna.className = 'handset-antenna'; antenna.setAttribute('aria-hidden','true'); phone.prepend(antenna);
let closed = false;
function slideMetrics() { phone.style.setProperty('--slide-travel', Math.max(0,stage.getBoundingClientRect().height+15)+'px'); }
function setCover(value) {
  closed = value; phone.classList.toggle('slider-closed',closed); keypad.inert = closed;
  if (closed) keypad.setAttribute('aria-hidden','true'); else keypad.removeAttribute('aria-hidden');
  const label = closed ? 'Slide open to reveal keypad' : 'Slide closed to cover keypad';
  cover.setAttribute('aria-expanded',String(!closed)); cover.setAttribute('aria-label',label); cover.title = label;
  cover.querySelector('.slider-caption').textContent = label;
}
cover.onclick = () => setCover(!closed);
if ('ResizeObserver' in window) new ResizeObserver(slideMetrics).observe(stage);
else window.addEventListener('resize',slideMetrics);
const legends = {'1':'','2':'abc','3':'def','4':'ghi','5':'jkl','6':'mno','7':'pqrs','8':'tuv','9':'wxyz','0':'+'};
keypad.querySelectorAll('[data-key]').forEach(b => {
  const value = b.dataset.key, numeral = document.createElement('span'); numeral.className = 'key-numeral'; numeral.textContent = value;
  b.replaceChildren(numeral);
  if (legends[value]) { const small = document.createElement('small'); small.textContent = legends[value]; b.append(small); }
  if (value === '1') { const voicemail = document.createElement('span'); voicemail.className = 'key-voicemail'; voicemail.setAttribute('aria-hidden','true'); b.append(voicemail); }
});
const tools = document.createElement('div'); tools.className = 'handset-tools'; phone.after(tools);
const picker = document.createElement('label'); picker.className = 'handset-picker';
const pickerText = document.createElement('span'); pickerText.textContent = 'HANDSET';
const selectModel = document.createElement('select'); selectModel.setAttribute('aria-label','Choose handset model');
THEMES.forEach(([id,name]) => { const option = document.createElement('option'); option.value = id; option.textContent = name; selectModel.append(option); });
picker.append(pickerText,selectModel); tools.append(picker);
const help = document.createElement('details'); help.className = 'handset-help';
const helpSummary = document.createElement('summary'); helpSummary.textContent = 'Keypad shortcuts'; help.append(helpSummary);
const hint = phone.querySelector('.legend');
if (hint) { hint.innerHTML = '2 / 8 SCROLL · 5 SELECT · 4 / 6 SEEK<br>1 INFO · 3 SHARE · 0 QUALITY · * HOME · # LIGHT<br>7110: press the roller to select; click the cover to slide.'; help.append(hint); }
tools.append(help);
const disclaimer = document.createElement('p'); disclaimer.className = 'handset-disclaimer'; disclaimer.textContent = 'WAPFLIX · original-era handset study · enlarged cinema display'; tools.append(disclaimer);
function run(action) {
  if (action === 'select') { if (typeof select === 'function') select(); }
  else if (action === 'back') { if (typeof back === 'function') back(); }
  else if (action === 'home') { if (typeof key === 'function') key('*'); }
  else if (typeof key === 'function') key(action);
}
const power = document.createElement('button'); power.type = 'button'; power.className = 'handset-power';
power.setAttribute('aria-label','Toggle display backlight'); power.title = 'Backlight (not a simulated power-off)'; power.onclick = () => run('#'); phone.prepend(power);
function syncLight() { power.setAttribute('aria-pressed',String(!document.getElementById('lcd')?.classList.contains('dim'))); }
const lcd = document.getElementById('lcd'); if (lcd) new MutationObserver(syncLight).observe(lcd,{attributes:true,attributeFilter:['class']}); syncLight();
const receiver = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M6.6 10.8a15.4 15.4 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1.1-.2 1.2.4 2.5.6 3.8.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.7 21 3 13.3 3 3.7c0-.6.4-1 1-1h3.4c.6 0 1 .4 1 1 0 1.3.2 2.6.6 3.8.1.4 0 .8-.2 1.1z"/></svg>';
function button(label,className,action,title) {
  const b = document.createElement('button'); b.type = 'button'; b.className = 'key handset-extra ' + className;
  b.setAttribute('aria-label',title); b.textContent = label;
  if (className === 'handset-call' || className === 'handset-end') b.innerHTML = receiver;
  if (className.endsWith('-up') || className.endsWith('-down')) b.innerHTML = '<svg aria-hidden="true" viewBox="0 0 20 12"><path d="M3 9 10 3 17 9"/></svg>';
  b.onclick = () => run(action); return b;
}
function rocker() {
  const r = document.createElement('div'); r.className = 'handset-rocker handset-extra';
  r.append(button('','handset-up','2','Scroll up'),button('','handset-down','8','Scroll down')); return r;
}
function roller() {
  const r = document.createElement('div'); r.className = 'handset-roller handset-extra'; r.setAttribute('role','group');
  r.setAttribute('aria-label','Navi roller: scroll to browse, press to select');
  r.append(button('','roller-up','2','Roll up'),button('','roller-press','select','Press roller to select or play and pause'),button('','roller-down','8','Roll down'));
  let accumulated = 0, direction = 0;
  r.addEventListener('wheel',e => {
    if (e.ctrlKey || e.metaKey || !e.deltaY) return; e.preventDefault();
    const next = Math.sign(e.deltaY); if (next !== direction) accumulated = 0; direction = next;
    accumulated += e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 100 : 1);
    if (Math.abs(accumulated) >= 24) { run(accumulated > 0 ? '8' : '2'); accumulated = 0; }
  },{passive:false}); return r;
}
function apply() {
  const id = THEMES[index][0], focused = document.activeElement;
  const restoreFocus = deck.contains(focused) && focused !== left && focused !== right;
  document.body.classList.remove(...THEMES.map(t => 'handset-'+t[0])); document.body.classList.add('handset-'+id);
  phone.dataset.handset = id; phone.setAttribute('aria-label','WAPFLIX pocket cinema, Nokia '+id+' inspired handset');
  deck.querySelectorAll('.handset-extra').forEach(el => el.remove());
  left.className = 'key handset-select'; right.className = 'key handset-back'; left.type = right.type = 'button';
  const single = singleNavi(); deck.className = 'handset-controls '+(single ? 'controls-navi' : id === '7110' ? 'controls-roller' : 'controls-dual');
  left.textContent = ''; right.textContent = single ? 'C' : '';
  right.onclick = single ? () => run('back') : originalRight;
  right.setAttribute('aria-label',single ? 'Back (C)' : rightContext);
  if (single) deck.append(rocker());
  else deck.append(button('','handset-call','select','Select or play and pause'),id === '7110' ? roller() : rocker(),button('','handset-end','home','Return home'));
  cover.hidden = id !== '7110'; setCover(false); selectModel.value = id; slideMetrics();
  if (restoreFocus) left.focus({preventScroll:true});
  try { localStorage.setItem(KEY,id); } catch {}
}
new MutationObserver(() => {
  const label = right.getAttribute('aria-label'); if (label !== 'Back (C)') rightContext = label || 'Back';
  if (singleNavi() && label !== 'Back (C)') right.setAttribute('aria-label','Back (C)');
}).observe(right,{attributes:true,attributeFilter:['aria-label']});
function set(id) { const at = THEMES.findIndex(t => t[0] === id); if (at < 0) return false; index = at; apply(); return true; }
function cycle() { index = (index+1)%THEMES.length; apply(); return THEMES[index][1]; }
selectModel.onchange = () => set(selectModel.value);
// Native controls own their keyboard events, not the app's document shortcuts.
tools.addEventListener('keydown',event => event.stopPropagation());
window.wapflixHandset = {cycle,set,current:() => THEMES[index][1]};
apply();
})();
