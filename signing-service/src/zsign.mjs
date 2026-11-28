import { execFile } from 'node:child_process';

/* استدعاء zsign مرة واحدة فقط. أي تجاوز للمهلة يقتل العملية. */
export function runZsign({ ipa, p12, password, profile, out, bin = process.env.ZSIGN_BIN || 'zsign', timeoutMs = 120000 }) {
  return new Promise((resolve, reject) => {
    const args = ['-k', p12, '-p', password, '-m', profile, '-o', out, '-z', '1', ipa];
    const child = execFile(bin, args, { timeout: timeoutMs, maxBuffer: 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) return reject(Object.assign(new Error('zsign_failed'), { stdout, stderr }));
      resolve({ stdout, stderr });
    });
    child.on('error', reject);
  });
}
