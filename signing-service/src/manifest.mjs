export function buildManifest({ ipaURL, bundleId, version, title }) {
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>items</key><array><dict>
<key>assets</key><array><dict><key>kind</key><string>software-package</string><key>url</key><string>${esc(ipaURL)}</string></dict></array>
<key>metadata</key><dict><key>bundle-identifier</key><string>${esc(bundleId)}</string><key>bundle-version</key><string>${esc(version)}</string><key>kind</key><string>software</string><key>title</key><string>${esc(title)}</string></dict>
</dict></array></dict></plist>`;
}
