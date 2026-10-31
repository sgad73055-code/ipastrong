"""Add an IPA URL to IPA Strong. Standard library; no IPA code is executed."""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

MAX_BYTES = 5 * 1024**3

def check_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise ValueError('Use a direct public HTTPS IPA download URL without credentials')
    # Do not expose temporary signed URLs as durable public catalog entries.
    query = urllib.parse.parse_qs(p.query)
    if any(k.lower() in ('token','access_token','x-amz-signature','sig','signature','jwt') for k in query):
        raise ValueError('Use the permanent share/download URL, not a temporary signed URL')

def download(url, destination):
    check_url(url)
    deadline = time.monotonic() + 1200
    total = 0
    digest = hashlib.sha256()
    req = urllib.request.Request(url, headers={'User-Agent':'IPA-Strong-Importer/1.0'})
    with urllib.request.urlopen(req, timeout=40) as response, open(destination,'wb') as output:
        length = response.headers.get('Content-Length','')
        if length.isdigit() and int(length) > MAX_BYTES: raise ValueError('IPA exceeds 5 GiB import limit')
        while True:
            if time.monotonic() > deadline: raise TimeoutError('Download exceeded 20 minutes')
            chunk = response.read(1024*1024)
            if not chunk: break
            if total == 0 and chunk[:4] not in (b'PK\x03\x04',b'PK\x05\x06'):
                # Check the original and redirect destination hosts without logging
                # URLs, which may contain private query parameters.
                hosts = [urllib.parse.urlsplit(u).hostname or ''
                         for u in (url, response.geturl())]
                if any(h == 'modsfire.com' or h.endswith('.modsfire.com') for h in hosts):
                    raise ValueError(
                        'ModsFire returned a download webpage, not an IPA file. '
                        'Interactive ModsFire pages are not supported. Download the IPA '
                        'in your browser, upload it to GitHub Releases, then use the '
                        'permanent HTTPS release asset download URL. Do not use a '
                        'temporary signed link. Catalog unchanged.')
                raise ValueError(
                    'URL returned HTML or another non-IPA response. Use a permanent '
                    'public HTTPS link that downloads the IPA without a download page, '
                    'login or CAPTCHA (for example a GitHub Releases asset). '
                    'Catalog unchanged.')
            total += len(chunk)
            if total > MAX_BYTES: raise ValueError('IPA exceeds 5 GiB import limit')
            digest.update(chunk)
            output.write(chunk)
    if not total: raise ValueError('Empty download')
    return total, digest.hexdigest()

def inspect(path):
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.startswith('Payload/') and n.endswith('.app/Info.plist') and n.count('/') == 2]
        if len(names) != 1: raise ValueError('IPA must contain exactly one main application')
        item = archive.getinfo(names[0])
        if item.file_size > 1024*1024: raise ValueError('Info.plist is unexpectedly large')
        info = plistlib.loads(archive.read(item))
        bundle = info.get('CFBundleIdentifier')
        version = info.get('CFBundleShortVersionString') or info.get('CFBundleVersion')
        if not isinstance(bundle,str) or not bundle.strip() or not isinstance(version,(str,int,float)):
            raise ValueError('IPA missing bundle identifier or version')
        return {'bundle':bundle.strip(),'version':str(version),'build':str(info.get('CFBundleVersion','')),
                'name':str(info.get('CFBundleDisplayName') or info.get('CFBundleName') or bundle),
                'minOS':str(info.get('MinimumOSVersion',''))}

