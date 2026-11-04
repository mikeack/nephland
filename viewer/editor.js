/* Nephland pin editor. Loaded only by `python3 nephland.py edit` (never published).
   Adds, moves, edits and deletes pins in dm/locations.json through the local server. */
(function start(){
'use strict';
const N = window.nephland;
if(!N){ window.addEventListener('nephland:ready', start, {once:true}); return; }
const els = N.els;
const TYPES = ['town','landmark','dungeon','tavern','shop'];
let raw = null;          // {locations, maps} straight from dm/
let mode = null;         // null | 'place' | 'move'
let form = null;         // the location being edited (a copy)
let isNew = false;
let busy = false;

/* ---------- styles ---------- */
const css = document.createElement('style');
css.textContent = `
.edbar{position:absolute;left:12px;bottom:12px;z-index:6;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.edbar button{background:var(--ember);color:#fff;border:0;border-radius:8px;height:40px;padding:0 14px;cursor:pointer;font:inherit}
.edbar button.alt{background:rgba(29,24,18,.92);border:1px solid var(--line);color:var(--ink)}
.edbar .msg{background:rgba(29,24,18,.92);border:1px solid var(--dm);border-radius:8px;padding:8px 12px;font-size:.85rem;max-width:360px}
#viewport.placing{cursor:crosshair}
.pin.draft{pointer-events:none}
.pin.draft .dot{background:#fff;border-color:var(--ember);box-shadow:0 0 0 3px var(--ember),0 2px 6px rgba(0,0,0,.6)}
.edform label{display:block;margin:10px 0 4px;font:600 .72rem/1 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.edform input[type=text],.edform input[type=url],.edform select,.edform textarea{width:100%;background:var(--panel);color:var(--ink);
  border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:inherit;font-size:.92rem}
.edform textarea{min-height:70px;resize:vertical}
.edform .dmfield{border-color:var(--dm)}
.edform .check{display:flex;gap:8px;align-items:center;margin-top:12px;font-size:.92rem;cursor:pointer}
.edform .coords{margin-top:8px;font:.78rem ui-monospace,Menlo,monospace;color:var(--muted)}
.edform .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.edform .err{margin-top:10px;padding:8px 10px;border:1px solid var(--ember);border-radius:8px;font-size:.85rem;white-space:pre-wrap}
.edform .danger{background:transparent;border:1px solid var(--ember);color:var(--ember)}
.edform h4{margin:0 0 4px}
`;
document.head.appendChild(css);

/* ---------- toolbar ---------- */
const bar = document.createElement('div'); bar.className = 'edbar';
const addBtn = document.createElement('button'); addBtn.type = 'button'; addBtn.textContent = '+ Add pin';
const msg = document.createElement('span'); msg.className = 'msg'; msg.hidden = true;
bar.append(addBtn, msg);
els.wrap.appendChild(bar);
$('#mode').textContent = 'DM editor · saves to dm/';
document.querySelector('.hint').textContent = 'Editor: click “+ Add pin”, then click the map. Click any pin to edit it. Drag to pan, scroll to zoom.';

function $(s){ return document.querySelector(s); }
let msgTimer = 0;
function say(text, sticky){
  msg.textContent = text; msg.hidden = false;
  clearTimeout(msgTimer);
  if(!sticky) msgTimer = setTimeout(() => { msg.hidden = true; }, 6000);
}
function setMode(m){
  mode = m;
  els.vp.classList.toggle('placing', !!m);
  addBtn.textContent = m === 'place' ? 'Cancel' : '+ Add pin';
  addBtn.classList.toggle('alt', m === 'place');
  if(m === 'place') say('Click the map where the new pin goes. Esc to cancel.', true);
  else if(m === 'move') say('Click the new spot for “'+(form.name || 'this pin')+'”. Esc to cancel.', true);
  else msg.hidden = true;
}
addBtn.onclick = () => {
  if(mode === 'place'){ setMode(null); return; }
  if(!raw){ say('Still loading…'); return; }
  setMode('place');
};
window.addEventListener('keydown', e => { if(e.key === 'Escape' && mode){ setMode(null); drawDraft(); } });

/* ---------- data ---------- */
function loadRaw(){
  return fetch('api/locations', {cache:'no-store'}).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); })
    .then(d => { raw = d; });
}
function reloadView(selectId){
  return fetch('data/map-data.json', {cache:'no-store'}).then(r => r.json()).then(d => {
    N.reload(d);
    if(selectId) N.select(selectId); else N.closeCard();
  });
}
const slug = s => s.normalize('NFKD').replace(/[̀-ͯ]/g,'').toLowerCase()
  .replace(/['’]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'') || 'place';
function uniqueId(base, except){
  const used = new Set(raw.locations.filter(l => l !== except).map(l => l.id));
  let id = base, n = 2;
  while(used.has(id)) id = base+'-'+(n++);
  return id;
}

/* ---------- draft marker ---------- */
function drawDraft(){
  document.querySelectorAll('.pin.draft').forEach(p => p.remove());
  if(!form || form.map !== N.cur.id) return;
  const b = document.createElement('span'); b.className = 'pin draft';
  b.style.left = form.x+'%'; b.style.top = form.y+'%';
  const dot = document.createElement('span'); dot.className = 'dot'; b.appendChild(dot);
  els.pins.appendChild(b);
}

/* ---------- hooks from the viewer ---------- */
N.hooks.mapClick = (x, y) => {
  if(!mode) return;
  x = Math.round(Math.min(100, Math.max(0, x))*100)/100;
  y = Math.round(Math.min(100, Math.max(0, y))*100)/100;
  if(mode === 'place'){
    form = {id:'', name:'', map:N.cur.id, x, y, type:'town', revealed:false, description:'', dm_notes:''};
    isNew = true;
  } else if(mode === 'move' && form){
    form.x = x; form.y = y;
  }
  setMode(null);
  renderForm();
  drawDraft();
};
N.hooks.pinClick = l => {
  if(mode === 'move') return true;
  N.select(l.id);
  return true;               // in the editor, clicking a pin selects it instead of opening its map
};
N.hooks.card = (l, card) => {
  const row = document.createElement('div'); row.className = 'row';
  const b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = 'Edit pin';
  b.onclick = () => startEdit(l.id);
  row.appendChild(b); card.appendChild(row);
};
N.hooks.mapShown = () => {
  if(form && form.map !== N.cur.id){ form = null; }
  setMode(null);
  drawDraft();
};

function startEdit(id){
  const l = raw && raw.locations.find(x => x.id === id);
  if(!l){ say('Could not find '+id+' in dm/locations.json. Reload the page.'); return; }
  form = JSON.parse(JSON.stringify(l));
  isNew = false;
  renderForm();
  drawDraft();
}

/* ---------- form ---------- */
function field(parent, labelText, input){
  const lab = document.createElement('label'); lab.textContent = labelText;
  parent.append(lab, input); return input;
}
function renderForm(errors){
  const c = els.card; c.textContent = ''; c.hidden = false;
  const f = document.createElement('form'); f.className = 'edform'; f.noValidate = true;
  const h = document.createElement('h4'); h.textContent = isNew ? 'New pin' : 'Edit pin';
  f.appendChild(h);

  const name = field(f, 'Name', document.createElement('input')); name.type = 'text'; name.value = form.name || ''; name.required = true;
  const idIn = field(f, 'Id (used in links and commands)', document.createElement('input')); idIn.type = 'text';
  idIn.value = form.id || ''; idIn.placeholder = 'made from the name';
  if(!isNew){ idIn.readOnly = true; idIn.title = 'Ids of existing pins are fixed, because links and calendar events point at them.'; }
  let idTouched = !isNew;
  idIn.oninput = () => { idTouched = true; };
  name.oninput = () => { if(!idTouched) idIn.value = name.value ? uniqueId(slug(name.value)) : ''; };

  const type = field(f, 'Type', document.createElement('select'));
  const types = new Set(TYPES.concat(form.type && !TYPES.includes(form.type) ? [form.type] : []));
  types.forEach(t => { const o = document.createElement('option'); o.value = t; o.textContent = t; type.appendChild(o); });
  type.value = form.type || 'town';

  const desc = field(f, 'Description (players see this)', document.createElement('textarea')); desc.value = form.description || '';
  const notes = field(f, 'DM notes (never published)', document.createElement('textarea')); notes.value = form.dm_notes || ''; notes.className = 'dmfield';

  const opens = field(f, 'Clicking it opens map', document.createElement('select'));
  const none = document.createElement('option'); none.value = ''; none.textContent = '— nothing —'; opens.appendChild(none);
  raw.maps.filter(m => m.id !== form.map).forEach(m => {
    const o = document.createElement('option'); o.value = m.id; o.textContent = m.title+(m.revealed ? '' : ' (hidden map)'); opens.appendChild(o);
  });
  opens.value = form.opens || '';

  const url = field(f, 'Read-more link (optional)', document.createElement('input')); url.type = 'url'; url.value = form.note_url || ''; url.placeholder = 'https://';

  const chk = document.createElement('label'); chk.className = 'check';
  const rev = document.createElement('input'); rev.type = 'checkbox'; rev.checked = !!form.revealed;
  chk.append(rev, document.createTextNode('Visible to players'));
  f.appendChild(chk);

  const coords = document.createElement('div'); coords.className = 'coords';
  const mapTitle = (raw.maps.find(m => m.id === form.map) || {}).title || form.map;
  coords.textContent = mapTitle+' · x '+form.x+', y '+form.y;
  f.appendChild(coords);

  if(errors && errors.length){
    const e = document.createElement('div'); e.className = 'err'; e.textContent = errors.join('\n'); f.appendChild(e);
  }

  const row = document.createElement('div'); row.className = 'row';
  const save = document.createElement('button'); save.type = 'submit'; save.className = 'btn'; save.textContent = isNew ? 'Add pin' : 'Save';
  const move = document.createElement('button'); move.type = 'button'; move.className = 'btn alt'; move.textContent = 'Move';
  const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'btn alt'; cancel.textContent = 'Cancel';
  row.append(save, move, cancel);
  if(!isNew){
    const del = document.createElement('button'); del.type = 'button'; del.className = 'btn danger'; del.textContent = 'Delete';
    del.onclick = () => remove();
    row.appendChild(del);
  }
  f.appendChild(row);

  const collect = () => {
    form.name = name.value.trim();
    if(isNew) form.id = idIn.value.trim() || (form.name ? uniqueId(slug(form.name)) : '');
    form.type = type.value; form.description = desc.value.trim(); form.dm_notes = notes.value.trim();
    form.opens = opens.value; form.note_url = url.value.trim(); form.revealed = rev.checked;
  };
  move.onclick = () => { collect(); setMode('move'); };
  cancel.onclick = () => { const id = isNew ? null : form._orig || form.id; form = null; setMode(null); drawDraft(); if(id) N.select(id); else N.closeCard(); };
  f.onsubmit = ev => { ev.preventDefault(); collect(); persist(); };
  c.appendChild(f);
  if(!form._orig && !isNew) form._orig = form.id;
  (isNew ? name : save).focus();
}

function payloadWith(list){
  return JSON.stringify({locations: list.map(l => { const o = Object.assign({}, l); delete o._orig; return o; })});
}
function post(list){
  busy = true;
  return fetch('api/locations', {method:'POST', headers:{'Content-Type':'application/json'}, body: payloadWith(list)})
    .then(r => r.json().then(j => ({status:r.status, j})))
    .finally(() => { busy = false; });
}
function report(j, what){
  if(j.check_ok) say(what+' Saved to dm/ and rebuilt. Leak check passed, ready to publish.');
  else say(what+' Saved, but the leak check FAILED. Do not publish until it is fixed:\n'+j.log, true);
}

function persist(){
  if(busy) return;
  const errs = [];
  if(!form.name) errs.push('Give the pin a name.');
  if(errs.length) return renderForm(errs);
  const orig = isNew ? null : (form._orig || form.id);
  const list = raw.locations.slice();
  const i = orig ? list.findIndex(l => l.id === orig) : -1;
  if(i >= 0) list[i] = form; else list.push(form);
  post(list).then(({status, j}) => {
    if(status !== 200 || !j.ok) return renderForm(j.errors || ['Save failed ('+status+')']);
    const id = form.id, label = (isNew ? 'Added ' : 'Saved ')+'“'+form.name+'”.';
    form = null; drawDraft();
    return loadRaw().then(() => reloadView(id)).then(() => report(j, label));
  }).catch(e => renderForm(['Could not reach the editor server. Is `python3 nephland.py edit` still running? ('+e.message+')']));
}

function remove(){
  if(busy) return;
  const id = form._orig || form.id;
  if(!confirm('Delete “'+(form.name || id)+'”? A backup of the previous file is kept in dm/locations.backup.json.')) return;
  const list = raw.locations.filter(l => l.id !== id);
  post(list).then(({status, j}) => {
    if(status !== 200 || !j.ok) return renderForm(j.errors || ['Delete failed ('+status+')']);
    const label = 'Deleted “'+(form.name || id)+'”.';
    form = null; drawDraft();
    return loadRaw().then(() => reloadView(null)).then(() => report(j, label));
  }).catch(e => renderForm(['Could not reach the editor server. ('+e.message+')']));
}

loadRaw().then(() => say('Editor ready. Changes save to '+raw.source+'/locations.json.'))
  .catch(() => say('Could not load locations from the editor server.', true));
})();
