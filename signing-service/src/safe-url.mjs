export function publicHttpsURL(value) {
  let u; try { u = new URL(String(value)); } catch { return null; }
  const h = u.hostname.toLowerCase().replace(/\.$/, '');
  if (u.protocol !== 'https:' || u.username || u.password || u.port) return null;
  if (!h.includes('.') || h.startsWith('[') || /^[\d.]+$/.test(h)) return null;
  if (/(^|\.)(localhost|local|internal|lan|home\.arpa)$/.test(h)) return null;
  return u;
}
