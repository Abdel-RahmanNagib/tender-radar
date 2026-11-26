/* رادار المناقصات – app logic (no libraries). Data comes from data/*.json written by the scanner. */
'use strict';

/* ------------------------------------------------------------------ helpers */
const $ = (s, el = document) => el.querySelector(s);
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const h = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
};
const prefs = Object.assign({ opened: {}, notifyLocal: false, office: {}, ntfyTopic: '', known: [], dismiss: {} },
  store.get('tr.prefs', {}));
const savePrefs = () => { store.set('tr.prefs', prefs); syncMeta(); };
const tget = (id) => Object.assign({ status: '', docs: {}, steps: {} }, store.get('tr.t.' + id, {}));
const tset = (id, v) => store.set('tr.t.' + id, v);
let refs = store.get('tr.refs', []);

const S = { data: null, status: null, profile: null, route: { view: 'list', tab: 'all', id: null, dtab: 'info' },
  q: '', country: '', disc: '', sort: 'deadline', installEvt: null, mailLang: null, lastTab: 'all' };

const STATUS = { '': 'لم أحدد', study: 'ندرسها', apply: 'سنقدّم', submitted: 'تم التقديم', skip: 'غير مناسبة' };
const SOURCE_AR = { worldbank: 'البنك الدولي', etimad: 'منصة اعتماد', etimad_prequal: 'اعتماد – التأهيل المسبق', monaqasat: 'منصة مناقصات قطر', ungm: 'الأمم المتحدة UNGM',
  kuwait_capt: 'جهاز المناقصات – الكويت', pc_relay: 'من كمبيوتر المكتب', oman_tenderboard: 'مجلس المناقصات – عُمان',
  bahrain_tb: 'مجلس المناقصات – البحرين', ebrd_ecepp: 'البنك الأوروبي EBRD',
  uae_mof: 'الإمارات – الجهات الاتحادية', dubai_esupply: 'حكومة دبي – eSupply', abudhabi_adgpg: 'حكومة أبوظبي – ADGPG',
  dewa_tenders: 'هيئة كهرباء ومياه دبي',
  google_news: 'أخبار الطروحات', rss_feeds: 'خلاصات RSS', web_pages: 'بوابات حكومية وبنوك تنمية' };
const EN = { stormwater: 'stormwater drainage', hydrology: 'hydrology and hydraulic modelling', sewer: 'sewerage and wastewater',
  water: 'water networks', irrigation: 'irrigation networks', roads: 'roads and highway design', pavement: 'pavement design',
  grading: 'grading and earthworks', utilities: 'wet utilities and infrastructure', bim: 'BIM modelling', review: 'design review' };

const ICON = {
  mail: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5 12 13l8.5-6.5"/></svg>',
  phone: '<svg viewBox="0 0 24 24"><path d="M5 4h3.5l1.6 4.2-2.2 1.4a11 11 0 0 0 6.5 6.5l1.4-2.2L20 15.5V19a1.5 1.5 0 0 1-1.6 1.5A16.5 16.5 0 0 1 3.5 5.6 1.5 1.5 0 0 1 5 4z"/></svg>',
  wa: '<svg viewBox="0 0 24 24"><path d="M4 20l1.3-4A8 8 0 1 1 8 18.8z"/><path d="M9 9.5c0 3 2.5 5.5 5.5 5.5l1.2-1.4-1.8-.9-.9.9a4 4 0 0 1-2.1-2.1l.9-.9-.9-1.8z"/></svg>',
  web: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/></svg>',
  pin: '<svg viewBox="0 0 24 24"><path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/></svg>',
  copy: '<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>',
  cal: '<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>',
  share: '<svg viewBox="0 0 24 24"><circle cx="18" cy="5.5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="18.5" r="2.5"/><path d="M8.2 10.8l7.6-4.1M8.2 13.2l7.6 4.1"/></svg>',
  out: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 20 20"/></svg>',
  back: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg>',
};

const framed = (() => { try { return window.self !== window.top; } catch (e) { return true; } })();

/* ------------------------------------------------------------------ dates */
const DAY = 864e5;
const today = () => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); };
const pd = (s) => { if (!s) return null; const [y, m, d] = String(s).slice(0, 10).split('-').map(Number); return y ? new Date(y, m - 1, d) : null; };
const diffDays = (a, b) => Math.round((a - b) / DAY);
const fLong = new Intl.DateTimeFormat('ar-EG-u-nu-latn', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
const fShort = new Intl.DateTimeFormat('ar-EG-u-nu-latn', { day: 'numeric', month: 'long' });
const dLong = (s) => { const d = pd(s); return d ? fLong.format(d) : ''; };
const dShort = (s) => { const d = pd(s); return d ? fShort.format(d) : ''; };
function daysWord(n) {
  n = Math.abs(n);
  if (n === 1) return 'يوم واحد';
  if (n === 2) return 'يومان';
  if (n <= 10) return `${n} أيام`;
  return `${n} يوماً`;
}
const left = (t) => { const d = pd(t.deadline); return d ? diffDays(d, today()) : null; };
function leftLabel(n) {
  if (n === null) return 'الموعد غير مذكور';
  if (n < 0) return 'انتهى الموعد';
  if (n === 0) return 'ينتهي اليوم';
  if (n === 1) return 'ينتهي غداً';
  return 'باقي ' + daysWord(n);
}
const urgency = (n) => (n === null ? 'none' : n < 0 ? 'over' : n <= 3 ? 'urgent' : n <= 7 ? 'soon' : 'ok');
function relDay(s) {
  const d = pd(s); if (!d) return '';
  const n = diffDays(d, today());
  if (n === 0) return 'اليوم';
  if (n === 1) return 'غداً';
  if (n > 1) return 'بعد ' + daysWord(n);
  return 'متأخرة ' + daysWord(n);
}
function ago(iso) {
  const ms = Date.now() - Date.parse(iso);
  if (!(ms >= 0)) return '';
  const m = Math.round(ms / 6e4);
  if (m < 2) return 'الآن';
  if (m < 60) return `منذ ${m} دقيقة`;
  const hr = Math.round(m / 60);
  if (hr < 24) return hr === 1 ? 'منذ ساعة' : hr === 2 ? 'منذ ساعتين' : `منذ ${hr} ساعات`;
  return 'منذ ' + daysWord(Math.round(hr / 24));
}

/* ------------------------------------------------------------------ text matching (for your past projects) */
const AR_MAP = { 'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ة': 'ه', 'ى': 'ي', 'ـ': '' };
const norm = (s) => String(s || '').toLowerCase().replace(/[\u064B-\u0652]/g, '')
  .replace(/[أإآةىـ]/g, (c) => AR_MAP[c]).replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
let MATCHERS = null;
function matchers() {
  if (MATCHERS || !S.profile) return MATCHERS || [];
  MATCHERS = S.profile.disciplines.map((d) => ({
    id: d.id, ar: d.ar,
    tests: d.keywords.map((k) => {
      const w = norm(k);
      if (/[a-z0-9]/.test(w)) {
        const rx = new RegExp('(^|[^a-z0-9])' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![a-z0-9])');
        return (t) => rx.test(t);
      }
      return (t) => t.includes(w);
    }),
  }));
  return MATCHERS;
}
const classify = (text) => { const t = norm(text); return matchers().filter((m) => m.tests.some((f) => f(t))).map((m) => m.id); };
function similar(t) {
  const want = new Set(t.match.ids || []);
  return refs.map((r) => ({ r, k: r.ids.filter((i) => want.has(i)).length + (/complet|deliver|submit|منته|تسليم/i.test(r.st) ? 0.3 : 0) }))
    .filter((x) => x.k >= 1).sort((a, b) => b.k - a.k).slice(0, 6).map((x) => x.r);
}

/* ------------------------------------------------------------------ data */
async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}
async function load(first) {
  try {
    const [d, s, p] = await Promise.all([getJSON('data/tenders.json'),
      getJSON('data/status.json').catch(() => null), getJSON('data/profile.json').catch(() => null)]);
    S.data = d; S.status = s; S.profile = p; MATCHERS = null;
  } catch (e) {
    if (!S.data) S.data = { tenders: [], missing: true };
  }
  if (first) route(); else render();
  notifyFresh();
}
const all = () => (S.data && S.data.tenders) || [];
const byId = (id) => all().find((t) => t.id === id);
const isOpen = (t) => { const n = left(t); return n === null || n >= 0; };
const isNew = (t) => !prefs.opened[t.id] && Date.now() - Date.parse(t.first_seen) < 7 * DAY;
function inTab(t, tab) {
  const st = tget(t.id).status;
  if (tab === 'mine') return ['study', 'apply', 'submitted'].includes(st);
  if (!isOpen(t)) return false;
  if (tab === 'new') return isNew(t);
  if (tab === 'soon') { const n = left(t); return n !== null && n <= 7; }
  return true;
}
function filtered(tab) {
  const q = norm(S.q.trim());
  let list = all().filter((t) => inTab(t, tab));
  if (S.country) list = list.filter((t) => t.country === S.country);
  if (S.disc) list = list.filter((t) => (t.match.ids || []).includes(S.disc));
  if (q) list = list.filter((t) => norm([t.title, t.client, t.reference, t.country_ar, t.summary].join(' ')).includes(q));
  const lv = { high: 0, medium: 1, low: 2 };
  const key = {
    deadline: (t) => { const n = left(t); return n === null ? 1e6 : n; },
    newest: (t) => -Date.parse(t.first_seen),
    fit: (t) => lv[t.match.level] * 1000 - t.match.score,
  }[S.sort];
  list.sort((a, b) => (tget(a.id).status === 'skip') - (tget(b.id).status === 'skip') || key(a) - key(b));
  return list;
}

