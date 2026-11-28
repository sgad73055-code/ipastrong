/* نقرأ الطلب بالكامل ونُسقط الزائد عن الحد بدل قطع الاتصال فجأة،
   حتى لا يصطدم العميل بـECONNRESET قبل أن يصله ردّ 413 واضح. */
export function readBody(req, maxBytes) {
  return new Promise((resolve, reject) => {
    const chunks = []; let size = 0, overLimit = false;
    req.on('data', c => {
      size += c.length;
      if (size > maxBytes) { overLimit = true; return; } // استمر بتفريغ الدفق دون تخزين
      chunks.push(c);
    });
    req.on('end', () => overLimit ? reject(Object.assign(new Error('too_large'), { code: 'too_large' })) : resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}
