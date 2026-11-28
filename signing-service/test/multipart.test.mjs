import test from 'node:test';
import assert from 'node:assert/strict';
import { parseMultipart } from '../src/multipart.mjs';

function build(boundary, parts) {
  const chunks = [];
  for (const p of parts) {
    chunks.push(Buffer.from(`--${boundary}\r\n`));
    const disp = p.filename ? `form-data; name="${p.name}"; filename="${p.filename}"` : `form-data; name="${p.name}"`;
    chunks.push(Buffer.from(`Content-Disposition: ${disp}\r\n\r\n`));
    chunks.push(Buffer.isBuffer(p.value) ? p.value : Buffer.from(p.value));
    chunks.push(Buffer.from('\r\n'));
  }
  chunks.push(Buffer.from(`--${boundary}--\r\n`));
  return Buffer.concat(chunks);
}

test('parses fields and files, preserving exact binary bytes', () => {
  const boundary = 'XBOUNDARY123';
  const binary = Buffer.from([0, 1, 2, 0x0d, 0x0a, 0x2d, 0x2d, 255, 254, 13, 10]); // يحتوي CRLF و -- داخل المحتوى
  const body = build(boundary, [
    { name: 'password', value: 'p@ss\r\n ends' },
    { name: 'bundleId', value: 'com.example.app' },
    { name: 'ipa', filename: 'a.ipa', value: binary },
  ]);
  const { fields, files } = parseMultipart(body, `multipart/form-data; boundary=${boundary}`);
  assert.equal(fields.bundleId, 'com.example.app');
  assert.equal(fields.password, 'p@ss\r\n ends');
  assert.deepEqual(files.ipa.data, binary);
  assert.equal(files.ipa.filename, 'a.ipa');
});

test('throws on missing boundary', () => {
  assert.throws(() => parseMultipart(Buffer.from('x'), 'multipart/form-data'));
});

test('handles a large (multi-MB) file part without corruption', () => {
  const boundary = 'B2';
  const big = Buffer.alloc(3 * 1024 * 1024);
  crypto_fill(big);
  const body = build(boundary, [{ name: 'ipa', filename: 'x.ipa', value: big }]);
  const { files } = parseMultipart(body, `multipart/form-data; boundary=${boundary}`);
  assert.equal(files.ipa.data.length, big.length);
  assert.ok(files.ipa.data.equals(big));
});
function crypto_fill(buf) { for (let i = 0; i < buf.length; i++) buf[i] = (i * 2654435761) & 0xff; }
