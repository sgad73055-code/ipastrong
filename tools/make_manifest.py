#!/usr/bin/env python3
"""ينشئ manifest.plist لملف IPA موقّع مسبقاً. لا يوقّع الملف ولا يتعامل مع أي شهادة."""
import argparse, plistlib, sys
from pathlib import Path
from urllib.parse import urlparse

def build(ipa_url, bundle_id, version, title):
    u = urlparse(ipa_url)
    if u.scheme != 'https' or not u.hostname:
        raise ValueError('ipa-url must be a public https URL')
    return plistlib.dumps({'items': [{
        'assets': [{'kind': 'software-package', 'url': ipa_url}],
        'metadata': {'bundle-identifier': bundle_id, 'bundle-version': version,
                     'kind': 'software', 'title': title},
    }]})

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ipa-url', 'bundle-id', 'version', 'title', 'out'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    out = Path(a.out)
    if out.exists():
        sys.exit(f'{out} already exists; refusing to overwrite')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build(a.ipa_url, a.bundle_id, a.version, a.title))
    print('Wrote', out)