def extract_icon(path, root, metadata, sha256):
    """Extract a declared PNG icon when available; never modify the IPA."""
    with zipfile.ZipFile(path) as archive:
        plist_names = [n for n in archive.namelist() if n.startswith('Payload/') and n.endswith('.app/Info.plist') and n.count('/') == 2]
        if len(plist_names) != 1: return ''
        base = plist_names[0].rsplit('/', 1)[0] + '/'
        info = plistlib.loads(archive.read(plist_names[0]))
        names = []
        for icons in (info.get('CFBundleIcons', {}), info.get('CFBundleIcons~ipad', {})):
            if not isinstance(icons, dict): continue
            primary = icons.get('CFBundlePrimaryIcon', {})
            if isinstance(primary, dict):
                names.extend(n for n in primary.get('CFBundleIconFiles', []) if isinstance(n, str))
                n = primary.get('CFBundleIconName')
                if isinstance(n, str): names.append(n)
        candidates = []
        for item in archive.infolist():
            n = item.filename
            if not n.startswith(base) or '/' in n[len(base):] or not n.lower().endswith('.png'):
                continue
            if item.file_size > 4 * 1024 * 1024: continue
            stem = n[len(base):].lower()
            declared = any(stem.startswith(x.lower().removesuffix('.png')) for x in names)
            if declared or 'appicon' in stem or 'icon' in stem:
                candidates.append((0 if declared else 1, -item.file_size, n))
        for _, _, name in sorted(candidates):
            data = archive.read(name)
            if not data.startswith(bytes.fromhex('89504e470d0a1a0a')): continue
            # Apple optimized PNGs (CgBI) are not standard browser PNGs.
            if b'CgBI' in data[:48]: continue
            destination = root / 'assets' / 'app-icons' / (sha256[:24] + '.png')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            return 'https://raw.githubusercontent.com/sgad73055-code/ipastrong/main/assets/app-icons/' + destination.name
    return ''

def add(source, metadata, url, size, sha256, name='', description='', icon='', date=None):
    check_url(url)
    if icon: check_url(icon)
    result = copy.deepcopy(source)
    date = date or datetime.now(timezone.utc).isoformat()
    # An identical URL is an update; a different URL remains a separate tweak/variant.
    existing = next((a for a in result['apps'] if a.get('downloadURL') == url and a.get('_sourceURL') == 'local'), None)
    image = icon or (existing or {}).get('iconURL')
    if not image:
        image = next((a.get('iconURL') for a in result['apps'] if str(a.get('bundleIdentifier','')).lower() == metadata['bundle'].lower() and a.get('iconURL')),result.get('iconURL',''))
    display = name.strip() or (existing or {}).get('name') or metadata['name']
    version = {'version':metadata['version'],'date':date,'downloadURL':url,'size':size,'sha256':sha256}
    if metadata['build']: version['buildVersion']=metadata['build']
    if metadata['minOS']: version['minOSVersion']=metadata['minOS']
    app = {'name':display,'bundleIdentifier':metadata['bundle'],'developerName':'IPA Strong','version':metadata['version'],
           'versionDate':date,'downloadURL':url,'size':size,'iconURL':image,'localizedDescription':description.strip() or (existing or {}).get('localizedDescription',''),
           'versions':[version],'sha256':sha256,'_sourceURL':'local','_addedFromLink':True}
    if metadata['minOS']:app['minOSVersion']=metadata['minOS']
    if existing:
        history = [v for v in existing.get('versions',[]) if (str(v.get('version')),v.get('downloadURL')) != (metadata['version'],url)]
        app['versions'].extend(history)
        result['apps'][result['apps'].index(existing)] = app
    else:result['apps'].insert(0,app)
    result['lastUpdated']=date
    return result

def fixture():
    return {'name':'IPA Strong','iconURL':'https://example.org/icon.png','apps':[]}

META = {'bundle':'com.example.test','version':'2.0','build':'20','name':'Test','minOS':'14.0'}

