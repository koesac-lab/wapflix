(() => {
'use strict';
const THEMES = [['3310','NOKIA 3310'],['8210','NOKIA 8210'],['6310','NOKIA 6310'],['7110','NOKIA 7110'],['3210','NOKIA 3210']];
const KEY = 'wapflix-handset';
let index = 0;
try {
  const saved = localStorage.getItem(KEY);
  const at = THEMES.findIndex(t => t[0] === saved);
  if (at >= 0) index = at;
} catch (error) {}
function apply() {
  document.body.classList.remove(...THEMES.map(t => 'handset-' + t[0]));
  document.body.classList.add('handset-' + THEMES[index][0]);
}
function cycle() {
  index = (index + 1) % THEMES.length;
  try { localStorage.setItem(KEY, THEMES[index][0]); } catch (error) {}
  apply();
  return THEMES[index][1];
}
apply();
window.wapflixHandset = { cycle, current: () => THEMES[index][1] };
})();
