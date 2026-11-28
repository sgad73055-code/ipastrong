/* منطق مشترك لفحص روابط OTA. لا يقرأ ولا يخزّن أي شهادة أو مفتاح خاص. */
export const LIMITS = { manifestBytes: 256 * 1024, redirects: 4, timeoutMs: 10000 };

/* https فقط، باسم نطاق عام: بدون IP أو localhost أو منفذ مخصص أو بيانات دخول */
export function publicHttpsURL(value) {
  let u;
  try { u = new URL(String(value)); } catch { return null; }
  const h = u.hostname.toLowerCase().replace(/\.$/, '');
  if (u.protocol !== 'https:' || u.username || u.password || u.port) return null;
  if (!h.includes('.') || h.startsWith('[') || /^[\d.]+$/.test(h)) return null;
  if (/(^|\.)(localhost|local|internal|lan|home\.arpa)$/.test(h)) return null;
  return u;
}

/* قارئ صغير لملفات plist النصية (XML). لا يوجد DOMParser داخل Workers. */
export function parsePlist(xml) {
  const src = String(xml).replace(/<!--[\s\S]*?-->/g, '').replace(/<\?[\s\S]*?\?>/g, '').replace(/<!DOCTYPE[^>]*>/gi, '').trim();
  const tokens = src.match(/<!\[CDATA\[[\s\S]*?\]\]>|<[^>]+>|[^<]+/g) || [];
  let i = 0, depth = 0;
  const fail = () => { throw new Error('bad plist'); };
  const entities = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };
  const decode = s => s.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos);/gi, (m, e) => {
    if (e[0] !== '#') return entities[e.toLowerCase()];
    const n = e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
    return n <= 0x10ffff ? String.fromCodePoint(n) : fail();
  });
  const skip = () => { while (i < tokens.length && !tokens[i].trim()) i++; };
  const next = () => { skip(); return i < tokens.length ? tokens[i++].trim() : fail(); };
  const text = close => {
    let out = '';
    while (i < tokens.length) {
      const t = tokens[i++];
      if (t.trim() === close) return out;
      if (t.startsWith('<![CDATA[')) out += t.slice(9, -3);
      else if (t.startsWith('<')) fail();
      else out += decode(t);
    }
    return fail();
  };
  const value = tag => {
    if (++depth > 20) fail();
    let out;
    if (tag === '<dict>') {
      out = Object.create(null);
      for (let t = next(); t !== '</dict>'; t = next()) {
        if (t !== '<key>') fail();
        const k = text('</key>');
        out[k] = value(next());
      }
    } else if (tag === '<array>') {
      out = [];
      for (let t = next(); t !== '</array>'; t = next()) out.push(value(t));
    } else if (tag === '<dict/>') out = Object.create(null);
    else if (tag === '<array/>') out = [];
    else if (tag === '<true/>') out = true;
    else if (tag === '<false/>') out = false;
    else if (tag === '<string/>') out = '';
    else {
      const m = /^<(string|integer|real|date|data)>$/.exec(tag);
      if (!m) fail();
      out = text('</' + m[1] + '>');
    }
    depth--;
    return out;
  };
  if (!/^<plist[\s>]/.test(next())) fail();
  const root = value(next());
  if (next() !== '</plist>') fail();
  return root;
}

export function readManifest(xml) {
  let root;
  try { root = parsePlist(xml); } catch { return { error: 'manifest_invalid' }; }
  const item = root?.items?.[0];
  if (!item || !Array.isArray(item.assets)) return { error: 'manifest_invalid' };
  const meta = item.metadata || {};
  if (meta.kind !== 'software' || !meta['bundle-identifier'] || !meta['bundle-version'] || !meta.title) return { error: 'manifest_metadata_missing' };
  const pkg = item.assets.find(a => a && a.kind === 'software-package');
  if (!pkg || !publicHttpsURL(pkg.url)) return { error: 'package_url_invalid' };
  return { packageURL: pkg.url, bundleIdentifier: meta['bundle-identifier'], bundleVersion: meta['bundle-version'] };
}

/* لماذا يُعدّ السجل غير صالح للعرض؟ (يعيد null إذا كان مسموحاً) */
export function certificateBlock(cert, now = Date.now()) {
  if (!cert || cert.enabled !== true) return 'disabled';
  if (!['adhoc', 'enterprise'].includes(cert.type)) return 'bad_type';
  const auth = cert.authorization || {};
  if (!String(auth.grantedBy || '').trim() || !String(auth.reference || '').trim()) return 'no_authorization';
  const exp = Date.parse(cert.expiresAt);
  if (!Number.isFinite(exp)) return 'no_expiry';
  if (exp <= now) return 'expired';
  return null;
}

async function safeFetch(url, init, doFetch, signal) {
  let target = url;
  for (let hop = 0; hop <= LIMITS.redirects; hop++) {
    const u = publicHttpsURL(target);
    if (!u) return { error: 'unsafe_url' };
    const res = await doFetch(u.href, { ...init, redirect: 'manual', signal });
    if (res.status < 300 || res.status >= 400) return { res };
    const loc = res.headers.get('location');
    await res.body?.cancel();
    if (!loc) return { error: 'bad_redirect' };
    target = new URL(loc, u).href;
  }
  return { error: 'too_many_redirects' };
}

/* يقرأ حتى max بايت ثم يلغي البقية، فلا يُنزَّل ملف IPA كاملاً */
async function readUpTo(res, max) {
  const reader = res.body?.getReader();
  const chunks = [];
  let size = 0, truncated = false;
  while (reader) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value); size += value.length;
    if (size > max) { truncated = true; await reader.cancel(); break; }
  }
  const bytes = new Uint8Array(size);
  let at = 0;
  for (const c of chunks) { bytes.set(c, at); at += c.length; }
  return { bytes, truncated };
}

async function firstBytes(res, n) {
  const reader = res.body?.getReader();
  const out = [];
  while (reader && out.length < n) {
    const { done, value } = await reader.read();
    if (done) break;
    for (let k = 0; k < value.length && out.length < n; k++) out.push(value[k]);
  }
  await reader?.cancel();
  return out;
}

export async function checkInstall(install, { fetchRemote, fetchManifest = fetchRemote, timeoutMs = LIMITS.timeoutMs }) {
  const signal = AbortSignal.timeout(timeoutMs);
  try {
    const m = await safeFetch(install.manifestURL, {}, fetchManifest, signal);
    if (m.error) return { ok: false, reason: m.error };
    if (m.res.status !== 200) { await m.res.body?.cancel(); return { ok: false, reason: 'manifest_unreachable' }; }
    const body = await readUpTo(m.res, LIMITS.manifestBytes);
    if (body.truncated) return { ok: false, reason: 'manifest_too_large' };
    const info = readManifest(new TextDecoder().decode(body.bytes));
    if (info.error) return { ok: false, reason: info.error };
    if (info.bundleIdentifier !== install.bundleIdentifier) return { ok: false, reason: 'bundle_mismatch' };

    const p = await safeFetch(info.packageURL, { headers: { Range: 'bytes=0-3' } }, fetchRemote, signal);
    if (p.error) return { ok: false, reason: p.error };
    if (![200, 206].includes(p.res.status)) { await p.res.body?.cancel(); return { ok: false, reason: 'package_unreachable' }; }
    const sig = await firstBytes(p.res, 4);
    if (sig.join() !== '80,75,3,4') return { ok: false, reason: 'package_not_ipa' };
    return { ok: true, reason: 'links_ok' };
  } catch {
    return { ok: false, reason: 'network_error' };
  }
}
