import unittest
from blocked_apps import is_blocked


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


if __name__ == '__main__':
    unittest.main()
