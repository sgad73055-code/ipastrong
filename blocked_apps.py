"""Owner-removed families: TikTok/Instagram LRD and SAT builds, and all Snapchat."""
import re
from urllib.parse import unquote, urlsplit


def is_blocked(app):
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
    return {'removedApps': before - len(source['apps'])}
