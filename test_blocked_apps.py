import unittest
from blocked_apps import is_blocked, remove_blocked


def app(name, bundle, url='https://example.com/a.ipa'):
    return {'name': name, 'bundleIdentifier': bundle, 'downloadURL': url, 'versions': []}


class BlockedAppsTest(unittest.TestCase):
    def test_blocked(self):
        for name, bundle in [('InstaNyxLRD', 'com.burbn.instagram'), ('BHTikTokLRD', 'com.zhiliaoapp.musically'),
                             ('TikTok SAT', 'x.y'), ('InstagramSat', 'x.y'), ('iota', 'com.toyopagroup.picaboo')]:
            self.assertTrue(is_blocked(app(name, bundle)), name)

    def test_kept(self):
        for name, bundle in [('LikeeLRD', 'video.like'), ('LRD Cracked', 'com.google.ios.youtube'),
                             ('InstaRocketBH', 'com.burbn.instagram'), ('TikTok Satella', 'com.zhiliaoapp.musically'),
                             ('TikTok++', 'com.zhiliaoapp.musically'), ('NGLPro', 'fun.ask')]:
            self.assertFalse(is_blocked(app(name, bundle)), name)

    def test_fastsign_removed_everywhere(self):
        self.assertTrue(is_blocked(app('Regram', 'com.burbn.instagram', 'https://fouadraheb.com/r.ipa') | {'_sourceURL': 'https://fastsign.dev/repo.json'}))
        self.assertTrue(is_blocked(app('X', 'a.b', 'https://fastsign.dev/d/x/app.ipa')))
        self.assertFalse(is_blocked(app('X', 'a.b', 'https://github.com/fastsignfan/x.ipa')))

    def test_fastsign_credit_stripped(self):
        src = {'apps': [app('Rhino', 'a.b') | {'localizedDescription': 'Great app.\n\nFastSign is operated by CertFish.\nThe easy way to sideload: https://cert.fish/'}]}
        self.assertEqual(remove_blocked(src)['strippedCredits'], 1)
        self.assertEqual(src['apps'][0]['localizedDescription'], 'Great app.')


if __name__ == '__main__':
    unittest.main()
