/* GET /api/cert-status?cert=<id>&install=<id>
   يفحص فقط الروابط المسجّلة في certs/registry.json (ليس وسيطاً مفتوحاً).
   طلب مستقل لكل خيار تثبيت: تعطّل واحد لا يؤثر على غيره، ويبقى ضمن حد الطلبات الفرعية. */
import { certificateBlock, checkInstall } from '../_lib.mjs';

const json = (data, status = 200, maxAge = 0) => new Response(JSON.stringify(data), {
  status,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': maxAge ? `public, max-age=${maxAge}` : 'no-store',
    'x-content-type-options': 'nosniff',
  },
});

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  let registry;
  try {
    const r = await env.ASSETS.fetch(new URL('/certs/registry.json', url));
    if (!r.ok) throw new Error();
    registry = await r.json();
  } catch { return json({ ok: false, reason: 'registry_unavailable' }, 503); }

  const list = Array.isArray(registry?.certificates) ? registry.certificates : [];
  const cert = list.find(c => c?.id === url.searchParams.get('cert'));
  const install = Array.isArray(cert?.installs) ? cert.installs.find(x => x?.id === url.searchParams.get('install')) : null;
  if (!install) return json({ ok: false, reason: 'unknown_entry' }, 404);
  const blocked = certificateBlock(cert);
  if (blocked) return json({ ok: false, reason: blocked });

  const cache = globalThis.caches?.default;
  const key = new Request(`${url.origin}/__cert-check?m=${encodeURIComponent(install.manifestURL)}&b=${encodeURIComponent(install.bundleIdentifier)}`);
  const hit = await cache?.match(key);
  if (hit) return json(await hit.json());

  const result = await checkInstall(install, {
    fetchRemote: (u, init) => fetch(u, init),
    /* manifest المستضاف على نفس الموقع يُقرأ من أصول Pages مباشرة */
    fetchManifest: (u, init) => new URL(u).origin === url.origin ? env.ASSETS.fetch(new Request(u, init)) : fetch(u, init),
  });
  const body = { ...result, checkedAt: new Date().toISOString() };
  if (cache) context.waitUntil(cache.put(key, json(body, 200, result.ok ? 300 : 60)));
  return json(body);
}
