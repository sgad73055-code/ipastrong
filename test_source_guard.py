import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_guard as g

NOW = 2000000000
URL = 'https://example.org/main.ipa'
ALT = 'https://example.org/mirror.ipa'

def app(name='Example', version='2.0', url=URL):
    return {'name':name, 'bundleIdentifier':'com.example.app', '_sourceURL':'local',
            'version':version, 'versionDate':'2026-10-01', 'downloadURL':url, 'size':123,
            'versions':[{'version':version,'date':'2026-10-01','downloadURL':url,'size':123}]}

def source(): return {'name':'IPA Strong','apps':[app()]}

def missing(state, url=URL):
    g.record(state, url, {'status':'missing','http':404}, NOW-3600)
    g.record(state, url, {'status':'missing','http':404}, NOW)

class GuardTests(unittest.TestCase):
    def test_valid_source(self): g.validate(source())
    def test_empty_source_rejected(self):
        with self.assertRaises(ValueError): g.validate({'name':'x','apps':[]})
    def test_bad_date_rejected(self):
        s=source();s['apps'][0]['versions'][0]['date']='not-date'
        with self.assertRaises(ValueError):g.validate(s)
    def test_html_url_not_accepted_as_relative(self):
        s=source();s['apps'][0]['downloadURL']='file:///a.ipa'
        with self.assertRaises(ValueError):g.validate(s)
    def test_bad_size_rejected(self):
        s=source();s['apps'][0]['size']='10 MB'
        with self.assertRaises(ValueError):g.validate(s)
    def test_mismatched_current_rejected(self):
        s=source();s['apps'][0]['version']='3.0'
        with self.assertRaises(ValueError):g.validate(s)
    def test_preserve_missing_owner_app(self):
        s=source();c={'name':'IPA Strong','apps':[app('Other')]};r,n=g.preserve(s,c)
        self.assertEqual(n,1);self.assertEqual(len(r['apps']),2)
    def test_preserve_old_versions(self):
        s=source();s['apps'][0]['_sourceURL']='https://repo.example';c=copy.deepcopy(s);c['apps'][0]=dict(app(version='3.0',url=ALT),_sourceURL='https://repo.example')
        r,_=g.preserve(s,c);self.assertEqual(len(r['apps'][0]['versions']),2)
    def test_owner_metadata_cannot_be_overwritten(self):
        s=source();c=source();c['apps'][0]['localizedDescription']='changed by importer'
        r,_=g.preserve(s,c);self.assertEqual(r['apps'][0],s['apps'][0])
    def test_no_duplicate_versions(self):
        r,_=g.preserve(source(),source());self.assertEqual(len(r['apps'][0]['versions']),1)
    def test_single_404_never_repaired(self):
        s=source();state={};g.record(state,URL,{'status':'missing'},NOW)
        self.assertEqual(g.apply_repairs(s,state,NOW),([],[]));self.assertEqual(s['apps'][0]['downloadURL'],URL)
    def test_immediate_retry_not_second_run(self):
        state={};g.record(state,URL,{'status':'missing'},NOW);g.record(state,URL,{'status':'missing'},NOW+5)
        self.assertEqual(state['links'][g.url_id(URL)]['missingRuns'],1)
    def test_restriction_breaks_missing_streak(self):
        state={};missing(state);g.record(state,URL,{'status':'restricted','http':403},NOW+3600)
        self.assertEqual(state['links'][g.url_id(URL)]['missingRuns'],0)
    def test_timeout_never_deletes(self):
        s=source();state={};missing(state);g.record(state,URL,{'status':'temporary'},NOW+3600)
        g.apply_repairs(s,state,NOW+3600);self.assertEqual(len(s['apps']),1)
    def test_no_fallback_preserves_broken_entry(self):
        s=source();state={};missing(state);r,u=g.apply_repairs(s,state,NOW)
        self.assertEqual(len(u),1);self.assertEqual(len(s['apps']),1)
    def test_same_release_verified_fallback(self):
        s=source();s['apps'][0]['versions'].append(dict(s['apps'][0]['versions'][0],downloadURL=ALT))
        state={};missing(state);g.record(state,ALT,{'status':'ok'},NOW)
        r,u=g.apply_repairs(s,state,NOW);self.assertEqual(len(r),1);self.assertEqual(s['apps'][0]['downloadURL'],ALT);g.validate(s)
    def test_no_automatic_downgrade(self):
        s=source();s['apps'][0]['versions'].append({'version':'1.0','date':'2020-01-01','downloadURL':ALT,'size':1})
        state={};missing(state);g.record(state,ALT,{'status':'ok'},NOW)
        self.assertIsNone(g.choose_fallback(s['apps'][0],state,NOW))
    def test_other_variant_never_used(self):
        s=source();s['apps'].append(app('Example++',url=ALT));state={};missing(state);g.record(state,ALT,{'status':'ok'},NOW)
        self.assertIsNone(g.choose_fallback(s['apps'][0],state,NOW))
    def test_stale_fallback_not_used(self):
        a=app();a['versions'].append(dict(a['versions'][0],downloadURL=ALT));state={};g.record(state,ALT,{'status':'ok'},NOW-90000)
        self.assertIsNone(g.choose_fallback(a,state,NOW))
    def test_round_robin_coverage(self):
        s=source();s['apps'].append(app('Other',url=ALT));state={};first=g.select_urls(s,state,1)[0]
        g.record(state,first,{'status':'temporary'},NOW);self.assertNotEqual(first,g.select_urls(s,state,1)[0])
    def test_overrides_survive_refresh(self):
        s=source();g.apply_overrides(s,{URL:{'downloadURL':ALT,'size':456}})
        self.assertEqual(s['apps'][0]['versions'][0]['downloadURL'],ALT);g.validate(s)
    def test_owner_override_applied_after_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);base=source();base['_downloadOverrides']={URL:{'downloadURL':ALT,'size':456}}
            (p/'ipastrong.json').write_text(json.dumps(base))
            with patch.object(g,'candidate_source',return_value=(source(),{})):
                g.run(p,0)
            self.assertEqual(g.read(p/'ipastrong.json')['apps'][0]['downloadURL'],ALT)
    def test_backup_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);old=source();new=source();new['apps'].append(app('Other'))
            old_bytes=json.dumps(old).encode();(p/'ipastrong.json').write_bytes(old_bytes)
            g.publish(p,old_bytes,new);self.assertEqual(len(g.read(p/'ipastrong.json')['apps']),2)
            g.rollback(p);self.assertEqual((p/'ipastrong.json').read_bytes(),old_bytes)
    def test_invalid_publish_leaves_source_and_backup_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);data=json.dumps(source()).encode();(p/'ipastrong.json').write_bytes(data)
            with self.assertRaises(ValueError):g.publish(p,data,{'name':'x','apps':[]})
            self.assertEqual((p/'ipastrong.json').read_bytes(),data);self.assertFalse((p/'backups').exists())
    def test_upstream_failure_never_publishes(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);data=json.dumps(source()).encode();(p/'ipastrong.json').write_bytes(data)
            with patch.object(g,'candidate_source',side_effect=ValueError('all sources failed')):
                with self.assertRaises(ValueError):g.run(p,0)
            self.assertEqual((p/'ipastrong.json').read_bytes(),data)
    def test_corrupt_source_auto_restored(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);data=json.dumps(source()).encode();g.publish(p,data,source())
            (p/'ipastrong.json').write_text('{broken')
            restored,base,recovered=g.load_base(p)
            self.assertTrue(recovered);self.assertEqual(restored,data);self.assertEqual(base,source())
    def test_corrupt_backup_never_overwrites_source(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'ipastrong.json').write_text('{broken');(p/'backups').mkdir();(p/'backups/ipastrong.last-good.json.gz').write_bytes(b'broken')
            with self.assertRaises(Exception):g.load_base(p)
            self.assertEqual((p/'ipastrong.json').read_text(),'{broken')
    def test_recovery_commits_even_when_sources_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);data=json.dumps(source()).encode();g.publish(p,data,source());(p/'ipastrong.json').write_text('{broken')
            with patch.object(g,'candidate_source',side_effect=ValueError('offline')):
                report=g.run(p,0)
            self.assertTrue(report['recoveredPublishedSource']);g.validate(g.read(p/'ipastrong.json'))
    def test_corrupt_health_state_resets_without_removing_apps(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'ipastrong.json').write_text(json.dumps(source()));(p/g.STATE_NAME).write_text('{broken')
            report=g.run(p,0,False);self.assertEqual(report['outputApps'],1)
    def test_zero_limit_does_no_network(self):
        def fail(url): raise AssertionError('network called')
        r=g.monitor(source(),{},0,NOW,fail);self.assertEqual(r['checked'],0)
    def test_probe_cannot_accept_html_200(self):
        class Response:
            status=200
            headers={'Content-Type':'text/html','Content-Length':'100'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):self_n=n;return b'<htm'
        with patch('urllib.request.urlopen',return_value=Response()):self.assertEqual(g.probe(URL)['status'],'not_ipa')
    def test_probe_reads_only_four_bytes(self):
        class Response:
            status=206
            headers={'Content-Range':'bytes 0-3/12345'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):
                if n!=4:raise AssertionError('unbounded transfer')
                return b'PK\x03\x04'
        with patch('urllib.request.urlopen',return_value=Response()):
            r=g.probe(URL);self.assertEqual(r['status'],'ok');self.assertEqual(r['size'],12345)

if __name__=='__main__':unittest.main()