/* ------------------------------------------------------------------ scale bar */
function scaleBar(t, big) {
  const n = left(t);
  const u = urgency(n);
  const end = pd(t.deadline);
  if (!end) {
    return big
      ? `<div class="scale scale--big scale--none"><div class="scale__headline"><strong>الموعد غير مذكور في المصدر</strong><span>راجع الإعلان الرسمي</span></div></div>`
      : `<div class="scale scale--none"><div class="scale__bar"></div><span class="scale__left">الموعد غير مذكور</span></div>`;
  }
  let start = pd(t.published) || pd((t.first_seen || '').slice(0, 10)) || today();
  if (start >= end) start = new Date(end.getTime() - 7 * DAY);
  const total = Math.max(1, diffDays(end, start));
  let seg = 7; let k = Math.ceil(total / seg);
  while (k > 14) { seg *= 2; k = Math.ceil(total / seg); }
  const elapsed = Math.max(0, Math.min(total, diffDays(today(), start)));
  let segs = '';
  for (let i = 0; i < k; i++) {
    const len = Math.min(seg, total - i * seg);
    const f = Math.max(0, Math.min(1, (elapsed - i * seg) / len));
    segs += `<span class="scale__seg" style="flex:${len} 1 0"><i style="width:${(f * 100).toFixed(1)}%"></i></span>`;
  }
  const pct = (elapsed / total) * 100;
  const cls = `scale scale--${u}${big ? ' scale--big' : ''}`;
  const aria = `المدة من النشر حتى آخر موعد مقسمة إلى أسابيع، ${leftLabel(n)}`;
  if (!big) {
    return `<div class="${cls}"><div class="scale__bar" role="img" aria-label="${aria}">${segs}</div><span class="scale__left">${leftLabel(n)}</span></div>`;
  }
  let ticks = ''; let lastPos = -10;
  (t.steps || []).forEach((s, i) => {
    if (!s.due || s.after_deadline) return;
    const pos = Math.max(0, Math.min(100, (diffDays(pd(s.due), start) / total) * 100));
    if (pos - lastPos < 4) return;
    lastPos = pos;
    ticks += `<a href="#t-${t.id}--steps" style="inset-inline-start:${pos.toFixed(1)}%" title="${h(s.title)}">${i + 1}</a>`;
  });
  const time = t.deadline_time ? ` – الساعة ${h(t.deadline_time)}` : '';
  return `<div class="${cls}">
    <div class="scale__headline"><strong>${leftLabel(n)}</strong><span>آخر موعد: ${dLong(t.deadline)}${time}</span></div>
    <div class="scale__bar" role="img" aria-label="${aria}" style="margin-top:10px">${segs}
      ${n >= 0 ? `<span class="scale__today" style="inset-inline-start:${pct.toFixed(1)}%" title="اليوم"></span>` : ''}</div>
    <div class="scale__ticks" aria-hidden="true">${ticks}</div>
    <div class="scale__ends"><span>النشر <b>${dShort(isoLocal(start))}</b></span><span>التسليم <b>${dShort(t.deadline)}</b></span></div>
    <p class="scale__legend">كل قطعة في الشريط = ${seg === 7 ? 'أسبوع' : daysWord(seg)}، والجزء الداكن ما مضى، والأرقام تحته مواعيد خطوات التقديم.</p></div>`;
}
function plural(n) {
  if (n === 1) return 'فرصة واحدة';
  if (n === 2) return 'فرصتان';
  if (n >= 3 && n <= 10) return `${n} فرص`;
  return `${n} فرصة`;
}
const isoLocal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

/* ------------------------------------------------------------------ list */
function sheet(t) {
  const st = tget(t.id).status;
  return `<a class="sheet${st === 'skip' ? ' is-skip' : ''}" href="#t-${t.id}" data-id="${t.id}"${S.route.id === t.id ? ' aria-current="true"' : ''}>
    <div class="sheet__meta"><span class="pill pill--country">${h(t.country_ar)}</span><span>${h(SOURCE_AR[t.source_key] || t.source)}</span>
      ${isNew(t) ? '<span class="pill pill--new">جديد</span>' : ''}${st ? `<span class="pill pill--status st-${st}">${STATUS[st]}</span>` : ''}</div>
    <h2 class="sheet__title" dir="auto">${h(t.title)}</h2>
    <p class="sheet__client" dir="auto">${h(t.client || t.notice_type_ar)}</p>
    ${scaleBar(t, false)}
    <div class="sheet__foot"><div class="tags"><span class="tag">${h(t.match.disciplines[0] || '')}</span>${t.match.disciplines.length > 1 ? `<span class="tag ltr" title="${h(t.match.disciplines.slice(1).join('، '))}">+${t.match.disciplines.length - 1}</span>` : ''}</div>
      <span class="fit fit--${t.match.level}">${h(t.match.level_ar)}</span></div></a>`;
}
function renderListControls() {
  const countries = [...new Map(all().map((t) => [t.country, t.country_ar])).entries()].sort((a, b) => a[1].localeCompare(b[1], 'ar'));
  const discs = (S.profile && S.profile.disciplines) || [];
  $('#listPane').innerHTML = `
    <div class="tabs" role="toolbar" aria-label="عرض">
      ${[['new', 'جديدة'], ['soon', 'تنتهي قريباً'], ['all', 'الكل'], ['mine', 'متابعتي']].map(([k, l]) =>
        `<button class="tab" data-act="tab" data-tab="${k}" aria-pressed="${S.route.tab === k}">${l}<b data-count="${k}"></b></button>`).join('')}
    </div>
    <div class="filters">
      <label class="search">${ICON.search}<input id="q" type="search" aria-label="بحث" placeholder="ابحث بالعنوان أو الجهة أو الرقم المرجعي" value="${h(S.q)}"></label>
      <details class="more"${window.innerWidth >= 1000 || S.country || S.disc ? ' open' : ''}><summary>تصفية وترتيب${S.country || S.disc ? '<b>مفعّلة</b>' : ''}</summary><div class="more__grid">
      <select id="fCountry" aria-label="الدولة"><option value="">كل الدول</option>${countries.map(([k, v]) => `<option value="${h(k)}"${S.country === k ? ' selected' : ''}>${h(v)}</option>`).join('')}</select>
      <select id="fDisc" aria-label="التخصص"><option value="">كل التخصصات</option>${discs.map((d) => `<option value="${d.id}"${S.disc === d.id ? ' selected' : ''}>${h(d.ar)}</option>`).join('')}</select>
      <select id="fSort" aria-label="الترتيب"><option value="deadline"${S.sort === 'deadline' ? ' selected' : ''}>الترتيب: الأقرب موعداً</option>
        <option value="newest"${S.sort === 'newest' ? ' selected' : ''}>الترتيب: الأحدث رصداً</option><option value="fit"${S.sort === 'fit' ? ' selected' : ''}>الترتيب: الأنسب لكم</option></select>
      </div></details>
    </div>
    <div id="results"></div>`;
}
function renderResults() {
  const tab = S.route.tab;
  document.querySelectorAll('[data-count]').forEach((b) => { const n = all().filter((t) => inTab(t, b.dataset.count)).length; b.textContent = n || ''; });
  const list = filtered(tab);
  const box = $('#results');
  if (!box) return;
  if (S.data && S.data.missing) {
    box.innerHTML = `<div class="empty"><b>لا توجد بيانات بعد</b>أول فحص لم يكتمل. في التشغيل السحابي افتح GitHub ثم Actions ثم Tender Radar ثم Run workflow، وانتظر 3 دقائق.</div>`;
    return;
  }
  if (!all().length) {
    box.innerHTML = `<div class="empty"><b>لم تُسجَّل فرص بعد</b>${S.status ? `آخر فحص ${ago(S.status.last_run)}. ` : ''}لو استمر ذلك، راجع «حالة الرادار» في <a href="#prefs">الإعدادات</a> لمعرفة المصادر التي تعذر الوصول إليها.</div>`;
    return;
  }
  if (!list.length) {
    const msg = { new: 'لا توجد فرص جديدة منذ آخر مرة. سيصلك إشعار فور ظهور فرصة.', soon: 'لا توجد فرص تنتهي خلال أسبوع.',
      mine: 'لم تحدد حالة أي فرصة بعد. افتح فرصة واختر «سنقدّم» أو «ندرسها» لتظهر هنا.', all: 'لا توجد نتائج بهذه الشروط.' }[tab];
    box.innerHTML = `<div class="empty"><b>لا شيء هنا الآن</b>${msg}</div>`;
    return;
  }
  box.innerHTML = `<p class="count">${plural(list.length)}</p><div class="sheets">${list.map(sheet).join('')}</div>`;
}

