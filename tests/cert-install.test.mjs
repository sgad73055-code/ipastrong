import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { publicHttpsURL, readManifest, certificateBlock, checkInstall } from '../functions/_lib.mjs';
import { onRequestGet } from '../functions/api/cert-status.js';

const IPA = 'https://files.example.com/app.ipa?a=1&b=2';
const MANIFEST = 'https://ota.example.com/m.plist';
const plist = (ipa = IPA, id = 'com.example.app') => execFileSync('python3', ['-c',
  'import sys;sys.path.insert(0,"tools");from make_manifest import build;sys.stdout.buffer.write(build(sys.argv[1],sys.argv[2],"1.0","تطبيق & اختبار"))', ipa, id]).toString();
const zip = () => new Response(new Uint8Array([80, 75, 3, 4, 0, 0]), { status: 206 });
const install = { id: 'a', manifestURL: MANIFEST, bundleIdentifier: 'com.example.app' };
const net = routes => async url => { const r = routes[url]; if (!r) throw new Error('offline'); return r(); };
const good = { [MANIFEST]: () => new Response(plist()), [IPA]: zip };
const reason = async (routes, i = install) => (await checkInstall(i, { fetchRemote: net(routes) })).reason;

test('rejects unsafe URLs', () => {
  for (const u of ['http://a.com/x', 'https://127.0.0.1/x', 'https://2130706433/', 'https://[::1]/', 'https://localhost/', 'https://x.local./', 'https://u:p@a.com/', 'https://a.com:8443/', 'itms-services://x', ''])
    assert.equal(publicHttpsURL(u), null, u);
});
test('reads a generated manifest, including entities', () => assert.equal(readManifest(plist()).packageURL, IPA));
test('rejects HTML and truncated XML', () => {
  assert.ok(readManifest('<!DOCTYPE html><html></html>').error);
  assert.ok(readManifest(plist().slice(0, 200)).error);
});
test('working links pass', async () => assert.equal(await reason(good), 'links_ok'));
test('HTTP 200 HTML instead of IPA fails', async () => assert.equal(await reason({ ...good, [IPA]: () => new Response('<html>gone</html>') }), 'package_not_ipa'));
test('failures are classified', async () => {
  assert.equal(await reason({ ...good, [MANIFEST]: () => new Response('', { status: 404 }) }), 'manifest_unreachable');
  assert.equal(await reason({ ...good, [IPA]: () => new Response('', { status: 403 }) }), 'package_unreachable');
  assert.equal(await reason({}), 'network_error');
  assert.equal(await reason(good, { ...install, bundleIdentifier: 'com.other' }), 'bundle_mismatch');
  assert.equal(await reason({ [MANIFEST]: () => new Response('x'.repeat(300000)) }), 'manifest_too_large');
});
test('redirect to a private address is blocked', async () => assert.equal(await reason({ ...good, [IPA]: () => new Response(null, { status: 302, headers: { location: 'https://127.0.0.1/a' } }) }), 'unsafe_url'));
test('safe redirect is followed', async () => assert.equal(await reason({ ...good, [IPA]: () => new Response(null, { status: 302, headers: { location: 'https://cdn.example.com/a' } }), 'https://cdn.example.com/a': zip }), 'links_ok'));
test('certificate rules', () => {
  const c = { enabled: true, type: 'adhoc', expiresAt: '2999-01-01', authorization: { grantedBy: 'x', reference: 'y' } };
  assert.equal(certificateBlock(c), null);
  assert.equal(certificateBlock({ ...c, expiresAt: '2000-01-01' }), 'expired');
  assert.equal(certificateBlock({ ...c, authorization: {} }), 'no_authorization');
  assert.equal(certificateBlock({ ...c, enabled: false }), 'disabled');
});
test('API checks only registered entries and ignores caller URLs', async () => {
  const registry = { certificates: [null, { id: 'c', enabled: true, type: 'adhoc', expiresAt: '2000-01-01', authorization: { grantedBy: 'x', reference: 'y' }, installs: [install] }] };
  const call = async q => { const r = await onRequestGet({ request: new Request('https://site.example.com/api/cert-status?' + q), env: { ASSETS: { fetch: async () => Response.json(registry) } }, waitUntil() {} }); return [r.status, (await r.json()).reason]; };
  assert.deepEqual(await call('url=https://evil.example.com'), [404, 'unknown_entry']);
  assert.deepEqual(await call('cert=c&install=a'), [200, 'expired']);
});
test('shipped registry is valid JSON with no secret fields', () => {
  const raw = readFileSync('certs/registry.json', 'utf8');
  JSON.parse(raw);
  assert.doesNotMatch(raw, /password|private.?key|\.p12|mobileprovision/i);
});
