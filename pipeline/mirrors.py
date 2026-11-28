"""One copy per build: drop mirror copies of the same IPA (e.g. a proxy of a GitHub release).

Two entries are the same build only when bundle ID, version AND the IPA file name are the same
(or bundle + version + exact byte size when the file name is hidden). Different mods of the same
app have different file names/sizes, so they are never merged.
"""
import re
from urllib.parse import unquote, urlsplit

PROXY_HOSTS = ('proxy-files.thuthuatjb.com',)


def file_name(url):
    part = urlsplit(str(url or ''))
    path = unquote(part.path + ('?' + part.query if part.query else ''))
    name = path.rstrip('/').rsplit('/', 1)[-1].rsplit('=', 1)[-1].casefold()
    return name if name.endswith(('.ipa', '.tipa')) else ''


def _rank(app):
    host = urlsplit(str(app.get('downloadURL', ''))).netloc.casefold()
    owner = bool(app.get('_addedFromLink') or app.get('_featured') or app.get('_sourceURL') == 'local')
    # Owner entries first, then direct links (GitHub etc.) before proxies, then the plain name.
    return (not owner, host in PROXY_HOSTS, ' — ' in str(app.get('name', '')), len(str(app.get('name', ''))))


def remove_mirrors(source):
    groups = {}
    for index, app in enumerate(source['apps']):
        bundle = str(app.get('bundleIdentifier', '')).casefold()
        version = str(app.get('version', ''))
        name = file_name(app.get('downloadURL'))
        size = app.get('size') if type(app.get('size')) is int and app.get('size', 0) > 1_000_000 else None
        key = (bundle, version, 'f', name) if name else ((bundle, version, 's', size) if size else None)
        if key and bundle and version:
            groups.setdefault(key, []).append(index)
    drop = set()
    for indexes in groups.values():
        if len(indexes) > 1:
            keep = min(indexes, key=lambda i: _rank(source['apps'][i]))
            drop.update(i for i in indexes if i != keep)
    if drop:
        source['apps'] = [a for i, a in enumerate(source['apps']) if i not in drop]
    return {'removedMirrors': len(drop)}