/* ------------------------------------------------------------------ detail */
function factsBlock(t) {
  const facts = [
    ['الدولة', t.country_ar], ['الجهة', t.client], ['نوع الإعلان', t.notice_type_ar], ['الرقم المرجعي', t.reference],
    [t.kind === 'etimad' ? 'النشاط' : 'طريقة الاختيار', t.kind === 'etimad' ? t.activity : t.method_ar], ['التمويل', t.funding],
    ['قيمة الكراسة أو الوثائق', t.booklet_price], ['الضمان الابتدائي', t.guarantee], ['مدة العقد', t.contract_duration],
    ['المصدر', t.source],
  ].filter(([, v]) => v);
  const fit = `${t.match.level_ar}: ${t.match.disciplines.join('، ')}`;
  const n = facts.length; const r4 = n % 4;
  const cls = (i) => (i === n - 1 ? [n % 2 ? 'm2' : '', r4 ? 'd' + (5 - r4) : ''].join(' ').trim() : '');
  return `<div class="tblock">${facts.map(([l, v], i) => `<div class="${cls(i)}"><span class="tblock__l">${l}</span><span class="tblock__v" dir="auto">${h(v)}</span></div>`).join('')}
    <div class="wide"><span class="tblock__l">مدى مناسبتها لكم</span><span class="tblock__v">${h(fit)}</span></div></div>`;
}
function progress(done, total, label) {
  const p = total ? Math.round((done / total) * 100) : 0;
  return `<div class="progress"><span>${label} ${done} من ${total}</span><span class="progress__bar"><i style="width:${p}%"></i></span></div>`;
}
const counts = (t) => {
  const st = tget(t.id);
  return { d: t.documents.filter((_, i) => st.docs[i]).length, s: t.steps.filter((_, i) => st.steps[i]).length };
};
function renderDetail() {
  const t = byId(S.route.id);
  const pane = $('#detailPane');
  if (!t) {
    pane.innerHTML = `<button class="back" data-act="back">${ICON.back} رجوع</button><div class="empty"><b>هذه الفرصة لم تعد في القائمة</b>ربما انتهى موعدها منذ أكثر من أسبوعين.</div>`;
    return;
  }
  const st = tget(t.id);
  const c = counts(t);
  const dt = S.route.dtab;
  const tab = (k, l, extra = '') => `<button class="dtab" role="tab" data-act="dtab" data-dtab="${k}" aria-selected="${dt === k}">${l}${extra}</button>`;
  const official = (t.links || [])[0];
  pane.innerHTML = `
    <button class="back" data-act="back">${ICON.back} كل الفرص</button>
    <h1 class="d-title" dir="auto">${h(t.title)}</h1>
    <p class="d-sub">${h(t.notice_type_ar)}${t.client ? ' – ' + h(t.client) : ''}</p>
    ${!t.is_arabic ? `<div class="d-tools"><a class="btn btn--ghost btn--sm" target="_blank" rel="noopener" href="https://translate.google.com/?sl=auto&tl=ar&op=translate&text=${encodeURIComponent(t.title + '\n\n' + (t.summary || ''))}">ترجمة للعربية</a></div>` : ''}
    ${factsBlock(t)}
    ${scaleBar(t, true)}
    <div class="dtabs" role="tablist" aria-label="أقسام الفرصة">
      ${tab('info', 'البيانات')}${tab('docs', 'الأوراق المطلوبة', `<small data-dcount>${c.d}/${t.documents.length}</small>`)}
      ${tab('contact', 'التواصل')}${tab('steps', 'خطوات التقديم', `<small data-scount>${c.s}/${t.steps.length}</small>`)}
    </div>
    <div class="dpanel" role="tabpanel">${{ info: panelInfo, docs: panelDocs, contact: panelContact, steps: panelSteps }[dt](t)}</div>
    <div class="actionbar">
      ${official ? `<a class="btn" href="${h(official.url)}" target="_blank" rel="noopener">${ICON.out} الإعلان الرسمي</a>` : ''}
      <button class="btn btn--ghost btn--icon" data-act="share" aria-label="مشاركة" title="مشاركة">${ICON.share}</button>
      <select class="statussel" data-act="status" aria-label="حالة هذه الفرصة عندكم">${Object.entries(STATUS).map(([k, v]) => `<option value="${k}"${st.status === k ? ' selected' : ''}>${k ? v : 'الحالة'}</option>`).join('')}</select>
    </div>`;
}
function panelInfo(t) {
  const notes = (t.notes || []).map((n) => `<p class="note">${h(n)}</p>`).join('');
  const dates = (t.dates || []).map((d) => `<li><b>${h(d.label)}:</b> ${h(dLong(d.date))}${d.time ? ' – الساعة ' + h(d.time) : ''} <span class="muted small">(${relDay(d.date)})</span></li>`).join('');
  const links = (t.links || []).map((l) => `<a class="act" href="${h(l.url)}" target="_blank" rel="noopener">${ICON.out}<span class="act__t"><span>${h(l.label)}</span><small class="ltr">${h(host(l.url))}</small></span></a>`).join('');
  return `${notes}
    ${t.summary ? `<section class="box"><h3>عن المشروع</h3><p dir="auto">${h(t.summary)}</p></section>` : ''}
    <section class="box"><h3>المواعيد المهمة</h3>${dates ? `<ul class="steps-mini">${dates}</ul>` : '<p class="muted">لم تُذكر مواعيد في البيانات المتاحة — راجع الإعلان الرسمي.</p>'}
      ${t.deadline ? `<div class="d-tools" style="margin:6px 0 0"><button class="btn btn--ghost btn--sm" data-act="ics">${ICON.cal} أضف المواعيد إلى التقويم</button>
        <a class="btn btn--ghost btn--sm" target="_blank" rel="noopener" href="${gcal(t)}">${ICON.cal} تقويم Google</a></div>` : ''}</section>
    <section class="box"><h3>الروابط</h3><div class="actions">${links}</div></section>
    ${t.excerpt ? `<details class="box"><summary>نص الإعلان كما ورد في المصدر</summary><div class="excerpt" dir="auto">${h(t.excerpt)}</div></details>` : ''}`;
}
function panelDocs(t) {
  const st = tget(t.id);
  const c = counts(t);
  const items = t.documents.map((d, i) => `<li><label class="check${st.docs[i] ? ' is-done' : ''}"><input type="checkbox" data-act="doc" data-i="${i}"${st.docs[i] ? ' checked' : ''}>
    <span style="flex:1"><b>${h(d.title)}${d.from_notice ? '<span class="flag">مذكور في الإعلان</span>' : ''}</b><span>${h(d.detail)}</span></span></label></li>`).join('');
  const conds = (t.conditions || []).map((x) => `<p class="quote" dir="auto">${h(x)}</p>`).join('');
  const sim = similar(t);
  const simBox = refs.length
    ? (sim.length
      ? `<ul class="refs">${sim.map((r) => `<li dir="auto"><b>${h(r.t)}</b> <span class="muted small">${h(r.s)}${r.st ? ' – ' + h(r.st) : ''}</span></li>`).join('')}</ul>
         <button class="btn btn--ghost btn--sm" data-act="copyrefs">${ICON.copy} نسخ القائمة لجدول المشاريع المماثلة</button>`
      : '<p class="muted">لا توجد مشاريع سابقة بنفس التخصص في السجل المستورد.</p>')
    : `<p class="muted">استورد سجل مشاريعكم (ملف Excel) مرة واحدة من الإعدادات، وسيقترح التطبيق المشاريع المناسبة لكل فرصة. يبقى الملف على هذا الجهاز فقط.</p>
       <a class="btn btn--ghost btn--sm" href="#prefs">استيراد سجل المشاريع</a>`;
  return `${progress(c.d, t.documents.length, 'جهّزتم')}
    ${t.doc_note ? `<p class="note note--info">${h(t.doc_note)}</p>` : ''}
    <section class="box"><h3>الأوراق المطلوبة للتقديم</h3><ul class="checks">${items}</ul></section>
    ${conds ? `<section class="box"><h3>شروط وردت في نص الإعلان</h3>${conds}
      ${!t.is_arabic ? `<a class="btn btn--ghost btn--sm" target="_blank" rel="noopener" href="https://translate.google.com/?sl=auto&tl=ar&op=translate&text=${encodeURIComponent((t.conditions || []).join('\n\n'))}">ترجمة الشروط</a>` : ''}</section>` : ''}
    <section class="box"><h3>مشاريعكم المشابهة (لجدول الخبرات)</h3>${simBox}</section>`;
}
function mailText(t, lang) {
  const o = prefs.office || {};
  const c = (t.contacts || [])[0] || {};
  const ref = t.reference ? ` (Ref. ${t.reference})` : '';
  if (lang === 'en') {
    const fields = (t.match.ids || []).map((i) => EN[i]).filter(Boolean).slice(0, 3).join(', ') || 'infrastructure design';
    return {
      subject: `Inquiry${t.reference ? ' – ' + t.reference : ''} – ${t.title}`.slice(0, 160),
      body: `Dear ${c.name || 'Sir/Madam'},\n\nWith reference to your notice "${t.title}"${ref}, we are an engineering consultancy specialized in ${fields}, and we are interested in this assignment.\n\nWe kindly request:\n1. The Terms of Reference (ToR) and any related documents, if available.\n2. Clarification on: [write your question here]\n\nKindly confirm receipt of this email.\n\nBest regards,\n${o.person || '[Name]'}\n${o.name || '[Office name]'}\n${[o.phone, o.email].filter(Boolean).join(' | ') || '[Phone | E-mail]'}`,
    };
  }
  return {
    subject: `استفسار${t.reference ? ' – ' + t.reference : ''} – ${t.title}`.slice(0, 160),
    body: `السادة ${c.org || c.name || 'المحترمين'}،\nتحية طيبة وبعد،\n\nبالإشارة إلى إعلانكم بعنوان «${t.title}»${t.reference ? ` رقم ${t.reference}` : ''}، نود إفادتكم بأننا مكتب استشاري هندسي متخصص في ${(t.match.disciplines || []).slice(0, 3).join('، ') || 'تصميم البنية التحتية'}، ونرغب في المشاركة.\n\nنرجو التكرم بـ:\n1. تزويدنا بالشروط المرجعية ووثائق الطرح إن وُجدت.\n2. الإفادة بخصوص: [اكتب سؤالك هنا]\n\nونرجو التكرم بتأكيد الاستلام.\n\nوتفضلوا بقبول فائق الاحترام،\n${o.person || '[الاسم]'}\n${o.name || '[اسم المكتب]'}\n${[o.phone, o.email].filter(Boolean).join(' | ') || '[الهاتف | الإيميل]'}`,
  };
}
const mailto = (to, m) => `mailto:${encodeURIComponent(to || '')}?subject=${encodeURIComponent(m.subject)}&body=${encodeURIComponent(m.body)}`;
function contactCard(c, t, isEntity) {
  const lang = S.mailLang || (t.is_arabic ? 'ar' : 'en');
  const m = mailText(t, lang);
  const who = [c.name, c.org].filter(Boolean).join(' – ');
  let acts = '';
  (c.emails || []).forEach((e) => {
    acts += `<div class="act-row"><a class="act" href="${h(isEntity ? mailto(e, m) : 'mailto:' + e)}">${ICON.mail}<span class="act__t"><small>${isEntity ? 'إيميل – يفتح رسالة استفسار جاهزة' : 'إيميل'}</small><span class="ltr">${h(e).replace('@', '@<wbr>')}</span></span></a>
      <button class="copy" data-act="copy" data-text="${h(e)}" aria-label="نسخ ${h(e)}">${ICON.copy}</button></div>`;
  });
  (c.phones || []).forEach((p) => {
    acts += `<div class="act-row"><a class="act" href="tel:${h(p.tel)}">${ICON.phone}<span class="act__t"><small>${p.whatsapp ? 'اتصال أو واتساب' : 'اتصال'}</small><span class="ltr" style="white-space:nowrap">${h(p.display)}</span></span></a>
      ${p.whatsapp ? `<a class="copy act--wa" href="https://wa.me/${h(p.whatsapp)}" target="_blank" rel="noopener" aria-label="واتساب ${h(p.display)}" title="واتساب">${ICON.wa}</a>` : ''}
      <button class="copy" data-act="copy" data-text="${h(p.display)}" aria-label="نسخ الرقم">${ICON.copy}</button></div>`;
  });
  if (c.website) acts += `<a class="act" href="${h(c.website)}" target="_blank" rel="noopener">${ICON.web}<span class="act__t"><small>الموقع</small><span class="ltr">${h(c.website.replace(/^https?:\/\//, '').slice(0, 60))}</span></span></a>`;
  if (c.address) acts += `<a class="act" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(c.address)}" target="_blank" rel="noopener">${ICON.pin}<span class="act__t"><small>العنوان</small><span dir="auto">${h(c.address)}</span></span></a>`;
  return `<section class="box contact"><h3>${h(c.title)}</h3>${who ? `<p class="who" dir="auto">${h(who)}</p>` : ''}
    ${acts ? `<div class="actions">${acts}</div>` : ''}
    ${c.hours ? `<p class="small" style="margin-top:8px"><b>مواعيد العمل:</b> ${h(c.hours)}</p>` : ''}
    ${c.note ? `<p class="small muted" style="margin-top:8px">${h(c.note)}</p>` : ''}
    ${c.source ? `<p class="small muted">مصدر الرقم: ${h(c.source)}</p>` : ''}</section>`;
}
function panelContact(t) {
  const lang = S.mailLang || (t.is_arabic ? 'ar' : 'en');
  const m = mailText(t, lang);
  const entity = (t.contacts || [])[0] || {};
  const firstMail = (entity.emails || [])[0];
  const cards = (t.contacts || []).map((c, i) => contactCard(c, t, i === 0)).join('');
  const needOffice = !(prefs.office && prefs.office.name);
  return `<p class="note note--info"><b>طريقة الاستفسار:</b> ${h(t.inquiry_how)}</p>${cards}
    ${t.kind !== 'etimad' && t.kind !== 'news' ? `<section class="box"><h3>إيميل استفسار جاهز</h3>
      <div class="seg" role="group" aria-label="لغة الإيميل"><button data-act="mlang" data-l="en" aria-pressed="${lang === 'en'}">English</button><button data-act="mlang" data-l="ar" aria-pressed="${lang === 'ar'}">عربي</button></div>
      ${needOffice ? '<p class="small muted">أضف اسم المكتب ورقم الهاتف مرة واحدة من <a href="#prefs">الإعدادات</a> ليظهر توقيعكم تلقائياً.</p>' : ''}
      <textarea class="mail" id="mailBody" dir="${lang === 'en' ? 'ltr' : 'rtl'}" aria-label="نص الإيميل">${h(m.body)}</textarea>
      <div class="d-tools" style="margin:8px 0 0"><button class="btn btn--ghost btn--sm" data-act="copymail">${ICON.copy} نسخ النص</button>
        ${firstMail ? `<button class="btn btn--sm" data-act="openmail" data-to="${h(firstMail)}">${ICON.mail} فتح في البريد</button>` : ''}</div></section>` : ''}`;
}
function panelSteps(t) {
  const st = tget(t.id);
  const c = counts(t);
  const nowIdx = t.steps.findIndex((_, i) => !st.steps[i]);
  const items = t.steps.map((s, i) => {
    const late = s.due && pd(s.due) < today() && !st.steps[i];
    const isToday = s.due && diffDays(pd(s.due), today()) === 0;
    const dueTxt = s.due ? `${dLong(s.due)} (${relDay(s.due)})` : s.due_ar;
    return `<li class="station${st.steps[i] ? ' is-done' : ''}${i === nowIdx ? ' is-now' : ''}">
      <button class="station__n" data-act="step" data-i="${i}" aria-pressed="${!!st.steps[i]}" aria-label="الخطوة ${i + 1}: ${st.steps[i] ? 'تمت' : 'لم تتم'}">${st.steps[i] ? '✓' : i + 1}</button>
      <div class="station__b"><b>${h(s.title)}</b>${s.detail ? `<p dir="auto">${h(s.detail)}</p>` : ''}
        <span class="due${late ? ' due--late' : isToday ? ' due--today' : ''}">${h(dueTxt)}</span></div></li>`;
  }).join('');
  return `${progress(c.s, t.steps.length, 'أنجزتم')}
    <p class="small muted" style="margin:0 0 12px">اضغط رقم الخطوة عند إنجازها. التواريخ محسوبة من مواعيد الإعلان، وتظهر الأرقام نفسها على شريط المدة بالأعلى.</p>
    <ol class="route">${items}</ol>
    ${t.deadline ? `<div class="d-tools"><button class="btn btn--ghost btn--sm" data-act="ics">${ICON.cal} أضف المواعيد إلى التقويم</button></div>` : ''}`;
}

