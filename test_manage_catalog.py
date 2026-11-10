import copy
import base64
import io
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import catalog_owner as owner
import manage_catalog as manager
import source_guard


def app(name='Test', url='https://example.org/a.ipa'):
    return {'name': name, 'bundleIdentifier': 'com.test', 'version': '1', 'versionDate': '2026-01-01T00:00:00+00:00',
            'downloadURL': url, 'size': 123, 'iconURL': 'https://example.org/old.png', 'localizedDescription': 'Old',
            '_sourceURL': 'https://example.org/feed.json', 'extra': {'preserve': True},
            'versions': [{'version': '1', 'date': '2026-01-01T00:00:00+00:00', 'downloadURL': url, 'size': 123}]}


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = {'name': 'IPA Strong', 'apps': [app(), app('Other', 'https://example.org/b.ipa')]}
        self.original = json.dumps(self.source).encode()
        (self.root / 'ipastrong.json').write_bytes(self.original)

    def read(self):
        return json.loads((self.root / 'ipastrong.json').read_bytes())

    def test_list_and_ambiguous_target_write_nothing(self):
        self.assertEqual(manager.execute(self.root, 'list', 'test')['matched'], 2)
        self.assertFalse((self.root / 'catalog-owner.json').exists())
        with self.assertRaises(ValueError): manager.execute(self.root, 'delete', 'missing')
        self.assertEqual((self.root / 'ipastrong.json').read_bytes(), self.original)
        duplicate = copy.deepcopy(self.source)
        duplicate['apps'][1]['name'] = 'Test'
        with self.assertRaisesRegex(ValueError, 'matched 2'): manager.select(duplicate, 'Test')

    def test_edit_survives_upstream_refresh_and_publish(self):
        result = manager.execute(self.root, 'edit', owner.app_id(self.source['apps'][0]),
                                 {'name': 'My app', 'localizedDescription': 'وصف جديد', 'iconURL': 'https://example.org/new.png'})
        self.assertEqual((result['before'], result['after']), (2, 2))
        self.assertEqual(self.read()['apps'][0]['extra'], {'preserve': True})
        self.assertEqual(self.read()['apps'][1], self.source['apps'][1])
        upstream = copy.deepcopy(self.source)
        upstream['apps'][0]['version'] = '2'
        upstream['apps'][0]['versions'][0]['version'] = '2'
        source_guard.publish(self.root, self.original, upstream)
        refreshed = self.read()['apps'][0]
        self.assertEqual(refreshed['name'], 'My app')
        self.assertEqual(refreshed['version'], '2')
        self.assertEqual(refreshed['localizedDescription'], 'وصف جديد')
        self.assertEqual(refreshed['iconURL'], 'https://example.org/new.png')

    def test_delete_survives_refresh_and_restore(self):
        manager.execute(self.root, 'delete', 'Test')
        self.assertEqual(len(self.read()['apps']), 1)
        source_guard.publish(self.root, self.original, copy.deepcopy(self.source))
        self.assertEqual(self.read()['apps'], [self.source['apps'][1]])
        manager.execute(self.root, 'restore', self.source['apps'][0]['downloadURL'])
        self.assertEqual(len(self.read()['apps']), 2)
        self.assertEqual(owner.load(self.root / 'catalog-owner.json')['rules'], [])

    def test_dry_run_does_not_write(self):
        result = manager.execute(self.root, 'delete', 'Test', dry_run=True)
        self.assertFalse(result['written'])
        self.assertEqual((self.root / 'ipastrong.json').read_bytes(), self.original)
        self.assertFalse((self.root / 'catalog-owner.json').exists())

    def test_clear_and_restore_presentation(self):
        manager.execute(self.root, 'edit', 'Test', {'name': 'Renamed'}, clear_description=True, clear_icon=True)
        self.assertEqual(self.read()['apps'][0]['localizedDescription'], '')
        self.assertEqual(self.read()['apps'][0]['iconURL'], '')
        manager.execute(self.root, 'restore', self.source['apps'][0]['downloadURL'])
        self.assertEqual(self.read()['apps'][0], self.source['apps'][0])

    def response(self, body):
        response = io.BytesIO(body)
        response.headers = {'Content-Length': str(len(body))}
        response.geturl = lambda: 'https://example.org/direct'
        return response

    def ipa(self, bundle='com.new'):
        body = io.BytesIO()
        with zipfile.ZipFile(body, 'w') as archive:
            archive.writestr('Payload/New.app/Info.plist', plistlib.dumps({
                'CFBundleIdentifier': bundle, 'CFBundleShortVersionString': '2', 'CFBundleDisplayName': 'New'}))
        return body.getvalue()

    def test_add_does_not_use_global_source_icon_as_app_icon(self):
        with patch('urllib.request.urlopen', return_value=self.response(self.ipa())):
            manager.execute(self.root, 'add', updates={'downloadURL': 'https://example.org/new.ipa'})
        added = self.read()['apps'][0]
        self.assertEqual(added['iconURL'], '')
        self.assertEqual(self.read()['apps'][1:], self.source['apps'])

    def test_add_direct_ipa_and_idempotent_owner_overlay(self):
        with patch('urllib.request.urlopen', return_value=self.response(self.ipa())):
            manager.execute(self.root, 'add', updates={'downloadURL': 'https://example.org/new.ipa', 'name': 'Added'})
        self.assertEqual(len(self.read()['apps']), 3)
        upstream = copy.deepcopy(self.source)
        owner.apply_file(upstream, self.root)
        owner.apply_file(upstream, self.root)
        self.assertEqual(len(upstream['apps']), 3)
        self.assertEqual(upstream['apps'][1:], self.source['apps'])
        source_guard.validate(upstream)
        with self.assertRaises(ValueError):
            manager.execute(self.root, 'add', updates={'downloadURL': 'https://example.org/new.ipa'})

    def test_replace_ipa_verifies_identity_and_metadata(self):
        with patch('urllib.request.urlopen', return_value=self.response(self.ipa('com.test'))):
            manager.execute(self.root, 'edit', 'Test', {'downloadURL': 'https://example.org/new.ipa'})
        self.assertEqual(self.read()['apps'][0]['version'], '2')
        self.assertEqual(self.read()['apps'][0]['versions'][0]['downloadURL'], 'https://example.org/new.ipa')
        upstream = copy.deepcopy(self.source)
        upstream['apps'].append(copy.deepcopy(self.read()['apps'][0]))
        owner.apply_file(upstream, self.root)
        owner.apply_file(upstream, self.root)
        self.assertEqual(len(upstream['apps']), 2)
        source_guard.validate(upstream)

    def test_html_and_wrong_bundle_leave_files_untouched(self):
        for body in (b'<html>Download</html>', self.ipa('com.wrong')):
            with self.subTest(body=body[:20]), patch('urllib.request.urlopen', return_value=self.response(body)):
                with self.assertRaises(ValueError):
                    manager.execute(self.root, 'edit', 'Test', {'downloadURL': 'https://example.org/new.ipa'})
            self.assertEqual((self.root / 'ipastrong.json').read_bytes(), self.original)
            self.assertFalse((self.root / 'catalog-owner.json').exists())

    def test_policy_blocks_add_before_any_write(self):
        (self.root / 'catalog-policy.json').write_text(json.dumps({'schema': 1, 'blockedURLs': ['https://example.org/new.ipa']}))
        with patch('urllib.request.urlopen', return_value=self.response(self.ipa())):
            with self.assertRaisesRegex(ValueError, 'policy blocks'):
                manager.execute(self.root, 'add', updates={'downloadURL': 'https://example.org/new.ipa'})
        self.assertEqual((self.root / 'ipastrong.json').read_bytes(), self.original)
        self.assertFalse((self.root / 'catalog-owner.json').exists())

    def test_same_url_different_editions_remain_independent(self):
        self.source['apps'][1]['bundleIdentifier'] = 'com.other'
        self.source['apps'][1]['downloadURL'] = self.source['apps'][0]['downloadURL']
        self.source['apps'][1]['versions'][0]['downloadURL'] = self.source['apps'][0]['downloadURL']
        (self.root / 'ipastrong.json').write_text(json.dumps(self.source))
        target = owner.app_id(self.source['apps'][0])
        self.assertNotEqual(target, owner.app_id(self.source['apps'][1]))
        with self.assertRaises(ValueError): manager.select(self.source, self.source['apps'][0]['downloadURL'])
        manager.execute(self.root, 'edit', target, {'name': 'My edition'})
        self.assertEqual(self.read()['apps'][1], self.source['apps'][1])
        manager.execute(self.root, 'delete', owner.app_id(self.read()['apps'][0]))
        self.assertEqual(self.read()['apps'], [self.source['apps'][1]])
        source_guard.publish(self.root, self.original, copy.deepcopy(self.source))
        self.assertEqual(self.read()['apps'], [self.source['apps'][1]])

    def test_image_upload_has_permanent_url_and_preserves_other_apps(self):
        # A real minimal 1x1 PNG, no uploaded file is executed.
        icon = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4e8AAAAASUVORK5CYII='
        manager.execute(self.root, 'edit', 'Test', {'iconURL': icon})
        saved = self.read()['apps'][0]['iconURL']
        self.assertTrue(saved.startswith('https://raw.githubusercontent.com/sgad73055-code/ipastrong/main/assets/app-icons/owner-'))
        assets = list((self.root / 'assets' / 'app-icons').iterdir())
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].read_bytes(), base64.b64decode(icon.split(',')[1]))
        self.assertEqual(self.read()['apps'][1], self.source['apps'][1])
        source_guard.publish(self.root, self.original, copy.deepcopy(self.source))
        self.assertEqual(self.read()['apps'][0]['iconURL'], saved)

    def test_image_dry_run_and_bad_image_write_nothing(self):
        icon = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4e8AAAAASUVORK5CYII='
        manager.execute(self.root, 'edit', 'Test', {'iconURL': icon}, dry_run=True)
        for invalid in ('data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=', 'data:image/png;base64,bm90IGEgcG5n', 'data:image/png;base64,' + 'A' * 45001):
            with self.assertRaises(ValueError): manager.execute(self.root, 'edit', 'Test', {'iconURL': invalid})
        self.assertEqual((self.root / 'ipastrong.json').read_bytes(), self.original)
        self.assertFalse((self.root / 'catalog-owner.json').exists())
        self.assertFalse((self.root / 'assets').exists())

    def test_deleting_last_app_is_blocked(self):
        manager.execute(self.root, 'delete', 'Other')
        before = (self.root / 'ipastrong.json').read_bytes()
        rules = (self.root / 'catalog-owner.json').read_bytes()
        with self.assertRaises(ValueError): manager.execute(self.root, 'delete', 'Test')
        self.assertEqual((self.root / 'ipastrong.json').read_bytes(), before)
        self.assertEqual((self.root / 'catalog-owner.json').read_bytes(), rules)

if __name__ == '__main__': unittest.main()
