/* يحلّل body كامل (Buffer) لطلب multipart/form-data — لا اعتماديات خارجية.
   يُستدعى بعد تجميع الطلب في الذاكرة بحد أقصى مضبوط في server.js. */
export function parseMultipart(body, contentType) {
  const m = /boundary="?([^";]+)"?/.exec(contentType || '');
  if (!m) { const e = new Error('no_boundary'); e.code = 'bad_request'; throw e; }
  const marker = Buffer.from('--' + m[1]);
  const pieces = [];
  let start = 0, idx;
  while ((idx = body.indexOf(marker, start)) !== -1) {
    pieces.push({ at: idx });
    start = idx + marker.length;
  }
  const fields = {}; const files = {};
  for (let i = 0; i < pieces.length - 1; i++) {
    let s = pieces[i].at + marker.length;
    const e = pieces[i + 1].at;
    if (body[s] === 0x2d && body[s + 1] === 0x2d) continue; // "--" نهاية الرسالة
    // تخطَّ \r\n بعد الفاصل مباشرة
    if (body[s] === 0x0d && body[s + 1] === 0x0a) s += 2;
    const headerEnd = body.indexOf('\r\n\r\n', s);
    if (headerEnd === -1 || headerEnd > e) continue;
    const headers = body.subarray(s, headerEnd).toString('latin1');
    let content = body.subarray(headerEnd + 4, e);
    // أزل \r\n المتبقّية قبل الفاصل التالي مباشرة
    if (content.length >= 2 && content[content.length - 2] === 0x0d && content[content.length - 1] === 0x0a)
      content = content.subarray(0, content.length - 2);
    const disp = /content-disposition:[^\r\n]*/i.exec(headers)?.[0] || '';
    const name = /name="([^"]*)"/.exec(disp)?.[1];
    const filename = /filename="([^"]*)"/.exec(disp)?.[1];
    if (name === undefined) continue;
    if (filename !== undefined) files[name] = { filename, data: content };
    else fields[name] = content.toString('utf8');
  }
  return { fields, files };
}
