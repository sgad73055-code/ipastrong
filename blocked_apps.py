"""Owner-removed families: TikTok/Instagram LRD and SAT builds, all Snapchat, and the whole FastSign source."""
import re
from urllib.parse import unquote, urlsplit


import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).with_name('source-config.json')
try:
    _CONFIG = json.loads(_CONFIG_PATH.read_text(encoding='utf-8')) if _CONFIG_PATH.exists() else {}
except ValueError:
    _CONFIG = {}
BLOCKED_HOSTS = tuple(h.casefold() for h in _CONFIG.get('blockedHosts', ['fastsign.dev']))
BLOCKED_BUNDLES = {b.casefold() for b in _CONFIG.get('blockedBundles', [])}
BLOCKED_PREFIXES = tuple(b.casefold() for b in _CONFIG.get('blockedBundlePrefixes', []))
BLOCKED_NAMES = {n.casefold() for n in _CONFIG.get('blockedNames', [])}

# FastSign: removed entirely by the owner (credits/ads inside its builds).
FASTSIGN = re.compile(r'fastsign\.dev', re.I)
FASTSIGN_CREDIT = re.compile(r'\s*FastSign is operated by CertFish\.?(?:\s*The easy way to sideload:?\s*https?://cert\.fish/?)?', re.I)


def is_fastsign(app):
    links = [app.get('_sourceURL'), app.get('downloadURL')] + [v.get('downloadURL') for v in app.get('versions', [])]
    return any(FASTSIGN.search(str(u or '')) for u in links)


def strip_fastsign_credit(app):
    changed = 0
    for item in [app] + app.get('versions', []):
        for field in ('localizedDescription', 'versionDescription', 'subtitle'):
            value = item.get(field)
            if isinstance(value, str) and FASTSIGN_CREDIT.search(value):
                item[field] = FASTSIGN_CREDIT.sub('', value).rstrip()
                changed += 1
    return changed


def is_foreign_host(app):
    links = [app.get('_sourceURL'), app.get('downloadURL')] + [v.get('downloadURL') for v in app.get('versions', [])]
    hosts = [urlsplit(str(u or '')).netloc.casefold() for u in links]
    return any(h == b or h.endswith('.' + b) for h in hosts for b in BLOCKED_HOSTS)


def is_competitor_store(app):
    bundle = str(app.get('bundleIdentifier', '')).casefold()
    name = str(app.get('name', '')).strip().casefold()
    return (bundle in BLOCKED_BUNDLES or name in BLOCKED_NAMES
            or (bool(BLOCKED_PREFIXES) and bundle.startswith(BLOCKED_PREFIXES)))


DEAD_MARK = re.compile(r'Removed from the repo:|Status:\s*❌|\bThis is not working\b')


def is_marked_dead(app):
    # The uploader itself marked the build as removed/broken.
    return bool(DEAD_MARK.search(str(app.get('localizedDescription') or '')))


def is_blocked(app):
    if is_fastsign(app) or is_foreign_host(app) or is_competitor_store(app) or is_marked_dead(app):
        return True
    bundle = str(app.get('bundleIdentifier', '')).casefold()
    name = str(app.get('name', ''))
    if bundle.startswith('com.toyopagroup.') or re.search(r'snap[\s_\-]?chat|سناب ?شات', name, re.I):
        return True
    social = (bundle.startswith(('com.zhiliaoapp.', 'com.ss.iphone.ugc.', 'com.burbn.instagram'))
              or re.search(r'tik[\s_\-]?tok|instagram', name, re.I))
    if not social:
        return False
    links = [app.get('downloadURL')] + [v.get('downloadURL') for v in app.get('versions', [])]
    labels = [name] + [unquote(urlsplit(str(u or '')).path.rsplit('/', 1)[-1]) for u in links]
    # LRD may be glued (InstaNyxLRD). SAT must be a separate tag so Satella is not matched.
    return any(re.search(r'lrd|(?<![a-z])sat(?![a-z])|(?:tiktok|instagram)sat(?![a-z])', s, re.I)
               for s in labels)


def remove_blocked(source):
    before = len(source['apps'])
    source['apps'] = [a for a in source['apps'] if not is_blocked(a)]
    cleaned = sum(strip_fastsign_credit(a) for a in source['apps'])
    return {'removedApps': before - len(source['apps']), 'strippedCredits': cleaned}