/* ------------------------------------------------------------------ calendar, share, copy */
const ymd = (s) => String(s).slice(0, 10).replace(/-/g, '');
function gcal(t) {
  const end = new Date(pd(t.deadline).getTime() + DAY);
  return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent('آخر موعد تقديم: ' + t.title.slice(0, 80))}`
    + `&dates=${ymd(t.deadline)}/${ymd(isoLocal(end))}&details=${encodeURIComponent(deepLink(t) + '\n' + (((t.links || [])[0] || {}).url || ''))}`;
}
function fold(line) { const out = []; while (line.length > 60) { out.push(line.slice(0, 60)); line = ' ' + line.slice(60); } out.push(line); return out.join('\r\n'); }
const icsEsc = (s) => String(s).replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');
function ics(t) {
  if (framed) { toast('نسخة العرض لا تسمح بتنزيل الملفات — استخدم زر «تقويم Google»'); return; }
  const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
  const ev = (uid, date, title, alarms) => {
    const end = isoLocal(new Date(pd(date).getTime() + DAY));
    const al = alarms.map((a) => ['BEGIN:VALARM', `TRIGGER:-P${a}D`, 'ACTION:DISPLAY', `DESCRIPTION:${icsEsc(title)}`, 'END:VALARM']).flat();
    return ['BEGIN:VEVENT', `UID:${uid}@tender-radar`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${ymd(date)}`, `DTEND;VALUE=DATE:${ymd(end)}`,
      fold(`SUMMARY:${icsEsc(title)}`), fold(`DESCRIPTION:${icsEsc(t.title + '\n' + deepLink(t))}`), ...al, 'END:VEVENT'];
  };
  let lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//TenderRadar//AR', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH'];
  lines = lines.concat(ev(t.id + '-d', t.deadline, 'آخر موعد تقديم: ' + t.title.slice(0, 70), [7, 2]));
  if (t.inquiry_deadline) lines = lines.concat(ev(t.id + '-q', t.inquiry_deadline, 'آخر موعد للاستفسارات: ' + t.title.slice(0, 60), [2]));
  lines.push('END:VCALENDAR');
  const blob = new Blob([lines.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `موعد-${(t.reference || t.id).replace(/[^\w\u0600-\u06FF-]+/g, '-')}.ics`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  toast('تم تنزيل ملف التقويم — افتحه لإضافة المواعيد مع تذكير قبلها بأسبوع ويومين');
}
const host = (u) => { try { return new URL(u).hostname; } catch (e) { return u; } };
const deepLink = (t) => location.href.split('#')[0] + '#t-' + t.id;
async function copy(text, msg) {
  try { await navigator.clipboard.writeText(text); } catch (e) {
    const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (er) { /* ignore */ } ta.remove();
  }
  toast(msg || 'تم النسخ');
}
async function share(t) {
  const text = `${t.title}\n${t.country_ar} – ${leftLabel(left(t))}`;
  if (navigator.share) { try { await navigator.share({ title: t.title, text, url: deepLink(t) }); return; } catch (e) { if (e.name === 'AbortError') return; } }
  copy(text + '\n' + deepLink(t), 'تم نسخ رابط الفرصة — الصقه في واتساب أو البريد');
}
let toastTimer;
function toast(msg) {
  const el = $('#toast'); el.textContent = msg; el.classList.add('on');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('on'), 3200);
}

