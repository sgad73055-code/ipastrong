import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import source_guard as g
from blocked_apps import is_blocked
from pipeline.branding import BRAND, brand_source, clean_developer, clean_name, foreign_mentions
from pipeline.client_check import check
from pipeline.arabic import arabize_source, auto_translate, translate_feature
from pipeline.mirrors import remove_mirrors


def app(name='Game', dev='Unknown', desc='', url='https://example.org/a.ipa', bundle='com.example.game'):
    return {'name': name, 'bundleIdentifier': bundle, 'developerName': dev, 'version': '1.0',
            'versionDate': '2026-01-01', 'downloadURL': url, 'size': 10, 'iconURL': 'https://example.org/i.png',
            'localizedDescription': desc,
            'versions': [{'version': '1.0', 'date': '2026-01-01', 'downloadURL': url, 'size': 10}]}


def source(*apps):
    return {'name': 'ipastrong', 'identifier': 'com.ipastrong.store',
            'sourceURL': 'https://raw.githubusercontent.com/sgad73055-code/ipastrong/main/ipastrong.json',
            'apps': list(apps)}


class BrandingTest(unittest.TestCase):
    def test_other_store_credits_removed(self):
        s = source(
            app('Niyaz', 'ipaomtk.com', 'Niyaz. Listed by IPAOMTK.\nOriginal app page: https://ipaomtk.com/niyaz/\n\nUpstream variant: emulator'),
            app('Car', 'Karbin-Store', 'Car for iOS. Listed by iOSvizor.\nOriginal app page: https://iosvizor.com/games/car/'),
            app('News', 'TTJB IPA Repo', 'Chức năng đã thêm: Premium - IPA đã được kiểm tra và tổng hợp bởi TTJB Team'),
            app('Feather', 'IPA', 'Latest version of Feather. Join my telegram: t.me/riftysIPAlibrary'),
        )
        brand_source(s)
        a = s['apps']
        self.assertEqual(a[0]['localizedDescription'], 'Niyaz.\n\nUpstream variant: emulator')
        self.assertEqual(a[1]['localizedDescription'], 'Car for iOS.')
        self.assertEqual(a[2]['localizedDescription'], 'الميزة المضافة: Premium')
        self.assertEqual(a[3]['localizedDescription'], 'Latest version of Feather.')
        self.assertTrue(all(x['developerName'] == BRAND for x in a))
        self.assertEqual(foreign_mentions(s), [])

    def test_real_developers_and_tweak_names_kept(self):
        self.assertEqual(clean_developer('Spotify'), 'Spotify')
        self.assertEqual(clean_developer('SayGames LTD'), 'SayGames LTD')
        self.assertEqual(clean_developer('dvntms & IPA Vault'), BRAND)
        self.assertEqual(clean_name('Telegram (TGExtra)'), 'Telegram (TGExtra)')
        self.assertEqual(clean_name('YouMod (2.0.0) + Bonus Tweaks (IPAVault) iOS 16+'), 'YouMod (2.0.0) + Bonus Tweaks iOS 16+')

    def test_untouched_when_nothing_foreign_and_idempotent(self):
        text = 'Line one\n\n\n\nLine two  \n'
        s = source(app(dev='Rollic Games', desc=text))
        brand_source(s)
        self.assertEqual(s['apps'][0]['localizedDescription'], text)
        once = copy.deepcopy(source(app(desc='x. Listed by IPAOMTK.')))
        brand_source(once)
        twice = copy.deepcopy(once)
        brand_source(twice)
        self.assertEqual(once, twice)

    def test_own_channel_kept(self):
        s = source(app(desc='Join https://t.me/ipastrong for more.'))
        brand_source(s)
        self.assertEqual(s['apps'][0]['localizedDescription'], 'Join https://t.me/ipastrong for more.')

    def test_promo_only_description_gets_store_line(self):
        s = source(app('Clip', desc='Join https://t.me/+abc for more.'))
        brand_source(s)
        self.assertEqual(s['apps'][0]['localizedDescription'], 'Clip — متوفر على IPA Strong')


