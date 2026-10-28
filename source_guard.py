"""Conservative IPA source maintenance, Python standard library only."""
import argparse
import concurrent.futures
import copy
import gzip
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE_NAME = 'source-health.json'
REPORT_NAME = 'source-health-report.json'

def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else copy.deepcopy(default)

def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.source-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def write(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode())

def valid_url(url):
    if not isinstance(url, str): return False
    p = urllib.parse.urlsplit(url)
    return p.scheme in ('https', 'http') and bool(p.hostname) and not p.username and not p.password

def key(app):
    # Exact variant name: never substitute a different tweak using the same bundle ID.
    return (str(app.get('bundleIdentifier', '')).casefold(), str(app.get('name', '')).strip().casefold(), str(app.get('_sourceURL', 'local')))

def validate(source):
    if not isinstance(source, dict) or not source.get('name') or not isinstance(source.get('apps'), list) or not source['apps']:
        raise ValueError('Empty or invalid source; publication blocked')
    # AltSourceKit decodes OSVersion from a JSON string. Some feeds emit 10.0
    # as a number; one such field prevents clients from decoding the whole repo.
    for entry in source['apps']:
        if not isinstance(entry, dict):
            continue
        records = [entry] + (entry.get('versions') if isinstance(entry.get('versions'), list) else [])
        for record in records:
            if not isinstance(record, dict):
                continue
            for field in ('minOSVersion', 'maxOSVersion'):
                value = record.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if value < 0 or not float('-inf') < value < float('inf'):
                        raise ValueError('Invalid OS version')
                    record[field] = str(value)
                elif value is not None and not isinstance(value, str):
                    raise ValueError('Invalid OS version type')
    for app in source['apps']:
        if not isinstance(app, dict) or not app.get('name') or not app.get('bundleIdentifier') or not valid_url(app.get('downloadURL')):
            raise ValueError('App missing required identity or download URL')
        if not isinstance(app.get('size'), int) or isinstance(app['size'], bool) or app['size'] < 0:
            raise ValueError('Invalid app size')
        versions = app.get('versions')
        if not isinstance(versions, list) or not versions:
            raise ValueError('App has no versions')
        current = False
        for version in versions:
            if not isinstance(version, dict) or not valid_url(version.get('downloadURL')) or not version.get('version'):
                raise ValueError('Invalid version')
            datetime.fromisoformat(str(version.get('date', '')).replace('Z', '+00:00'))
            if not isinstance(version.get('size'), int) or isinstance(version['size'], bool) or version['size'] < 0:
                raise ValueError('Invalid version size')
            current |= version['downloadURL'] == app['downloadURL'] and str(version['version']) == str(app.get('version'))
        if not current: raise ValueError('App download and version records disagree')
    json.dumps(source, allow_nan=False)

def preserve(old, candidate):
    result = copy.deepcopy(candidate)
    entries = {key(a): a for a in result['apps']}
    restored = 0
    for app in old['apps']:
        # Owner records must never be overwritten by external sources.
        if key(app) not in entries:
            clone = copy.deepcopy(app)
            result['apps'].append(clone)
            entries[key(app)] = clone
            restored += 1
        else:
            target = entries[key(app)]
            if app.get('_sourceURL', 'local') == 'local':
                owner = copy.deepcopy(app)
                target.clear()
                target.update(owner)
            seen = {(str(v.get('version')), v.get('downloadURL')) for v in target['versions']}
            for version in app.get('versions', []):
                identity = (str(version.get('version')), version.get('downloadURL'))
                if identity not in seen:
                    target['versions'].append(copy.deepcopy(version))
                    seen.add(identity)
    if len(result['apps']) < len(old['apps']) * .85:
        raise ValueError('Unexpected catalog shrink; publication blocked')
    return result, restored

def apply_overrides(source, overrides):
    source['_downloadOverrides'] = copy.deepcopy(overrides)
    for app in source['apps']:
        for item in [app] + app.get('versions', []):
            fix = overrides.get(item.get('downloadURL'))
            if not isinstance(fix, dict) or not valid_url(fix.get('downloadURL')): continue
            for field in ('downloadURL', 'size', 'minOSVersion', 'maxOSVersion', 'sha256'):
                if field in fix: item[field] = fix[field]
            for field in ('ipaUrl', 'ipaURL', 'downloadUrl', 'down'):
                if field in item: item[field] = item['downloadURL']