/* ------------------------------------------------------------------ settings */
const isStandalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
function renderSettings() {
  const o = prefs.office || {};
  const s = S.status;
  const topic = prefs.ntfyTopic || '';
  const stale = s && !(S.data && S.data.demo) && Date.now() - Date.parse(s.last_run) > 3 * (s.every_minutes || 60) * 6e4;
  const row = (x, tag) => `<tr><td>${h(SOURCE_AR[x.key] || x.key)}${tag ? ` <small class="muted">${tag}</small>` : ''}</td><td>${x.ok ? `<span class="ok">يعمل</span>` : `<span class="bad">تعذر الوصول</span>`}</td><td>${x.count}</td></tr>`;
  const pc = (s && s.pc_helper) || {};
  const srcRows = s ? s.sources.filter((x) => x.key !== 'pc_relay').map((x) => row(x)).join('') + (pc.sources || []).map((x) => row(x, 'كمبيوتر المكتب')).join('') : '';
  const pcLine = !s ? '' : pc.linked === false ? `<p class="small">مساعد كمبيوتر المكتب${pc.label ? ` (${h(pc.label)})` : ''}: <span class="bad">لم يُربط بعد</span>.</p>`
    : pc.linked ? `<p class="small">مساعد كمبيوتر المكتب${pc.label ? ` (${h(pc.label)})` : ''}: ${pc.last_seen ? `آخر إرسال <b>${ago(pc.last_seen)}</b>` : '<span class="bad">لم يرسل نتائج خلال آخر 12 ساعة — تأكد أن كمبيوتر المكتب يعمل</span>'}.</p>` : '';
  const perm = typeof Notification === 'undefined' ? 'unsupported' : Notification.permission;
  $('#detailPane').innerHTML = `
    <button class="back" data-act="back">${ICON.back} كل الفرص</button>
    <h1 class="d-title">الإعدادات</h1>
    <p><a class="btn btn--ghost btn--sm" href="guide.html">دليل التشغيل الكامل خطوة بخطوة</a></p>
    <section class="box" id="notify"><h3>الإشعارات على الموبايل والكمبيوتر</h3>
      <p>ليصلك إشعار لكل فرصة جديدة حتى والتطبيق مغلق، نستخدم تطبيق <b>ntfy</b> المجاني (بدون حساب):</p>
      <ol class="steps-mini">
        <li>ثبّت ntfy: <a href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank" rel="noopener">أندرويد</a> أو <a href="https://apps.apple.com/app/id1625396347" target="_blank" rel="noopener">آيفون</a>. على الكمبيوتر يكفي المتصفح.</li>
        <li>اكتب اسم قناة مكتبكم — نفس الاسم المحفوظ في GitHub باسم NTFY_TOPIC.</li>
        <li>اضغط «اشترك الآن». كل من يشترك في نفس الاسم تصله الإشعارات.</li>
      </ol>
      <div class="form"><label>اسم القناة<input id="topic" dir="ltr" value="${h(topic)}" placeholder="delta-radar-xxxxxx" autocomplete="off"></label></div>
      <div class="d-tools" style="margin:10px 0 0"><button class="btn btn--ghost btn--sm" data-act="savetopic">حفظ الاسم</button>
        <button class="btn btn--ghost btn--sm" data-act="gentopic">اقترح اسماً عشوائياً</button></div>
      ${topic ? `<div class="actions two" style="margin-top:10px"><a class="act" href="ntfy://ntfy.sh/${h(topic)}">${ICON.phone}<span class="act__t"><small>على الموبايل (بعد تثبيت ntfy)</small><span>اشترك الآن في التطبيق</span></span></a>
        <a class="act" href="https://ntfy.sh/${h(topic)}" target="_blank" rel="noopener">${ICON.web}<span class="act__t"><small>على الكمبيوتر أو لو لم يعمل الزر الأول</small><span>اشترك من المتصفح</span></span></a></div>` : ''}
      <hr style="border:0;border-top:1px solid var(--rule-2);margin:14px 0">
      <p class="small"><b>تنبيه من التطبيق نفسه:</b> يعرض إشعاراً بالفرص الجديدة عند فتح التطبيق (وعلى أندرويد أحياناً في الخلفية).</p>
      <button class="btn btn--ghost btn--sm" data-act="localnotify"${perm === 'unsupported' || framed ? ' disabled' : ''}>${prefs.notifyLocal && perm === 'granted' ? 'مفعّل ✓ — اضغط للإيقاف' : 'تفعيل تنبيه التطبيق'}</button>
      ${perm === 'denied' ? '<p class="small bad">الإشعارات محظورة لهذا الموقع من إعدادات المتصفح.</p>' : ''}</section>
    <section class="box" id="install"><h3>تثبيت التطبيق على جهازك</h3>
      ${framed ? '<p class="note note--info">هذه نسخة عرض داخل صفحة أخرى، فلا يمكن تثبيتها. بعد التشغيل على GitHub افتحوا رابط تطبيقكم مباشرة وثبّتوه بالطريقة التالية.</p>' : ''}
      ${isStandalone() ? '<p class="ok">التطبيق مثبّت على هذا الجهاز.</p>' : `
      ${S.installEvt ? `<p><button class="btn" data-act="install">تثبيت الآن</button></p>` : ''}
      <ul class="steps-mini">
        <li><b>آيفون:</b> افتح الرابط من Safari ← زر المشاركة ⬆︎ ← «إضافة إلى الشاشة الرئيسية».</li>
        <li><b>أندرويد:</b> افتح الرابط من Chrome ← القائمة ⋮ ← «تثبيت التطبيق» أو «إضافة إلى الشاشة الرئيسية».</li>
        <li><b>الكمبيوتر:</b> افتح الرابط من Chrome أو Edge ← أيقونة التثبيت في آخر شريط العنوان، أو القائمة ← «تثبيت رادار المناقصات».</li>
      </ul>`}</section>
    <section class="box"><h3>بيانات مكتبكم</h3><p class="small muted">تظهر كتوقيع في إيميلات الاستفسار الجاهزة. تُحفظ على هذا الجهاز فقط.</p>
      <div class="form">
        <label>اسم المكتب<input id="oName" value="${h(o.name || '')}" placeholder="CEC – Delta Office"></label>
        <label>اسم المسؤول<input id="oPerson" value="${h(o.person || '')}"></label>
        <label>الهاتف<input id="oPhone" dir="ltr" value="${h(o.phone || '')}" inputmode="tel"></label>
        <label>الإيميل<input id="oEmail" dir="ltr" value="${h(o.email || '')}" inputmode="email"></label>
      </div>
      <div class="d-tools" style="margin:10px 0 0"><button class="btn btn--sm" data-act="saveoffice">حفظ</button></div></section>
    <section class="box"><h3>سجل مشاريعكم السابقة</h3>
      <p>استورد ملف Excel لسجل المشاريع (Master Projects Register) ليقترح التطبيق مشاريعكم المشابهة لكل فرصة. <b>الملف يبقى على هذا الجهاز ولا يُرفع لأي مكان.</b></p>
      <p class="small">${refs.length ? `محفوظ الآن: ${refs.length} مشروع.` : 'لم يتم الاستيراد بعد.'}</p>
      <div class="d-tools" style="margin:0"><button class="btn btn--ghost btn--sm" data-act="importrefs">اختيار ملف Excel</button>
        ${refs.length ? '<button class="btn btn--ghost btn--sm" data-act="clearrefs">حذف السجل من الجهاز</button>' : ''}</div></section>
    <section class="box"><h3>حالة الرادار</h3>
      ${s ? `<p>آخر فحص: <b>${ago(s.last_run)}</b> — يفحص كل ${s.every_minutes || 60} دقيقة.</p>
        ${stale ? '<p class="bad">الفحص متأخر عن موعده. في التشغيل السحابي: افتح GitHub ← Actions وتأكد أن Tender Radar يعمل.</p>' : ''}
        <p class="small">في آخر فحص — الإعلانات المقروءة: ${s.collected}، المناسب لتخصصاتكم: ${s.matched}، الفرص المفتوحة الآن: ${s.open}.</p>
        <table class="src"><thead><tr><th>المصدر</th><th>الحالة</th><th>الإعلانات</th></tr></thead><tbody>${srcRows}</tbody></table>
        ${pcLine}
        <p class="small" style="margin-top:10px">قنوات الإشعار المفعّلة على الخادم: ${['ntfy', 'telegram', 'email'].filter((k) => s.channels && s.channels[k]).map((k) => ({ ntfy: 'ntfy', telegram: 'تيليجرام', email: 'الإيميل' })[k]).join('، ') || '<span class="bad">لا شيء بعد — أضف NTFY_TOPIC في GitHub</span>'}</p>`
        : '<p class="muted">لا توجد بيانات حالة بعد.</p>'}</section>
    <section class="box"><h3>عن البيانات</h3><p class="small">المصادر: البنك الدولي، منصة اعتماد، بوابة الأمم المتحدة UNGM، مجلس المناقصات العُماني، مجلس المناقصات بالبحرين، بوابات الإمارات (المنصة الاتحادية، eSupply دبي، ADGPG أبوظبي، وهيئة كهرباء ومياه دبي)، البنك الأوروبي لإعادة الإعمار EBRD، منصة مناقصات قطر وكامل قائمة مجلس المناقصات العُماني (يفحصهما مساعد كمبيوتر المكتب لأنهما يمنعان السيرفرات السحابية؛ والجهاز المركزي للمناقصات بالكويت يمنع الفحص الآلي فيُراجع من رابطه)، البنك الإسلامي للتنمية، وأخبار الطروحات. الأرقام والإيميلات مأخوذة من نص الإعلان نفسه، وأرقام الدعم الفني للبوابات من مواقعها الرسمية. راجعوا الإعلان الرسمي دائماً قبل التقديم.</p></section>`;
}
function randomTopic() {
  const a = new Uint8Array(6); (crypto || window.msCrypto).getRandomValues(a);
  return 'delta-radar-' + [...a].map((b) => 'abcdefghjkmnpqrstuvwxyz23456789'[b % 31]).join('');
}

