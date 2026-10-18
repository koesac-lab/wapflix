(() => {
'use strict';
const base = new URL('./', location.href);
const sheet = document.createElement('dialog');
sheet.className = 'share-sheet';
sheet.setAttribute('aria-labelledby', 'share-title');
sheet.innerHTML = `<h2 id="share-title">TRANSMIT A LINK</h2><p id="share-name"></p><fieldset><legend>WHAT TO SHARE</legend><label><input type="radio" name="share-target" value="episode" checked> This transmission</label><label><input type="radio" name="share-target" value="station">Whole station</label></fieldset><label id="share-time-row"><input type="checkbox" id="share-time"> Include playback position</label><label for="share-url">LINK</label><input id="share-url" type="text" readonly spellcheck="false"><div class="share-actions"><button id="share-native" type="button">Device share...</button><button id="share-copy" type="button">Copy link</button><a id="share-whatsapp" target="_blank" rel="noopener noreferrer">WhatsApp</a><a id="share-email">Email</a></div><p id="share-status" role="status" aria-live="polite"></p><button id="share-close" type="button">Back</button>`;
document.body.append(sheet);
const get = id => sheet.querySelector('#'+id);
let snapshot = null, payload = null, opener = null;
function candidate() {
  if (view === 'player') return item;
  if (view === 'episodes') return groups[group]?.items[index] || null;
  return null;
}
function update() {
  const episode = snapshot?.item && sheet.querySelector('input[name="share-target"]:checked').value === 'episode';
  const url = new URL(episode ? 'share/'+encodeURIComponent(snapshot.item.id)+'/' : './', base);
  if (episode && snapshot.position > 0 && get('share-time').checked) url.searchParams.set('t', String(snapshot.position));
  payload = {title: episode ? 'WAPFLIX / '+snapshot.item.title : 'WAPFLIX / pocket cinema', text: 'A green-backlit ASCII cinema experiment. Demo animation, not actual episode footage.', url: url.href};
  get('share-name').textContent = episode ? snapshot.item.title : 'WAPFLIX / pocket cinema';
  get('share-url').value = url.href;
  get('share-time').disabled = !episode || !snapshot.position;
  get('share-whatsapp').href = 'https://wa.me/?text='+encodeURIComponent(payload.title+'\n'+payload.url);
  get('share-email').href = 'mailto:?subject='+encodeURIComponent(payload.title)+'&body='+encodeURIComponent(payload.text+'\n\n'+payload.url);
  get('share-status').textContent = '';
}
function open() {
  if (sheet.open) return;
  opener = document.activeElement;
  const current = candidate();
  snapshot = {item: current, position: current && view === 'player' ? Math.max(0,Math.floor(elapsed)) : 0};
  setPlaying(false);
  if (clip) paint();
  const episode = sheet.querySelector('input[value="episode"]');
  episode.disabled = !current;
  sheet.querySelector('input[value="'+(current?'episode':'station')+'"]').checked = true;
  get('share-time').checked = false;
  get('share-time-row').hidden = !snapshot.position;
  get('share-native').hidden = typeof navigator.share !== 'function';
  update();
  sheet.showModal();
}
get('share-close').onclick = () => sheet.close();
sheet.addEventListener('close', () => { if (opener?.isConnected) opener.focus(); });
sheet.addEventListener('change', update);
sheet.addEventListener('click', e => { if(e.target === sheet) sheet.close(); });
get('share-native').onclick = async () => {
  try {
    await navigator.share({...payload});
    sheet.close();
    announce('Link handed to your device share sheet.');
  } catch (error) {
    if (error.name !== 'AbortError') get('share-status').textContent = 'Device sharing unavailable. Use Copy link instead.';
  }
};
get('share-copy').onclick = async () => {
  try {
    if (!navigator.clipboard?.writeText) throw Error('Clipboard unavailable');
    await navigator.clipboard.writeText(payload.url);
    get('share-status').textContent = 'LINK COPIED.';
  } catch {
    const input = get('share-url');
    input.focus(); input.select(); input.setSelectionRange(0,input.value.length);
    get('share-status').textContent = 'Select and copy this link manually.';
  }
};
const oldKey = key;
key = function(value) { if(value === '3') open(); else oldKey(value); };
async function restore() {
  const params = new URLSearchParams(location.search), id = params.get('episode');
  if (!id) return;
  const gi = groups.findIndex(g => g.items.some(i => i.id === id));
  if (gi < 0) { announce('Shared transmission not found. Browse the catalogue instead.'); return; }
  group = gi; index = groups[gi].items.findIndex(i => i.id === id);
  const pending = load(groups[group].items[index]), version = token;
  await pending;
  if (version !== token || !clip) return;
  const t = Number(params.get('t') || 0);
  if (Number.isFinite(t)) elapsed = Math.max(0,Math.min(t,clip.frames.length/clip.fps));
  paint();
}
Promise.resolve(window.wapflixReady).then(restore).catch(() => announce('Shared link could not be opened.'));
})();