def load_merger(root):
    spec = importlib.util.spec_from_file_location('ipa_merger', root/'merge_sources.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def candidate_source(root, base):
    merger = load_merger(root)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(merger.fetch, merger.SOURCES))
    successful = sum(apps is not None for _, apps, _ in responses)
    if successful == 0: raise ValueError('All upstream sources failed; keeping published source')
    candidate, report = merger.build(base, responses)
    validate(candidate)
    return candidate, report

_locks = {}
_lock_guard = threading.Lock()

def probe(url, timeout=10):
    """Bounded GET, no downloads or execution; verify ZIP magic rather than trusting HTTP 200."""
    if not valid_url(url): return {'status': 'invalid'}
    host = urllib.parse.urlsplit(url).hostname
    with _lock_guard:
        lock = _locks.setdefault(host, threading.Semaphore(3))
    with lock:
        try:
            request = urllib.request.Request(url, headers={'Range': 'bytes=0-3', 'User-Agent': 'IPA-Strong-LinkMonitor/1.0'})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                magic = response.read(4)  # Servers ignoring Range still transfer at most four bytes to us.
                is_zip = magic in (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')
                total = re.search(r'/(\d+)$', response.headers.get('Content-Range', ''))
                length = total.group(1) if total else response.headers.get('Content-Length', '') if response.status == 200 else ''
                return {'status': 'ok' if is_zip else 'not_ipa', 'http': response.status,
                        'size': int(length) if length.isdigit() else None}
        except urllib.error.HTTPError as e:
            return {'status': 'missing' if e.code in (404, 410) else 'restricted' if e.code in (401, 403, 429) else 'temporary', 'http': e.code}
        except Exception as e:
            return {'status': 'temporary', 'error': type(e).__name__}

def url_id(url): return hashlib.sha256(url.encode()).hexdigest()

def record(state, url, observation, now):
    entry = state.setdefault('links', {}).setdefault(url_id(url), {'url': url, 'missingRuns': 0})
    previous = entry.get('checkedAt', 0)
    if observation['status'] == 'missing':
        if now - previous >= 1800: entry['missingRuns'] = entry.get('missingRuns', 0) + 1
    elif observation['status'] == 'ok':
        entry['missingRuns'] = 0
    else:
        # A restriction or timeout breaks consecutive missing observations.
        entry['missingRuns'] = 0
    entry.update(observation, checkedAt=now)
    return entry

def select_urls(source, state, limit):
    urls = list(dict.fromkeys(a['downloadURL'] for a in source['apps']))
    # Unknown and least-recently checked URLs first; do not repeatedly hammer broken links.
    urls.sort(key=lambda u: (state.get('links', {}).get(url_id(u), {}).get('checkedAt', 0), url_id(u)))
    return urls[:limit]

def choose_fallback(app, state, now):
    # Use only this exact variant's existing versions, and only the SAME release version.
    for version in app['versions']:
        url = version['downloadURL']
        if url == app['downloadURL'] or str(version['version']) != str(app['version']): continue
        health = state.get('links', {}).get(url_id(url), {})
        if health.get('status') == 'ok' and now - health.get('checkedAt', 0) <= 86400:
            return version
    return None

def apply_repairs(source, state, now):
    repairs, unresolved = [], []
    for app in source['apps']:
        health = state.get('links', {}).get(url_id(app['downloadURL']), {})
        if health.get('status') != 'missing' or health.get('missingRuns', 0) < 2: continue
        alternate = choose_fallback(app, state, now)
        if alternate is None:
            unresolved.append({'name': app['name'], 'url': app['downloadURL']})
            continue
        old_url = app['downloadURL']
        for field in ('downloadURL', 'size', 'minOSVersion', 'maxOSVersion', 'sha256', 'absoluteVersion'):
            app.pop(field, None)
            if field in alternate: app[field] = alternate[field]
        app.setdefault('size', 0)
        for field in ('ipaUrl', 'ipaURL', 'downloadUrl', 'down'):
            if field in app: app[field] = app['downloadURL']
        source.setdefault('_downloadOverrides', {})[old_url] = {f: app[f] for f in ('downloadURL', 'size', 'minOSVersion', 'sha256') if f in app}
        repairs.append({'name': app['name'], 'from': old_url, 'to': app['downloadURL']})
    return repairs, unresolved

def monitor(source, state, limit, now, prober=probe):
    selected = select_urls(source, state, limit)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for url, observation in zip(selected, pool.map(prober, selected)):
            record(state, url, observation, now)
    # Spend at most one extra batch checking fallback candidates of confirmed failures.
    alternatives = []
    for app in source['apps']:
        h = state.get('links', {}).get(url_id(app['downloadURL']), {})
        if h.get('status') == 'missing' and h.get('missingRuns', 0) >= 2:
            alternatives.extend(v['downloadURL'] for v in app['versions'] if str(v['version']) == str(app['version']) and v['downloadURL'] != app['downloadURL'])
    alternatives = list(dict.fromkeys(alternatives))[:limit]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for url, observation in zip(alternatives, pool.map(prober, alternatives)):
            record(state, url, observation, now)
    repairs, unresolved = apply_repairs(source, state, now)
    # Bound state growth while keeping current and historical release URLs.
    active = {url_id(v['downloadURL']) for a in source['apps'] for v in a['versions']}
    state['links'] = {k:v for k,v in state.get('links', {}).items() if k in active}
    outcomes = {}
    for url in selected + alternatives:
        status = state.get('links', {}).get(url_id(url), {}).get('status', 'unknown')
        outcomes[status] = outcomes.get(status, 0) + 1
    return {'checked': len(selected)+len(alternatives), 'outcomes':outcomes, 'repaired': repairs, 'unresolved': unresolved}

def publish(root, old_bytes, source):
    if (root/'catalog-policy.json').exists():
        from catalog_policy import apply_policy
        apply_policy(source, root/'catalog-policy.json')
    validate(source)
    # Backup is updated only AFTER full validation, before the atomic source replacement.
    atomic_bytes(root/'backups/ipastrong.last-good.json.gz', gzip.compress(old_bytes, mtime=0))
    atomic_bytes(root/'ipastrong.json', (json.dumps(source, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode())

def rollback(root):
    data = gzip.decompress((root/'backups/ipastrong.last-good.json.gz').read_bytes())
    validate(json.loads(data))
    atomic_bytes(root/'ipastrong.json', data)

def load_base(root):
    data = (root/'ipastrong.json').read_bytes()
    try:
        base = json.loads(data)
        validate(base)
        return data, base, False
    except (ValueError, TypeError, KeyError):
        backup = root/'backups/ipastrong.last-good.json.gz'
        if not backup.exists(): raise ValueError('Published source invalid and no backup exists')
        restored = gzip.decompress(backup.read_bytes())
        base = json.loads(restored)
        validate(base)
        atomic_bytes(root/'ipastrong.json', restored)
        return restored, base, True

def run(root, limit=400, refresh=True):
    old_bytes, base, recovered = load_base(root)
    try:
        state = read(root/STATE_NAME, {'schema': 1, 'links': {}})
        if not isinstance(state, dict) or not isinstance(state.get('links'), dict):
            raise ValueError('Invalid health state')
    except (ValueError, TypeError):
        state = {'schema': 1, 'links': {}}
    now = time.time()
    try:
        candidate, upstream = candidate_source(root, base) if refresh else (copy.deepcopy(base), {'mode':'audit-only'})
    except Exception as error:
        if not recovered: raise
        # Publish the validated recovery even if upstream servers are unavailable.
        candidate, upstream = copy.deepcopy(base), {'mode':'backup-recovery', 'refreshError':str(error)}
    apply_overrides(candidate, base.get('_downloadOverrides', {}))
    source, restored = preserve(base, candidate)
    apply_overrides(source, base.get('_downloadOverrides', {}))
    policy_report = {'removedApps': 0, 'removedVersions': 0}
    if (root/'catalog-policy.json').exists():
        from catalog_policy import apply_policy
        policy_report = apply_policy(source, root/'catalog-policy.json')
    report = monitor(source, state, limit, now)
    validate(source)
    report.update(date=datetime.now(timezone.utc).isoformat(), inputApps=len(base['apps']), outputApps=len(source['apps']), preservedApps=restored, recoveredPublishedSource=recovered, removedApps=policy_report['removedApps'], catalogPolicy=policy_report, upstream=upstream)
    publish(root, old_bytes, source)
    write(root/STATE_NAME, state)
    write(root/REPORT_NAME, report)
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit-limit', type=int, default=400)
    parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.audit_limit <= 500: parser.error('audit-limit must be 0..500')
    if args.rollback:
        rollback(ROOT)
        print('Restored validated last-good source')
        return
    try:
        report = run(ROOT, args.audit_limit, not args.audit_only)
        print(json.dumps({k:report[k] for k in ('checked','inputApps','outputApps','removedApps','preservedApps')}, ensure_ascii=False))
    except Exception as error:
        # Never replace the source on fetch, parse, validation, or repair failure.
        write(ROOT/REPORT_NAME, {'blocked':True, 'error':str(error), 'date':datetime.now(timezone.utc).isoformat()})
        raise

if __name__ == '__main__': main()
