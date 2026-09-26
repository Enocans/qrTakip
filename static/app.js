'use strict';
const $ = (selector) => document.querySelector(selector);
const form = $('#daily-form');
const draftKey = 'pusula-daily-draft-v2';
const profileKey = 'pusula-profile-v1';
const number = value => Number(value).toLocaleString('tr-TR', {minimumFractionDigits:2, maximumFractionDigits:2});
let csrf = null, deferredInstall = null, busy = false;
let recordId = newId();
function newId() { return globalThis.crypto?.randomUUID?.() || Date.now().toString(36) + '-' + Array.from(crypto.getRandomValues(new Uint8Array(16)), n=>n.toString(16).padStart(2,'0')).join(''); }
function readStore(key) { try { return JSON.parse(localStorage.getItem(key) || 'null'); } catch { return null; } }
function writeStore(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } }
function removeStore(key) { try { localStorage.removeItem(key); } catch {} }
function fill(values) { if (!values || typeof values !== 'object') return; for (const [key, value] of Object.entries(values)) { const input = form.elements.namedItem(key); if (input && input.type !== 'checkbox') input.value = value; } }
function payload() { return {...Object.fromEntries(new FormData(form)), consent:form.elements.consent.checked, id:recordId}; }
function saveDraft() { const ok = writeStore(draftKey, payload()); $('#draft-status').textContent = ok ? 'Taslağın bu cihazda saklandı. Kaldığın yerden devam edebilirsin.' : 'Bu tarayıcıda taslak saklanamıyor. Sayfayı kapatma.'; }
function recalculate() {
  let correct=0, wrong=0, blank=0, completed=0;
  document.querySelectorAll('[data-subject]').forEach(row => {
    const inputs = row.querySelectorAll('input');
    const c = Number(inputs[0].value), w = Number(inputs[1].value), b = Number(inputs[2].value);
    const valid = [c,w,b].every(n=>Number.isInteger(n)&&n>=0&&n<=9999);
    inputs.forEach(input=>input.setCustomValidity(valid ? '' : 'Soru sayılarını 0–9999 arasında tam sayı olarak gir.'));
    row.classList.toggle('invalid', !valid);
    row.querySelector('.subject-total').textContent = valid ? c+w+b : '—';
    if (valid) { correct += c; wrong += w; blank += b; if(c+w+b>0) completed++; }
  });
  $('#total-correct').textContent=correct; $('#total-wrong').textContent=wrong; $('#total-blank').textContent=blank;
  $('#total-questions').textContent=correct+wrong+blank;
}
async function sessionInfo() {
  const response = await fetch('/api/session', {cache:'no-store'});
  if(!response.ok) throw new Error('Sunucuya ulaşılamadı. Taslağın saklanıyor.');
  const data = await response.json(); csrf=data.csrf;
  $('#provider-note').textContent = data.whatsapp_ready ? 'WhatsApp bağlantısı hazır. Kaydettiğinde iki alıcıya da sonuç özeti gönderilecek.' : 'WhatsApp henüz bağlanmadı. Günlük çalışmanı kaydedebilirsin; otomatik mesaj için yönetici bağlantıyı tamamlamalı.';
}
const statusLabels = {accepted:'WhatsApp sağlayıcısına iletildi; teslim henüz doğrulanmadı.', not_configured:'Gönderilmedi · WhatsApp bağlantısı kurulmamış.', failed:'Gönderilemedi · sağlayıcı isteği reddetti.', unknown:'Gönderim sonucu belirsiz · tekrar gönderilmedi.', pending:'Gönderim bekliyor veya işlem yarıda kaldı.'};
function statuses(container, notifications) {
  container.replaceChildren();
  for (const [key,label] of [['teacher','Öğretmenin'],['father','Baban']]) {
    const element=document.createElement('div'); element.className='notification-item'; element.textContent=`${label}: ${statusLabels[notifications[key]] || 'Durum bilinmiyor.'}`;container.append(element);
  }
}
function node(tag, text, className) {const el=document.createElement(tag);if(text!==undefined) el.textContent=text;if(className)el.className=className;return el;}
async function history() {
  const container=$('#history-list');container.replaceChildren(node('p','Günlüğün yükleniyor…','provider-note'));
  try {
    const response=await fetch('/api/records',{cache:'no-store'});if(!response.ok)throw new Error();
    const records=await response.json(); container.replaceChildren();
    if(!records.length) {
      const empty=node('div',undefined,'card empty-state'); empty.append(node('h2','İlk adım seninle başlar.'),node('p','Henüz günlük kaydın yok. Bugün çalıştığın soruları ekleyerek başla.'));
      const button=node('button','Günlük sorularımı ekle →','submit-button');button.type='button';button.onclick=()=>switchView('entry');empty.append(button);container.append(empty);return;
    }
    const days = new Map();
    for(const record of records) {
      if(!days.has(record.date)) days.set(record.date, []);
      days.get(record.date).push(record);
    }
    for(const [day, entries] of days) {
      const section=node('section');
      const heading=node('h2',new Date(day+'T12:00:00').toLocaleDateString('tr-TR',{day:'numeric',month:'long',year:'numeric'}),'day-heading');
      heading.append(node('span',`${entries.reduce((sum,r)=>sum+r.total_questions,0)} soru · ${entries.length} kayıt`));
      section.append(heading); container.append(section);
    for(const record of entries) {
      const card=node('article',undefined,'card history-card');const heading=node('div',undefined,'history-title');const title=node('div');title.append(node('h2','Çalışma kaydı'),node('p',`${record.student_name} · ${new Date(record.date+'T12:00:00').toLocaleDateString('tr-TR')} · ${record.correct} doğru / ${record.wrong} yanlış / ${record.blank} boş`));heading.append(title,node('span',`${record.total_questions} soru`,'history-net'));card.append(heading);
      const details=node('details');details.append(node('summary','Dersler ve WhatsApp durumları'));const subjects=node('div',undefined,'history-subjects');for(const subject of record.subjects){const s=node('div');s.append(node('strong',subject.label),node('div',`${subject.correct} D · ${subject.wrong} Y · ${subject.blank} B`),node('div',`${subject.total} soru`));subjects.append(s);}details.append(subjects);if(record.notes) details.append(node('p',record.notes));const notifications=node('div');statuses(notifications,record.notifications);details.append(notifications);card.append(details);section.append(card);
    }
    }
  }catch {container.replaceChildren(node('p','Geçmiş için internet bağlantısı gerekiyor. Bağlandıktan sonra Günlüğüm sekmesini yeniden aç.','error'));}
}
let currentView='entry';
function switchView(view) {currentView=view; for(const key of ['entry','reports','history']) $('#'+key+'-view').hidden=key!==view;$('#page-label').textContent={entry:'Soru gir',reports:'Raporlar',history:'Günlüğüm'}[view];document.querySelectorAll('[data-view]').forEach(button=>{button.classList.toggle('active',button.dataset.view===view);button.setAttribute('aria-current',button.dataset.view===view?'page':'false');});if(view==='history')history();if(view==='reports')reports();window.scrollTo({top:0});}
document.addEventListener('input',event=>{if(event.target.form!==form)return;recalculate();saveDraft();$('#form-error').textContent='';});
form.addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;recalculate();
  if(!profileValid()){openProfile();$('#profile-error').textContent='Kaydetmek için öğrenci bilgilerini ve paylaşım onayını tamamla.';return;}
  if(!form.reportValidity())return;
  if(Number($('#total-questions').textContent)===0){$('#form-error').textContent='En az bir ders için çalıştığın soru sayısını gir.';return;}
  if(!navigator.onLine){saveDraft();$('#form-error').textContent='Çevrimdışısın. Taslağın saklandı; bağlandığında yeniden kaydet.';return;}
  busy=true;const button=$('#save-button');button.disabled=true;button.textContent='Kaydediliyor ve paylaşılıyor…';$('#form-error').textContent='';
  const data=payload();saveDraft();
  // Prevent edits while the snapshot is being submitted.
  [...form.elements].forEach(el=>el.disabled=true);
  try{
    await sessionInfo();
    const response=await fetch('/api/records',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(data)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Kayıt tamamlanamadı. Yeniden dene.');
    const profile={student_name:data.student_name,father_phone:data.father_phone,teacher_phone:data.teacher_phone||'',consent:data.consent};writeStore(profileKey,profile);removeStore(draftKey);form.reset();fill(profile);form.elements.consent.checked=profile.consent;recordId=newId();recalculate();
    $('#saved-summary').textContent=`${result.date} · ${result.total_questions} soru`;
    statuses($('#notification-results'),result.notifications);$('#result-dialog').showModal();$('#draft-status').textContent='Yeni bir çalışma kaydı için hazırsın.';
  }catch(error){$('#form-error').textContent=error instanceof TypeError?'Bağlantı kesildi. Taslağın saklandı. Aynı kayıtla yeniden denediğinde çift kayıt oluşmaz.':error.message;}
  finally{busy=false;[...form.elements].forEach(el=>el.disabled=false);button.textContent='Kaydet ve paylaş →';}
});
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>switchView(button.dataset.view)));
$('#result-close').onclick=()=>{$('#result-dialog').close();switchView('history');};
$('#qr-open').onclick=()=>{$('#profile-dialog').close();$('#qr-dialog').showModal();};
document.querySelectorAll('.dialog-close').forEach(button=>button.onclick=()=>button.closest('dialog').close());
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();deferredInstall=event;});
$('#install').onclick=async()=>{if(deferredInstall){await deferredInstall.prompt();await deferredInstall.userChoice;deferredInstall=null;}else $('#install-dialog').showModal();};
window.addEventListener('appinstalled',()=>{$('#install').hidden=true;deferredInstall=null;});
function connection(){const online=navigator.onLine;$('#connection').textContent=online?'Çevrimiçisin':'Çevrimdışı · taslak açık';if(!online)$('#provider-note').textContent='Çevrimdışısın. Veri girmeye devam edebilirsin; kaydetmek ve paylaşmak için bağlantı gerekli.';else sessionInfo().catch(()=>{$('#provider-note').textContent='Sunucuya ulaşılamadı. Taslağın bu cihazda saklanır.';});}
window.addEventListener('online',connection);window.addEventListener('offline',connection);
fill(readStore(profileKey));const draft=readStore(draftKey);if(draft){fill(draft);if(typeof draft.id==='string')recordId=draft.id;$('#draft-status').textContent='Kaydedilmemiş taslağın geri yüklendi.';}
const today=new Date();const localDate=[today.getFullYear(),String(today.getMonth()+1).padStart(2,'0'),String(today.getDate()).padStart(2,'0')].join('-');form.elements.date.max=localDate;if(!draft?.date)form.elements.date.value=localDate;
const storedProfile=readStore(profileKey);form.elements.consent.checked=storedProfile?.consent===true;updateProfileLabel();recalculate();connection();
if(location.pathname==='/report'||location.pathname==='/panel')switchView('history');
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});

