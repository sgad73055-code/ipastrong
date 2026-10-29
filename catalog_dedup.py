"""Collapse only identical current releases; never guess an IPA's bundle ID."""
import copy


def release_key(app):
    return (str(app.get('bundleIdentifier', '')).casefold(),
            str(app.get('version', '')), app.get('downloadURL'))


def deduplicate(source):
    groups = {}
    for app in source['apps']:
        groups.setdefault(release_key(app), []).append(app)
    result, removed = [], []
    for entries in groups.values():
        # Conflicting content hashes need inspection, even with the same URL.
        hashes = {a.get('sha256') for a in entries if a.get('sha256')}
        if len(entries) == 1 or len(hashes) > 1:
            result.extend(entries)
            continue
        # Keep owner-supplied metadata ahead of imported display names.
        preferred = next((a for a in entries if a.get('_sourceURL', 'local') == 'local'), entries[0])
        winner = copy.deepcopy(preferred)
        seen = {(str(v['version']), v['downloadURL']) for v in winner['versions']}
        for entry in entries:
            if entry is preferred:
                continue
            for version in entry.get('versions', []):
                identity = (str(version['version']), version['downloadURL'])
                if identity not in seen:
                    winner['versions'].append(copy.deepcopy(version))
                    seen.add(identity)
            if entry.get('_featured'):
                winner['_featured'] = True
            removed.append({'name': entry['name'], 'keptName': winner['name'],
                            'bundleIdentifier': entry['bundleIdentifier'],
                            'version': entry['version'], 'downloadURL': entry['downloadURL']})
        result.append(winner)
    source['apps'] = result
    return {'removedApps': len(removed), 'duplicates': removed}
