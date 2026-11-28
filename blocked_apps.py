"""Owner-removed families: TikTok/Instagram LRD and SAT builds, all Snapchat, and the whole FastSign source."""
import re
from urllib.parse import unquote, urlsplit


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


def is_blocked(app):
    if is_fastsign(app):
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
