/* إضافة «التثبيت المباشر» — مستقلة عن كود المكتبة.
   إذا فشلت أو كان السجل فارغاً لا يظهر شيء ويبقى الموقع كما هو. */
(function () {
  'use strict';
  const TYPES = { adhoc: 'Ad Hoc — للأجهزة المسجّل UDID الخاص بها فقط', enterprise: 'Enterprise — توزيع مؤسسي للمخوّلين فقط' };
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  const https = v => { try { const u = new URL(String(v)); return u.protocol === 'https:' ? u.href : ''; } catch { return ''; } };
  const norm = v => { try { return new URL(String(v)).href; } catch { return ''; } };
  const ua = navigator.userAgent;
  /* iPadOS يعرّف نفسه كـ Macintosh، لذلك نفحص اللمس أيضاً */
  const isIOS = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  const inApp = isIOS && (!/Safari\//.test(ua) || /CriOS|FxiOS|EdgiOS|Instagram|FBAN|FBAV|Line\//.test(ua));
  const installURL = manifest => 'itms-services://?action=download-manifest&url=' + encodeURIComponent(manifest);

  let items = [], section, grid, status, search;

  /* كل شهادة وكل خيار يُقرأ منفرداً: سجل تالف لا يُسقط البقية */
  function collect(registry) {
    const out = [];
    for (const cert of Array.isArray(registry?.certificates) ? registry.certificates : []) {
      try {
        const auth = cert.authorization || {};
        if (cert.enabled !== true || !TYPES[cert.type] || !String(auth.grantedBy || '').trim() || !String(auth.reference || '').trim()) continue;
        if (!(Date.parse(cert.expiresAt) > Date.now())) continue;
        for (const x of Array.isArray(cert.installs) ? cert.installs : []) {
          if (!x || !x.id || !x.name || !x.bundleIdentifier || !https(x.manifestURL)) continue;
          out.push({ cert, x, state: 'checking', catalog: norm(x.catalogDownloadURL) });
        }
      } catch { /* تجاهل هذه الشهادة فقط */ }
    }
    return out;
  }

  async function check(item) {
    item.state = 'checking'; render();
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 20000);
    try {
      const q = new URLSearchParams({ cert: item.cert.id, install: item.x.id });
      const r = await fetch('./api/cert-status?' + q, { signal: ctl.signal, cache: 'no-store' });
      const d = await r.json();
      item.state = r.ok && d.ok === true ? 'ok' : 'down';
    } catch { item.state = 'unknown'; }
    finally { clearTimeout(timer); }
    render();
  }

  /* ثلاثة فحوص متزامنة كحد أقصى */
  async function checkAll(list) {
    const queue = [...list];
    await Promise.all([0, 1, 2].map(async () => { while (queue.length) await check(queue.shift()); }));
  }

  function installLink(item, label) {
    const a = el('a', 'button primary ci-install', label || 'تثبيت');
    a.href = installURL(https(item.x.manifestURL));
    a.addEventListener('click', e => {
      if (Date.parse(item.cert.expiresAt) <= Date.now()) { e.preventDefault(); status.textContent = 'انتهت صلاحية هذه الشهادة.'; return; }
      if (!isIOS) { e.preventDefault(); status.textContent = 'التثبيت المباشر يعمل من iPhone أو iPad فقط. افتح الموقع من Safari على جهازك.'; return; }
      status.textContent = 'إذا ظهرت نافذة التأكيد اضغط «تثبيت»، ثم تابع من الشاشة الرئيسية. إذا لم يظهر شيء افتح الموقع في Safari.';
    });
    return a;
  }

  function card(item) {
    const box = el('article', 'ci-card');
    const head = el('div', 'ci-head');
    const img = el('img'); img.alt = ''; img.width = img.height = 56; img.loading = 'lazy';
    const fallback = 'https://raw.githubusercontent.com/sgad73055-code/ipastrong/main/source-icon.jpeg';
    img.src = https(item.x.iconURL) || fallback;
    img.addEventListener('error', () => { img.src = fallback; }, { once: true });
    const title = el('div');
    const name = el('h3', '', item.x.name); name.dir = 'auto';
    title.append(name, el('p', '', item.x.version ? 'الإصدار ' + item.x.version : ''));
    head.append(img, title);
    box.append(head, el('p', 'ci-cert', item.cert.label || item.cert.id), el('p', 'ci-type', TYPES[item.cert.type]));
    if (item.state === 'ok') box.append(installLink(item));
    else {
      const b = el('button', 'button', item.state === 'checking' ? 'جارٍ فحص الروابط…' : 'تعذّر الفحص — أعد المحاولة');
      b.type = 'button'; b.disabled = item.state === 'checking'; b.onclick = () => check(item); box.append(b);
    }
    return box;
  }

  function render() {
    if (!grid) return;
    const q = search.value.trim().toLocaleLowerCase();
    /* الروابط المتعطلة لا تُعرض */
    const match = items.filter(i => !q || (i.x.name + ' ' + (i.cert.label || '')).toLocaleLowerCase().includes(q));
    const visible = match.filter(i => i.state !== 'down');
    grid.replaceChildren(...visible.map(card));
    const down = items.filter(i => i.state === 'down').length;
    const note = section.querySelector('.ci-down');
    note.hidden = !down;
    note.firstChild.textContent = 'خيارات متوقفة حالياً ومخفية: ' + down + ' ';
    if (!visible.length) grid.append(el('p', 'ci-empty', q && !match.length ? 'ما لكينا تطبيق بهذا الاسم.' : 'لا يوجد خيار تثبيت متاح حالياً.'));
  }

  function build() {
    section = el('section', 'wrap ci'); section.id = 'direct-install'; section.setAttribute('aria-labelledby', 'ciTitle');
    const h = el('h2', '', 'التثبيت المباشر'); h.id = 'ciTitle';
    section.append(h, el('p', 'ci-lead', 'اختار التطبيق واضغط تثبيت من Safari على iPhone أو iPad. فحص الموقع يتأكد من الروابط فقط، ولا يضمن أن Apple لم تُلغِ الشهادة أو أن جهازك مشمول بها.'));
    if (inApp) section.append(el('p', 'ci-warn', 'يبدو أنك داخل متصفح غير Safari. افتح الموقع في Safari حتى يعمل التثبيت.'));
    search = el('input', 'ci-search'); search.type = 'search'; search.placeholder = 'ابحث ضمن تطبيقات التثبيت المباشر…'; search.setAttribute('aria-label', search.placeholder); search.oninput = render;
    status = el('p', 'ci-status'); status.setAttribute('role', 'status');
    grid = el('div', 'ci-grid');
    const note = el('p', 'ci-down'); note.hidden = true;
    const retry = el('button', 'button ghost', 'إعادة الفحص'); retry.type = 'button';
    retry.onclick = () => checkAll(items.filter(i => i.state === 'down'));
    note.append(document.createTextNode(''), retry);
    section.append(search, status, grid, note);
    document.getElementById('library').before(section);
    document.querySelectorAll('.nav, .tabbar').forEach(nav => {
      const a = el('a', '', 'تثبيت'); a.href = '#direct-install';
      if (nav.classList.contains('tabbar')) {
        const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg'), use = document.createElementNS(NS, 'use');
        svg.setAttribute('class', 'ic'); svg.setAttribute('aria-hidden', 'true'); use.setAttribute('href', '#i-down'); svg.append(use); a.prepend(svg);
      }
      nav.insertBefore(a, nav.querySelector('a[href="#packages"]'));
    });
  }

  /* زر داخل نافذة تفاصيل التطبيق، فقط عند تطابق رابط الكتالوج حرفياً مع خيار فحصه ناجح */
  function hookDialog() {
    const dialog = document.getElementById('details');
    if (!dialog) return;
    new MutationObserver(() => {
      dialog.querySelectorAll('.ci-in-dialog').forEach(n => n.remove());
      if (!dialog.open) return;
      const url = typeof current !== 'undefined' && current ? norm(current.downloadURL) : '';
      if (!url) return;
      const foot = dialog.querySelector('.dialog-foot');
      const found = items.filter(i => i.state === 'ok' && i.catalog === url);
      for (const item of found.reverse()) {
        const a = installLink(item, 'تثبيت مباشر — ' + (item.cert.label || item.cert.id));
        a.classList.add('ci-in-dialog'); foot.prepend(a);
      }
    }).observe(dialog, { attributes: true, attributeFilter: ['open'] });
  }

  async function start() {
    try {
      const r = await fetch('./certs/registry.json', { cache: 'no-cache' });
      if (!r.ok) return;
      items = collect(await r.json());
      if (!items.length) return;
      build(); hookDialog(); render();
      await checkAll(items);
    } catch (err) { console.warn('IPA Strong: direct install unavailable', err); }
  }
  start();
})();