class ArabicTest(unittest.TestCase):
    def test_features_translated_and_layout(self):
        a = app('Knight Survivors', desc='Knight Survivors.\n\nUpstream variant: Unlimited Coins, No Ads, Damage Multiplier')
        a['minOSVersion'] = '15.0'
        a['_category'] = 'Games'
        s = source(a)
        arabize_source(s, '/nonexistent')
        self.assertEqual(s['apps'][0]['localizedDescription'],
                         'لعبة Knight Survivors — نسخة معدّلة.\n✨ المميزات: العملات غير محدودة، بدون إعلانات، مضاعفة الضرر\n📱 يتطلب iOS 15.0 أو أحدث')

    def test_idempotent_and_owner_arabic_kept(self):
        s = source(app('Spotify', desc='Injected with Premium'), app('Mine', desc='وصف المالك بالعربي'))
        arabize_source(s, '/nonexistent')
        once = copy.deepcopy(s)
        arabize_source(s, '/nonexistent')
        self.assertEqual(s, once)
        self.assertEqual(s['apps'][1]['localizedDescription'], 'وصف المالك بالعربي')
        self.assertNotIn('_originalDescription', s['apps'][1])

    def test_upstream_text_change_rebuilds(self):
        s = source(app('Spotify', desc='Injected with Premium'))
        arabize_source(s, '/nonexistent')
        s['apps'][0]['localizedDescription'] = 'Injected with No Ads'
        arabize_source(s, '/nonexistent')
        self.assertIn('بدون إعلانات', s['apps'][0]['localizedDescription'])

    def test_translation_overlay_used(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'translations').mkdir()
            (Path(temp) / 'translations' / 'ar.json').write_text(
                json.dumps({'com.example.game|game': 'لعبة حلوة.'}, ensure_ascii=False), encoding='utf-8')
            s = source(app('Game', desc='A very long English description about the game and its levels.'))
            arabize_source(s, temp)
            self.assertEqual(s['apps'][0]['localizedDescription'], 'لعبة حلوة.')

    def test_templates(self):
        self.assertEqual(auto_translate('This is a modded version of Spotify. This works with sidestore!!'),
                         'نسخة معدّلة من Spotify. تشتغل على SideStore.')
        self.assertIsNone(auto_translate('A beautiful app to track your habits every day.'))
        self.assertEqual(translate_feature('RyukGram'), 'RyukGram')


class MirrorTest(unittest.TestCase):
    def test_proxy_copy_removed_but_mods_kept(self):
        gh = 'https://github.com/x/r/releases/download/1/TikTok_47.0_Premium.ipa'
        proxy = 'https://proxy-files.thuthuatjb.com/apps?=x/r/releases/download/1/TikTok_47.0_Premium.ipa'
        other_mod = 'https://github.com/x/r/releases/download/1/TikTok_47.0_ASJTikTok.ipa'
        s = source(app('TikTok', url=proxy, bundle='com.zhiliaoapp.musically'),
                   app('TikTok', url=gh, bundle='com.zhiliaoapp.musically'),
                   app('TikTok', url=other_mod, bundle='com.zhiliaoapp.musically'))
        for a in s['apps']:
            a['version'] = '47.0'
        self.assertEqual(remove_mirrors(s)['removedMirrors'], 1)
        self.assertEqual([a['downloadURL'] for a in s['apps']], [gh, other_mod])


class BlockingTest(unittest.TestCase):
    def test_competitor_store_apps_blocked(self):
        self.assertTrue(is_blocked(app('IPAOMTK', bundle='ipaomtk.installer')))
        self.assertTrue(is_blocked(app('CyPwn Store', bundle='Ed0ardo.CyPwnStore')))
        self.assertTrue(is_blocked(app('X', url='https://cdn.fastsign.dev/x.ipa')))
        self.assertFalse(is_blocked(app('Scarlet', bundle='com.scarlet.app')))


class ClientCheckTest(unittest.TestCase):
    def test_valid_source(self):
        self.assertTrue(check(source(app(dev='IPA Strong')))['ok'])

    def test_breaking_problems_rejected(self):
        bad = app(dev='IPA Strong')
        bad['size'] = '10'
        bad['downloadURL'] = 'http://example.org/a.ipa'
        result = check(source(bad))
        self.assertFalse(result['ok'])
        self.assertEqual(result['errorCount'], 2)


class GuardTest(unittest.TestCase):
    def test_publish_brands_and_blocks_bad_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'backups').mkdir()
            (root / 'source-config.json').write_text('{"brand": "IPA Strong"}')
            old = json.dumps(source(app())).encode()
            g.publish(root, old, source(app(dev='NabzClan', desc='Game. Listed by IPAOMTK.')))
            out = json.loads((root / 'ipastrong.json').read_text())
            self.assertEqual(out['apps'][0]['developerName'], BRAND)
            self.assertEqual(json.loads((root / 'status.json').read_text())['apps'], 1)
            broken = source(app())
            broken['apps'][0]['size'] = 'big'
            (root / 'ipastrong.json').write_bytes(old)
            with self.assertRaises(ValueError):
                g.publish(root, old, broken)
            self.assertEqual((root / 'ipastrong.json').read_bytes(), old)

    def test_automatic_big_drop_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'source-config.json').write_text('{"publishGuard": {"maxDropPercent": 15}}')
            with self.assertRaises(ValueError):
                g.drop_guard(root, 100, {'apps': [app()] * 80})
            g.drop_guard(root, 100, {'apps': [app()] * 90})
            with patch.dict(os.environ, {'IPASTRONG_ALLOW_BIG_DROP': '1'}):
                g.drop_guard(root, 100, {'apps': [app()] * 10})


if __name__ == '__main__':
    unittest.main()