class ImportTests(unittest.TestCase):
    def test_direct_download_inspect_and_add(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('Payload/Test.app/Info.plist', plistlib.dumps({
                'CFBundleIdentifier': META['bundle'],
                'CFBundleShortVersionString': META['version']}))
        payload = data.getvalue()
        # No .ipa suffix required; the file contents decide acceptance.
        for url in ('https://example.org/download', 'https://modsfire.com/d/direct'):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as directory:
                response = io.BytesIO(payload)
                response.headers = {'Content-Length': str(len(payload))}
                response.geturl = lambda: url
                original = add(fixture(), META, 'https://example.org/old.ipa', 12, 'old')
                snapshot = copy.deepcopy(original)
                path = Path(directory) / 'app.ipa'
                with patch('urllib.request.urlopen', return_value=response):
                    size, digest = download(url, path)
                result = add(original, inspect(path), url, size, digest)
                self.assertEqual(size, len(payload))
                self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
                self.assertEqual(len(result['apps']), 2)
                self.assertEqual(result['apps'][1:], original['apps'])
                self.assertEqual(original, snapshot)

    def test_webpage_rejected_before_publish(self):
        import source_guard
        for url, final_url, message in (
            ('https://modsfire.com/d/t4kxC698eX3ZH22',
             'https://modsfire.com/d/t4kxC698eX3ZH22', 'ModsFire returned'),
            ('https://example.org/redirect', 'https://www.modsfire.com/d/test', 'ModsFire returned'),
            ('https://example.org/app.ipa', 'https://example.org/app.ipa', 'URL returned HTML'),
            ('https://notmodsfire.com/app.ipa', 'https://notmodsfire.com/app.ipa', 'URL returned HTML'),
        ):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = root / 'ipastrong.json'
                original = json.dumps(fixture()).encode()
                catalog.write_bytes(original)
                response = io.BytesIO(b'<!doctype html><a>Download</a>')
                response.headers = {}
                response.geturl = lambda: final_url
                with patch.dict(os.environ, {'APP_URL': url}), \
                     patch('sys.argv', ['importer']), \
                     patch.dict(main.__globals__, {'__file__': str(root / 'importer.py')}), \
                     patch('source_guard.validate'), \
                     patch('source_guard.publish') as publish, \
                     patch('urllib.request.urlopen', return_value=response):
                    with self.assertRaisesRegex(ValueError, message):
                        main()
                    publish.assert_not_called()
                self.assertEqual(catalog.read_bytes(), original)
                self.assertEqual(list(root.iterdir()), [catalog])

    def test_new_app(self):
        s=add(fixture(),META,'https://example.org/a.ipa',123,'hash');self.assertEqual(len(s['apps']),1);self.assertEqual(s['apps'][0]['version'],'2.0')
    def test_duplicate_idempotent(self):
        s=add(fixture(),META,'https://example.org/a.ipa',123,'hash');s=add(s,META,'https://example.org/a.ipa',123,'hash');self.assertEqual(len(s['apps']),1)
    def test_variants_preserved(self):
        s=add(fixture(),META,'https://example.org/a.ipa',123,'hash');s=add(s,META,'https://example.org/b.ipa',123,'hash');self.assertEqual(len(s['apps']),2)
    def test_owner_name_and_description_preserved(self):
        s=add(fixture(),META,'https://example.org/a.ipa',123,'hash','My tweak','My description');s=add(s,META,'https://example.org/a.ipa',123,'hash');self.assertEqual(s['apps'][0]['name'],'My tweak');self.assertEqual(s['apps'][0]['localizedDescription'],'My description')
    def test_credentials_rejected(self):
        with self.assertRaises(ValueError):check_url('https://user:secret@example.org/a.ipa')
    def test_temporary_url_rejected(self):
        with self.assertRaises(ValueError):check_url('https://example.org/a.ipa?token=secret')
    def test_binary_plist(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.ipa'
            with zipfile.ZipFile(p,'w') as z:z.writestr('Payload/Test.app/Info.plist',plistlib.dumps({'CFBundleIdentifier':'com.test','CFBundleShortVersionString':'1.0'},fmt=plistlib.FMT_BINARY))
            self.assertEqual(inspect(p)['bundle'],'com.test')
    def test_download_size_is_recorded(self):
        app=add(fixture(),META,'https://example.org/a.ipa',73400320,'hash')['apps'][0]
        self.assertEqual(app['size'],73400320)
        self.assertEqual(app['versions'][0]['size'],73400320)
    def test_missing_main_app(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.ipa'
            with zipfile.ZipFile(p,'w') as z:z.writestr('index.html','hello')
            with self.assertRaises(ValueError):inspect(p)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(ImportTests)
        if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():raise SystemExit(1)
        return
    root=Path(__file__).resolve().parent
    import source_guard
    old=(root/'ipastrong.json').read_bytes()
    source=json.loads(old)
    source_guard.validate(source)
    url=os.environ.get('APP_URL','').strip()
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'app.ipa'
        size,sha=download(url,path)
        metadata=inspect(path)
        icon=os.environ.get('APP_ICON','').strip()
        if not icon:
            icon=extract_icon(path,root,metadata,sha)
        result=add(source,metadata,url,size,sha,os.environ.get('APP_NAME',''),os.environ.get('APP_DESCRIPTION',''),icon)
        source_guard.publish(root,old,result)
    print(json.dumps({'added':metadata['name'],'version':metadata['version'],'bytes':size,'apps':len(result['apps'])},ensure_ascii=False))
    # Never embed user-supplied text in workflow command syntax or step-summary Markdown.

if __name__=='__main__':main()