function profileValid(){return ['student_name','father_phone','teacher_phone','consent'].every(key=>!form.elements[key]||form.elements[key].checkValidity());}
function openProfile(){$('#profile-dialog').showModal();}
function updateProfileLabel(){$('#profile-label').textContent=form.elements.student_name.value.trim().split(' ')[0]||'Bilgilerim';}
$('#profile-open').onclick=openProfile;
$('#profile-save').onclick=()=>{
  for(const key of ['student_name','father_phone','teacher_phone','consent']){const field=form.elements[key];if(field&&!field.reportValidity())return;}
  const data=payload();const profile={student_name:data.student_name,father_phone:data.father_phone,teacher_phone:data.teacher_phone||'',consent:data.consent};
  if(!writeStore(profileKey,profile)){$('#profile-error').textContent='Bu cihazda bilgiler saklanamıyor. Bu oturumda kullanabilirsin.';}
  updateProfileLabel();saveDraft();$('#profile-dialog').close();
};
$('#note-open').onclick=()=>$('#note-dialog').showModal();
$('#note-save').onclick=()=>{saveDraft();$('#note-dialog').close();$('#note-open').textContent=form.elements.notes.value?'✓ Not':'＋ Not';};
// Horizontal gestures navigate; vertical movement and editing keep their normal behavior.
let touchStart=null;
$('#screens').addEventListener('touchstart',event=>{if(event.touches.length!==1||event.target.closest('input,textarea,button,a,summary')){touchStart=null;return;}const t=event.touches[0];touchStart={x:t.clientX,y:t.clientY};},{passive:true});
$('#screens').addEventListener('touchend',event=>{if(!touchStart||busy)return;const t=event.changedTouches[0],dx=t.clientX-touchStart.x,dy=t.clientY-touchStart.y;touchStart=null;if(Math.abs(dx)<65||Math.abs(dx)<Math.abs(dy)*1.5)return;const views=['entry','reports','history'];const index=views.indexOf(currentView)+(dx<0?1:-1);if(views[index])switchView(views[index]);},{passive:true});
$('#screens').addEventListener('touchcancel',()=>{touchStart=null;},{passive:true});
document.querySelectorAll('[data-subject] input').forEach(input=>input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();const inputs=[...document.querySelectorAll('[data-subject] input')];const next=inputs[inputs.indexOf(input)+1];if(next)next.focus();else{input.blur();$('#save-button').focus();}}}));
async function reports(){
  const container=$('#reports-content');container.replaceChildren(node('p','Rapor hazırlanıyor…','provider-note'));
  try{
    const response=await fetch('/api/records',{cache:'no-store'});if(!response.ok)throw new Error();const records=await response.json();
    const dates=Array.from({length:7},(_,i)=>{const d=new Date();d.setDate(d.getDate()-6+i);return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');});
    const week=records.filter(r=>dates.includes(r.date));const total=week.reduce((n,r)=>n+r.total_questions,0);const active=new Set(week.map(r=>r.date)).size;
    container.replaceChildren();const stats=node('div',undefined,'report-stats');for(const [value,label] of [[total,'Son 7 gün · soru'],[active,'Çalışılan gün']]){const card=node('div',undefined,'card');card.append(node('strong',String(value)),node('p',label));stats.append(card);}container.append(stats);
    const chart=node('section',undefined,'card weekly-chart');chart.append(node('h2','Günlük soru sayısı'));const bars=node('div',undefined,'chart-bars');const totals=dates.map(day=>week.filter(r=>r.date===day).reduce((n,r)=>n+r.total_questions,0));const max=Math.max(1,...totals);
    dates.forEach((day,i)=>{const col=node('div',undefined,'chart-col');const bar=node('div',undefined,'chart-bar');bar.style.height=`${Math.max(2,totals[i]/max*100)}px`;col.append(node('strong',String(totals[i])),bar,node('small',new Date(day+'T12:00:00').toLocaleDateString('tr-TR',{weekday:'short'})));bars.append(col);});chart.append(bars);container.append(chart);
    const subjects=node('section',undefined,'card report-subjects');subjects.append(node('h2','Ders dağılımı · son 7 gün'));const totalsBySubject=new Map();week.forEach(r=>r.subjects.forEach(s=>totalsBySubject.set(s.label,(totalsBySubject.get(s.label)||0)+s.total)));
    if(!total)subjects.append(node('p','İlk çalışmanı kaydettiğinde raporun burada oluşacak.','provider-note'));
    for(const [label,count] of totalsBySubject){const row=node('div',undefined,'report-subject');row.append(node('span',label),node('strong',`${count} soru`));subjects.append(row);}container.append(subjects);
  }catch{container.replaceChildren(node('p','Raporlar için bağlantı gerekiyor. Bağlandığında Raporlar sekmesini yeniden aç.','error'));}
}