/* ------------------------------------------------------------------ Excel import (xlsx = zip of XML) */
async function unzip(buf) {
  const u8 = new Uint8Array(buf); const dv = new DataView(buf);
  let eocd = -1;
  for (let i = u8.length - 22; i >= Math.max(0, u8.length - 65557); i--) { if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; } }
  if (eocd < 0) throw new Error('ليس ملف Excel صالحاً');
  const count = dv.getUint16(eocd + 10, true); let p = dv.getUint32(eocd + 16, true);
  const files = {};
  for (let i = 0; i < count; i++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const method = dv.getUint16(p + 10, true); const csize = dv.getUint32(p + 20, true);
    const nlen = dv.getUint16(p + 28, true); const elen = dv.getUint16(p + 30, true); const clen = dv.getUint16(p + 32, true);
    const off = dv.getUint32(p + 42, true);
    files[new TextDecoder().decode(u8.subarray(p + 46, p + 46 + nlen))] = { method, csize, off };
    p += 46 + nlen + elen + clen;
  }
  return async (name) => {
    const f = files[name]; if (!f) return '';
    const start = f.off + 30 + dv.getUint16(f.off + 26, true) + dv.getUint16(f.off + 28, true);
    const data = u8.subarray(start, start + f.csize);
    if (f.method === 0) return new TextDecoder().decode(data);
    const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    return new Response(stream).text();
  };
}
const xdec = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'")
  .replace(/&#(\d+);/g, (m, n) => String.fromCharCode(+n)).replace(/&#x([0-9a-f]+);/gi, (m, n) => String.fromCharCode(parseInt(n, 16))).replace(/&amp;/g, '&');
async function readXlsx(buf) {
  const read = await unzip(buf);
  const ss = await read('xl/sharedStrings.xml');
  const shared = [...ss.matchAll(/<si>([\s\S]*?)<\/si>/g)].map((m) => [...m[1].matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((x) => xdec(x[1])).join(''));
  const wb = await read('xl/workbook.xml'); const rels = await read('xl/_rels/workbook.xml.rels');
  const sheets = [...wb.matchAll(/<sheet\b[^>]*>/g)].map((m) => ({ name: xdec((m[0].match(/name="([^"]*)"/) || [])[1] || ''), rid: (m[0].match(/r:id="([^"]*)"/) || [])[1] }));
  const relMap = {};
  for (const m of rels.matchAll(/<Relationship\b[^>]*>/g)) relMap[(m[0].match(/Id="([^"]*)"/) || [])[1]] = (m[0].match(/Target="([^"]*)"/) || [])[1];
  const sh = sheets.find((s) => /master|register|projects|مشاريع/i.test(s.name)) || sheets[0];
  const target = (relMap[sh.rid] || 'worksheets/sheet1.xml').replace(/^\/?xl\//, '').replace(/^\//, '');
  const xml = await read('xl/' + target);
  const rows = [];
  for (const rm of xml.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)) {
    const row = [];
    for (const cm of rm[1].matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
      const attrs = cm[1]; const body = cm[2] || '';
      const ref = (attrs.match(/r="([A-Z]+)\d+"/) || [])[1]; const type = (attrs.match(/t="([^"]+)"/) || [])[1];
      const col = ref ? [...ref].reduce((a, ch) => a * 26 + ch.charCodeAt(0) - 64, 0) - 1 : row.length;
      const vm = body.match(/<v>([\s\S]*?)<\/v>/);
      let v = '';
      if (type === 's' && vm) v = shared[+vm[1]] || '';
      else if (type === 'inlineStr') v = [...body.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((x) => xdec(x[1])).join('');
      else if (vm) v = xdec(vm[1]);
      row[col] = v;
    }
    rows.push(row);
  }
  return rows;
}
function rowsToRefs(rows) {
  const hi = rows.findIndex((r) => r && r.some((c) => /project title|اسم المشروع/i.test(c || '')));
  if (hi < 0) throw new Error('لم أجد عمود «Project Title» أو «اسم المشروع» في الملف');
  const H = rows[hi].map((c) => String(c || '').toLowerCase());
  const col = (re) => H.findIndex((c) => re.test(c));
  const ci = { title: col(/project title|اسم المشروع/), client: col(/client|العميل/), scope: col(/scope|النطاق/),
    tasks: col(/discipline|task|التخصص|المهام/), status: col(/overall status|^status|الحالة/), remarks: col(/remark|ملاحظات/) };
  const g = (r, i) => (i >= 0 ? String(r[i] || '').trim() : '');
  const out = [];
  for (const r of rows.slice(hi + 1)) {
    const title = g(r, ci.title);
    if (!title) continue;
    out.push({ t: title, c: g(r, ci.client), s: [g(r, ci.scope), g(r, ci.tasks)].filter(Boolean).join(' / '), st: g(r, ci.status),
      ids: classify([title, g(r, ci.scope), g(r, ci.tasks), g(r, ci.remarks)].join(' ')) });
  }
  return out;
}
async function importRefs(file) {
  try {
    let list;
    if (/\.json$/i.test(file.name)) list = JSON.parse(await file.text()).map((r) => ({ t: r.title || r.t, c: r.client || r.c || '', s: r.scope || r.s || '', st: r.status || r.st || '', ids: r.ids || classify([r.title, r.scope].join(' ')) }));
    else {
      if (typeof DecompressionStream === 'undefined') throw new Error('المتصفح قديم ولا يدعم قراءة Excel — جرّب Chrome أو Edge حديث');
      list = rowsToRefs(await readXlsx(await file.arrayBuffer()));
    }
    refs = list; store.set('tr.refs', refs);
    toast(`تم استيراد ${refs.length} مشروع — تظهر المشاريع المشابهة في تبويب «الأوراق المطلوبة»`);
    render();
  } catch (e) { toast('تعذر الاستيراد: ' + e.message); }
}

/* ------------------------------------------------------------------ notifications from the app itself */
async function syncMeta() {
  try {
    if (!('caches' in window)) return;
    const c = await caches.open('tr-meta');
    await c.put('known.json', new Response(JSON.stringify(prefs.known || [])));
    await c.put('prefs.json', new Response(JSON.stringify({ notifyLocal: prefs.notifyLocal })));
  } catch (e) { /* ignore */ }
}
async function notifyFresh() {
  const ids = all().map((t) => t.id);
  if (!ids.length) return;
  const known = new Set(prefs.known || []);
  const fresh = known.size ? all().filter((t) => !known.has(t.id)) : [];
  if (fresh.length) {
    toast(fresh.length === 1 ? 'وصلت فرصة جديدة' : `وصلت ${fresh.length} فرص جديدة`);
    if (prefs.notifyLocal && typeof Notification !== 'undefined' && Notification.permission === 'granted' && navigator.serviceWorker) {
      try {
        const reg = await navigator.serviceWorker.ready;
        fresh.slice(0, 5).forEach((t) => reg.showNotification(`فرصة جديدة – ${t.country_ar}`, {
          body: `${t.title}\n${leftLabel(left(t))}`, tag: t.id, dir: 'rtl', lang: 'ar',
          icon: 'icons/icon-192.png', badge: 'icons/badge-96.png', data: { url: `./#t-${t.id}` } }));
      } catch (e) { /* ignore */ }
    }
  }
  prefs.known = ids; savePrefs();
}
async function toggleLocalNotify() {
  if (prefs.notifyLocal && Notification.permission === 'granted') { prefs.notifyLocal = false; savePrefs(); render(); return; }
  const p = await Notification.requestPermission();
  prefs.notifyLocal = p === 'granted'; savePrefs();
  if (p === 'granted') {
    toast('تم تفعيل تنبيه التطبيق');
    try {
      const reg = await navigator.serviceWorker.ready;
      if ('periodicSync' in reg) {
        const st = await navigator.permissions.query({ name: 'periodic-background-sync' });
        if (st.state === 'granted') await reg.periodicSync.register('tr-check', { minInterval: 60 * 60 * 1000 });
      }
    } catch (e) { /* not supported */ }
  }
  render();
}

/* ------------------------------------------------------------------ banners, status line, nav */
function renderBanner() {
  const b = [];
  if (S.data && S.data.demo) b.push('<div class="banner banner--demo"><span><b>نسخة عرض ببيانات تجريبية.</b> كل الجهات والأرقام والإيميلات هنا أمثلة وليست مناقصات حقيقية.</span></div>');
  if (!framed && !isStandalone() && !prefs.dismiss.install && (S.installEvt || isIOS())) {
    b.push(`<div class="banner banner--install"><span>ثبّت «رادار المناقصات» على جهازك ليفتح كبرنامج مستقل.</span>
      <span>${S.installEvt ? '<button class="btn btn--sm" data-act="install">تثبيت</button>' : '<a class="btn btn--sm" href="#prefs">الطريقة</a>'}
      <button class="btn btn--ghost btn--sm" data-act="dismiss" data-k="install">لاحقاً</button></span></div>`);
  }
  $('#banner').innerHTML = b.join('');
}
function renderStatus() {
  const s = S.status; const el = $('#status');
  if (!s) { el.textContent = S.data && S.data.missing ? 'لا توجد بيانات بعد' : ''; return; }
  const stale = !(S.data && S.data.demo) && Date.now() - Date.parse(s.last_run) > 3 * (s.every_minutes || 60) * 6e4;
  const open = all().filter(isOpen).length;
  el.innerHTML = `آخر فحص <b>${ago(s.last_run)}</b> – ${plural(open)} مفتوحة${stale ? ' – <span class="warn">الفحص متأخر، راجع الإعدادات</span>' : ''}`;
}
function updateNav() {
  const r = S.route;
  const cur = r.view === 'settings' ? 'settings' : r.tab === 'mine' ? 'mine' : 'list';
  document.querySelectorAll('[data-nav]').forEach((a) => (a.dataset.nav === cur ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  document.documentElement.style.setProperty('--top-h', $('.top').offsetHeight + 'px');
}
function renderPlaceholder() {
  $('#detailPane').innerHTML = `<div class="empty" style="text-align:start;max-width:560px;margin:40px auto">
    <b>اختر فرصة من القائمة</b>
    <p>لكل فرصة أربعة أقسام: البيانات، والأوراق المطلوبة، وجهة التواصل بأرقامها وإيميلاتها، وخطوات التقديم بالترتيب مع مواعيدها.</p>
    <p>الشريط المقسّم تحت كل فرصة يمثل المدة من النشر حتى آخر موعد، وكل قطعة فيه أسبوع: الجزء الداكن هو ما مضى.</p></div>`;
}

/* ------------------------------------------------------------------ routing & render */
function parseHash() {
  // plain hashes (#all, #new, #t-<id>, #t-<id>--docs, #prefs); the older #/t/<id>/<tab> form still works
  const raw = decodeURIComponent(location.hash.replace(/^#\/?/, ''));
  const m = raw.match(/^t[-/]([a-z0-9]+-[0-9a-f]{10})(?:(?:--|\/)(info|docs|contact|steps))?$/);
  if (m) return { view: 'detail', id: m[1], dtab: m[2] || 'info', tab: S.lastTab };
  if (raw === 'prefs' || raw === 'settings') return { view: 'settings', tab: S.lastTab, id: null };
  const legacy = (raw.match(/tab=(\w+)/) || [])[1];
  const tab = ['new', 'soon', 'all', 'mine'].includes(raw) ? raw : legacy || S.lastTab || 'all';
  return { view: 'list', tab, id: null };
}
function route() {
  const prev = S.route;
  S.route = parseHash();
  S.lastTab = S.route.tab;
  render(prev);
}
function render(prev) {
  const r = S.route;
  document.body.classList.toggle('view-detail', r.view !== 'list');
  if (r.view === 'detail' && r.id && byId(r.id) && !prefs.opened[r.id]) { prefs.opened[r.id] = Date.now(); savePrefs(); }
  const needControls = !$('#results') || !prev || prev.tab !== r.tab || !render.done;
  if (needControls) renderListControls();
  render.done = true;
  renderResults();
  if (r.view === 'detail') renderDetail();
  else if (r.view === 'settings') renderSettings();
  else renderPlaceholder();
  renderStatus(); renderBanner(); updateNav();
  if (prev && (prev.view !== r.view || prev.id !== r.id) && window.innerWidth < 1000) window.scrollTo(0, 0);
}
render.done = false;

/* ------------------------------------------------------------------ events */
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (!el) return;
  const act = el.dataset.act;
  const t = S.route.id ? byId(S.route.id) : null;
  if (['doc', 'status'].includes(act)) return;  // handled on change
  if (act === 'tab') { location.hash = `#${el.dataset.tab}`; return; }
  if (act === 'dtab') { history.replaceState(null, '', `#t-${S.route.id}--${el.dataset.dtab}`); S.route.dtab = el.dataset.dtab; renderDetail(); return; }
  if (act === 'back') { if (S.cameFromList) { S.cameFromList = false; history.back(); } else location.hash = `#${S.lastTab}`; return; }
  if (act === 'step' && t) {
    const st = tget(t.id); const i = +el.dataset.i; st.steps[i] = !st.steps[i]; tset(t.id, st);
    $('.dpanel').innerHTML = panelSteps(t); const c = counts(t); const sc = $('[data-scount]'); if (sc) sc.textContent = `${c.s}/${t.steps.length}`;
    const b = document.querySelector(`.station__n[data-i="${i}"]`); if (b) b.focus();
    return;
  }
  if (act === 'copy') { copy(el.dataset.text); return; }
  if (act === 'copymail') { copy($('#mailBody').value, 'تم نسخ نص الإيميل'); return; }
  if (act === 'openmail' && t) {
    const m = mailText(t, S.mailLang || (t.is_arabic ? 'ar' : 'en'));
    location.href = mailto(el.dataset.to, { subject: m.subject, body: $('#mailBody').value });
    return;
  }
  if (act === 'mlang') { S.mailLang = el.dataset.l; $('.dpanel').innerHTML = panelContact(t); return; }
  if (act === 'copyrefs' && t) { copy(similar(t).map((r) => `- ${r.t}${r.c ? ' – ' + r.c : ''}${r.s ? ' (' + r.s + ')' : ''}`).join('\n'), 'تم نسخ قائمة المشاريع'); return; }
  if (act === 'ics' && t) { ics(t); return; }
  if (act === 'share' && t) { share(t); return; }
  if (act === 'install' && S.installEvt) { S.installEvt.prompt(); S.installEvt.userChoice.finally(() => { S.installEvt = null; renderBanner(); }); return; }
  if (act === 'dismiss') { prefs.dismiss[el.dataset.k] = Date.now(); savePrefs(); renderBanner(); return; }
  if (act === 'savetopic') { prefs.ntfyTopic = $('#topic').value.trim().replace(/[^\w-]/g, ''); savePrefs(); renderSettings(); toast('تم حفظ اسم القناة'); return; }
  if (act === 'gentopic') { $('#topic').value = randomTopic(); toast('اسم مقترح — احفظه، وضعه نفسه في GitHub باسم NTFY_TOPIC'); return; }
  if (act === 'localnotify') { toggleLocalNotify(); return; }
  if (act === 'saveoffice') {
    prefs.office = { name: $('#oName').value.trim(), person: $('#oPerson').value.trim(), phone: $('#oPhone').value.trim(), email: $('#oEmail').value.trim() };
    savePrefs(); toast('تم حفظ بيانات المكتب'); return;
  }
  if (act === 'importrefs') { $('#fileRefs').click(); return; }
  if (act === 'clearrefs') { refs = []; store.set('tr.refs', []); renderSettings(); toast('تم حذف السجل من هذا الجهاز'); }
});
document.addEventListener('change', (e) => {
  const el = e.target;
  const t = S.route.id ? byId(S.route.id) : null;
  if (el.dataset.act === 'doc' && t) {
    const st = tget(t.id); const i = +el.dataset.i; st.docs[i] = el.checked; tset(t.id, st);
    el.closest('.check').classList.toggle('is-done', el.checked);
    const c = counts(t); const dc = $('[data-dcount]'); if (dc) dc.textContent = `${c.d}/${t.documents.length}`;
    const pr = $('.dpanel .progress'); if (pr) pr.outerHTML = progress(c.d, t.documents.length, 'جهّزتم');
    return;
  }
  if (el.dataset.act === 'status' && t) {
    const st = tget(t.id); st.status = el.value; tset(t.id, st);
    toast(el.value ? `الحالة: ${STATUS[el.value]}` : 'تم إلغاء الحالة'); renderResults(); return;
  }
  if (el.id === 'fCountry') { S.country = el.value; renderResults(); }
  if (el.id === 'fDisc') { S.disc = el.value; renderResults(); }
  if (el.id === 'fSort') { S.sort = el.value; renderResults(); }
  if (el.id === 'fileRefs' && el.files[0]) { importRefs(el.files[0]); el.value = ''; }
});
document.addEventListener('input', (e) => { if (e.target.id === 'q') { S.q = e.target.value; renderResults(); } });
document.addEventListener('click', (e) => { if (e.target.closest('.sheet')) S.cameFromList = true; }, true);
window.addEventListener('hashchange', route);
window.addEventListener('resize', updateNav);
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); S.installEvt = e; renderBanner(); if (S.route.view === 'settings') renderSettings(); });
window.addEventListener('appinstalled', () => { S.installEvt = null; toast('تم تثبيت التطبيق'); renderBanner(); });
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') load(false); });
setInterval(() => { if (document.visibilityState === 'visible') load(false); }, 10 * 60 * 1000);
if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
load(true);
