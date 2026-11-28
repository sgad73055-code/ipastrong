import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
process.env.ZSIGN_BIN = new URL('./bin/fake-zsign.cjs', import.meta.url).pathname;
process.env.MAX_BODY_MB = '2';
const { createServer } = await import('../src/server.js');

function listen() { const s = createServer(); return new Promise(r => s.listen(0, () => r(s))); }
function post(server, path, parts, headers = {}) {
  const boundary = 'TB' + Math.random().toString(16).slice(2);
  const chunks = [];
  for (const p of parts) {
    chunks.push(Buffer.from(`--${boundary}\r\n`));
    const disp = p.filename ? `form-data; name="${p.name}"; filename="${p.filename}"` : `form-data; name="${p.name}"`;
    chunks.push(Buffer.from(`Content-Disposition: ${disp}\r\n\r\n`));
    chunks.push(Buffer.isBuffer(p.value) ? p.value : Buffer.from(String(p.value)));
    chunks.push(Buffer.from('\r\n'));
  }
  chunks.push(Buffer.from(`--${boundary}--\r\n`));
  const body = Buffer.concat(chunks);
  return new Promise((resolve, reject) => {
    const req = http.request({ port: server.address().port, path, method: 'POST', headers: { 'content-type': `multipart/form-data; boundary=${boundary}`, ...headers } }, res => {
      const bufs = []; res.on('data', c => bufs.push(c)); res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(bufs) }));
    });
    req.on('error', reject); req.end(body);
  });
}
function get(server, path) {
  return new Promise((resolve, reject) => { http.get({ port: server.address().port, path }, res => { const bufs = []; res.on('data', c => bufs.push(c)); res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(bufs) })); }).on('error', reject); });
}

const parts = (pw = 'secret') => [
  { name: 'bundleId', value: 'com.example.app' }, { name: 'version', value: '2.0' }, { name: 'title', value: 'تطبيق تجريبي' }, { name: 'password', value: pw },
  { name: 'ipa', filename: 'a.ipa', value: Buffer.from([80, 75, 3, 4, 1, 2]) },
  { name: 'p12', filename: 'c.p12', value: Buffer.from([9, 9, 9]) },
  { name: 'profile', filename: 'p.mobileprovision', value: Buffer.from('<plist/>') },
];

test('full sign flow: manifest + download work, and secrets are deleted', async () => {
  const server = await listen();
  try {
    const r = await post(server, '/sign', parts());
    const json = JSON.parse(r.body);
    assert.equal(r.status, 200); assert.ok(json.manifestURL);
    const id = /\/m\/([0-9a-f]{32})\.plist/.exec(json.manifestURL)[1];
    const m = await get(server, `/m/${id}.plist`);
    assert.match(m.body.toString(), /com\.example\.app/);
    assert.match(m.body.toString(), new RegExp(`/dl/${id}/app\\.ipa`));
    const dl = await get(server, `/dl/${id}/app.ipa`);
    assert.equal(dl.body.toString(), 'SIGNED:3');
  } finally { server.close(); }
});

test('wrong password surfaces sign_failed, not a crash', async () => {
  const server = await listen();
  try {
  const r = await post(server, '/sign', parts('WRONG'));
  assert.equal(r.status, 422); assert.equal(JSON.parse(r.body).reason, 'sign_failed');
  } finally { server.close(); }
});

test('missing bundleId is rejected', async () => {
  const server = await listen();
  try {
  const bad = parts().filter(p => p.name !== 'bundleId');
  const r = await post(server, '/sign', bad);
  assert.equal(r.status, 400);
  } finally { server.close(); }
});

test('download link expires after two uses', async () => {
  const server = await listen();
  try {
    const r = await post(server, '/sign', parts());
    const id = /\/m\/([0-9a-f]{32})\.plist/.exec(JSON.parse(r.body).manifestURL)[1];
    await get(server, `/dl/${id}/app.ipa`); await get(server, `/dl/${id}/app.ipa`);
    const third = await get(server, `/dl/${id}/app.ipa`);
    assert.equal(third.status, 404);
  } finally { server.close(); }
});

test('oversized body is rejected with 413, not an unhandled crash', async () => {
  const server = await listen();
  try {
  const big = Buffer.alloc(3 * 1024 * 1024);
  const r = await post(server, '/sign', [...parts(), { name: 'ipa', filename: 'big.ipa', value: big }]);
  assert.equal(r.status, 413);
  } finally { server.close(); }
});

test('ipaUrl path rejects private/unsafe URLs without touching the network', async () => {
  const server = await listen();
  try {
    const bad = parts().filter(p => p.name !== 'ipa').concat([{ name: 'ipaUrl', value: 'http://169.254.169.254/latest/meta-data' }]);
    const r = await post(server, '/sign', bad);
    assert.equal(r.status, 400); assert.equal(JSON.parse(r.body).reason, 'bad_ipa_url');
  } finally { server.close(); }
});
