import json
from pathlib import Path
import tempfile
import unittest
from catalog_limit import apply_limit


class CatalogLimitTests(unittest.TestCase):
    def test_preserves_owner_and_signing_before_newer_apps(self):
        apps = [{'name': n, 'downloadURL': n, 'versionDate': d, **extra}
                for n, d, extra in [('Old owner', '2020-01-01', {'_addedFromLink': True}),
                                    ('KSign', '2020-01-01', {}),
                                    ('Older', '2024-01-01', {}),
                                    ('Newest', '2026-01-01', {}),
                                    ('Broken', '2027-01-01', {})]]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'catalog-policy.json').write_text('{"maxApps":3}')
            (root/'source-health.json').write_text(json.dumps({'links': {'x': {'url':'Broken', 'status':'missing'}}}))
            source = {'apps': apps}
            apply_limit(source, root)
            self.assertEqual([a['name'] for a in source['apps']], ['Old owner', 'KSign', 'Newest'])
            apply_limit(source, root)
            self.assertEqual(len(source['apps']), 3)

    def test_refuses_to_remove_protected_apps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'catalog-policy.json').write_text('{"maxApps":1}')
            source = {'apps':[{'name':'KSign'}, {'name':'ESign'}]}
            with self.assertRaises(ValueError):
                apply_limit(source, root)
            self.assertEqual(len(source['apps']), 2)
