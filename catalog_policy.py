"""Owner-approved catalog filtering. No network calls or dependency packages."""
import copy
import json
import re


def numeric_version(value):
    text = str(value)
    if not re.fullmatch(r'\d+(?:\.\d+)*', text):
        return None
    parts = list(map(int, text.split('.')))
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def older(value, minimum):
    a, b = numeric_version(value), numeric_version(minimum)
    if a is None or b is None:
        return False
    length = max(len(a), len(b))
    return a + (0,) * (length - len(a)) < b + (0,) * (length - len(b))


def identity(app):
    return (str(app.get('bundleIdentifier', '')).casefold(),
            str(app.get('name', '')).strip().casefold(),
            str(app.get('_sourceURL', 'local')))


def is_video_star(app):
    text = (str(app.get('name', '')) + ' ' +
            str(app.get('bundleIdentifier', ''))).casefold()
    text = re.sub(r'\s+', '', text)
    return 'videostar' in text or 'فيديوستار' in text


def apply_policy(source, path):
    if not path.exists():
        return {'removedApps': 0, 'removedVersions': 0}
    policy = json.loads(path.read_text(encoding='utf-8'))
    if policy.get('schema') != 1:
        raise ValueError('Unsupported catalog policy schema')
    blocked = policy.get('blockedURLs', [])
    rules = policy.get('versionFloors', [])
    allowed = policy.get('videoStarAllowed', [])
    if not all(isinstance(x, list) for x in (blocked, rules, allowed)):
        raise ValueError('Invalid catalog policy lists')
    if not all(isinstance(x, str) for x in blocked):
        raise ValueError('Invalid blocked URL')
    floors = {}
    for rule in rules:
        if not isinstance(rule, dict) or numeric_version(rule.get('minimumVersion')) is None:
            raise ValueError('Invalid minimum-version rule')
        floors[identity(rule)] = str(rule['minimumVersion'])
    if not all(isinstance(x, dict) and all(isinstance(x.get(k), str) and x[k]
               for k in ('bundleIdentifier', 'version', 'downloadURL')) for x in allowed):
        raise ValueError('Invalid Video Star allowlist')
    if policy.get('videoStarOnlyAllowed') and not allowed:
        raise ValueError('Video Star policy requires a selected edition')
    owner_versions = policy.get('videoStarAdditionalOwnerVersions', [])
    if not isinstance(owner_versions, list) or not all(isinstance(v, str) and numeric_version(v) is not None for v in owner_versions):
        raise ValueError('Invalid additional owner Video Star versions')
    allowed_keys = {(x['bundleIdentifier'].casefold(), x['version'], x['downloadURL']) for x in allowed}
    blocked = set(blocked)
    # Prefer the owner's exact records if an upstream copy has the same URL.
    owner_video_urls = {a.get('downloadURL') for a in source['apps']
                        if a.get('_sourceURL', 'local') == 'local' and is_video_star(a)}
    result, video_seen = [], set()
    removed, pruned = 0, 0
    for original in source['apps']:
        app = copy.deepcopy(original)
        video = is_video_star(app) and policy.get('videoStarOnlyAllowed')
        if video:
            selected = (str(app.get('bundleIdentifier', '')).casefold(),
                        str(app.get('version')), app.get('downloadURL'))
            owner_addition = (app.get('_sourceURL', 'local') == 'local' and str(app.get('version')) in owner_versions)
            if (selected not in allowed_keys and not owner_addition) or app.get('downloadURL') in video_seen:
                removed += 1
                continue
            if app.get('_sourceURL', 'local') != 'local' and app.get('downloadURL') in owner_video_urls:
                removed += 1
                continue
            video_seen.add(app['downloadURL'])
        minimum = floors.get(identity(app)) if app.get('_sourceURL', 'local') != 'local' else None
        if app.get('downloadURL') in blocked or (minimum and older(app.get('version'), minimum)):
            removed += 1
            continue
        versions = []
        for version in app.get('versions', []):
            rejected = version.get('downloadURL') in blocked
            if minimum and older(version.get('version'), minimum):
                rejected = True
            if video and (str(app.get('bundleIdentifier', '')).casefold(),
                          str(version.get('version')), version.get('downloadURL')) not in allowed_keys and not (
                              app.get('_sourceURL', 'local') == 'local' and
                              str(version.get('version')) in owner_versions):
                rejected = True
            if rejected:
                pruned += 1
            else:
                versions.append(version)
        if not versions:
            raise ValueError('Policy unexpectedly removed all versions of a retained app')
        app['versions'] = versions
        result.append(app)
    if not result:
        raise ValueError('Policy cannot publish an empty catalog')
    source['apps'] = result
    return {'removedApps': removed, 'removedVersions': pruned}
