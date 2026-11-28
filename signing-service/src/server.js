import http from 'node:http';
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { parseMultipart } from './multipart.mjs';
import { readBody } from './http-body.mjs';
import { runZsign } from './zsign.mjs';
import { buildManifest } from './manifest.mjs';
import { publicHttpsURL } from './safe-url.mjs';

const PORT = process.env.PORT || 8080;
const ORIGIN = process.env.ALLOWED_ORIGIN || '*'; // ثبّت دومين موقعك في الإنتاج بدل *
const MAX_BODY = (Number(process.env.MAX_BODY_MB) || 700) * 1024 * 1024;
const TTL_MS = 10 * 60 * 1000;
const pending = new Map(); // id -> { dir, ipaPath, bundleId, version, title, expires, used }

function sweep() { const now = Date.now(); for (const [id, e] of pending) if (now > e.expires) { pending.delete(id); rm(e.dir, { recursive: true, force: true }).catch(() => {}); } }
const sweepTimer = setInterval(sweep, 60000); sweepTimer.unref?.();

function json(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'access-control-allow-origin': ORIGIN, 'cache-control': 'no-store' });
  res.end(JSON.stringify(body));
}
function baseURL(req) { return (process.env.PUBLIC_BASE_URL || `https://${req.headers.host}`).replace(/\/$/, ''); }

export async function handleSign(req, res) {
  let dir;
  try {
    const body = await readBody(req, MAX_BODY);
    const { fields, files } = parseMultipart(body, req.headers['content-type']);
    if (!files.p12 || !files.profile) return json(res, 400, { ok: false, reason: 'missing_files' });
    if (!files.ipa && !fields.ipaUrl) return json(res, 400, { ok: false, reason: 'missing_files' });
    const bundleId = String(fields.bundleId || '').trim();
    if (!bundleId) return json(res, 400, { ok: false, reason: 'missing_bundle_id' });
    const version = String(fields.version || '1.0').trim();
    const title = String(fields.title || 'App').trim();
    const password = fields.password || '';

    dir = await mkdtemp(path.join(tmpdir(), 'sign-'));
    const ipaPath = path.join(dir, 'in.ipa');
    const p12Path = path.join(dir, 'c.p12');
    const profilePath = path.join(dir, 'p.mobileprovision');
    const outPath = path.join(dir, 'out.ipa');

    let ipaBytes = files.ipa?.data;
    if (!ipaBytes) {
      const u = publicHttpsURL(fields.ipaUrl);
      if (!u) return json(res, 400, { ok: false, reason: 'bad_ipa_url' });
      const r = await fetch(u.href, { redirect: 'follow' }).catch(() => null);
      if (!r || !r.ok) return json(res, 502, { ok: false, reason: 'ipa_fetch_failed' });
      const buf = Buffer.from(await r.arrayBuffer());
      if (buf.length > MAX_BODY) return json(res, 413, { ok: false, reason: 'file_too_large' });
      if (buf[0] !== 0x50 || buf[1] !== 0x4b) return json(res, 400, { ok: false, reason: 'not_an_ipa' });
      ipaBytes = buf;
    }
    await Promise.all([writeFile(ipaPath, ipaBytes), writeFile(p12Path, files.p12.data), writeFile(profilePath, files.profile.data)]);

    try {
      await runZsign({ ipa: ipaPath, p12: p12Path, password, profile: profilePath, out: outPath });
    } catch {
      return json(res, 422, { ok: false, reason: 'sign_failed' });
    } finally {
      /* السر والملف الأصلي يُحذفان فوراً بغض النظر عن النتيجة */
      await rm(p12Path, { force: true }).catch(() => {});
      await rm(ipaPath, { force: true }).catch(() => {});
      await rm(profilePath, { force: true }).catch(() => {});
    }
    const signed = await readFile(outPath).catch(() => null);
    if (!signed) return json(res, 500, { ok: false, reason: 'no_output' });

    const id = crypto.randomBytes(16).toString('hex');
    pending.set(id, { dir, ipaPath: outPath, bundleId, version, title, expires: Date.now() + TTL_MS, used: 0 });
    dir = null; // لا تُحذف في finally بعد تسجيلها للتنزيل
    return json(res, 200, { ok: true, manifestURL: `${baseURL(req)}/m/${id}.plist`, expiresInSec: TTL_MS / 1000 });
  } catch (err) {
    if (err?.code === 'too_large') return json(res, 413, { ok: false, reason: 'file_too_large' });
    if (err?.code === 'bad_request') return json(res, 400, { ok: false, reason: 'bad_request' });
    console.error('sign_request_failed');
    return json(res, 500, { ok: false, reason: 'server_error' });
  } finally {
    if (dir) await rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}

export function serveManifest(req, res, id) {
  const e = pending.get(id);
  if (!e || Date.now() > e.expires) return json(res, 404, { ok: false, reason: 'expired' });
  const xml = buildManifest({ ipaURL: `${baseURL(req)}/dl/${id}/app.ipa`, bundleId: e.bundleId, version: e.version, title: e.title });
  res.writeHead(200, { 'content-type': 'text/xml; charset=utf-8', 'access-control-allow-origin': ORIGIN, 'cache-control': 'no-store' });
  res.end(xml);
}

export async function serveDownload(req, res, id) {
  const e = pending.get(id);
  if (!e || Date.now() > e.expires) { res.writeHead(404); return res.end(); }
  const data = await readFile(e.ipaPath).catch(() => null);
  if (!data) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': 'application/octet-stream', 'content-length': data.length });
  res.end(data);
  e.used++;
  if (e.used >= 2) { pending.delete(id); rm(e.dir, { recursive: true, force: true }).catch(() => {}); }
}

export function createServer() {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    if (req.method === 'OPTIONS') { res.writeHead(204, { 'access-control-allow-origin': ORIGIN, 'access-control-allow-headers': 'content-type', 'access-control-allow-methods': 'POST, GET, OPTIONS' }); return res.end(); }
    if (req.method === 'POST' && url.pathname === '/sign') return handleSign(req, res);
    const m = /^\/m\/([0-9a-f]{32})\.plist$/.exec(url.pathname); if (m) return serveManifest(req, res, m[1]);
    const d = /^\/dl\/([0-9a-f]{32})\/app\.ipa$/.exec(url.pathname); if (d) return serveDownload(req, res, d[1]);
    if (url.pathname === '/healthz') { res.writeHead(200); return res.end('ok'); }
    res.writeHead(404); res.end();
  });
}

if (import.meta.url === `file://${process.argv[1]}`) createServer().listen(PORT, () => console.log('signing service on', PORT));
