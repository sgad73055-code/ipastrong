"""Bound the published catalog while preserving owner imports and signing tools."""
import json
import re
from datetime import datetime, timezone


def release_date(app):
    values = [app.get(k) for k in ('versionDate', 'updatedAt', 'addedAt')]
    values += [v.get('date') for v in app.get('versions', [])]
    dates = []
    for value in values:
        try:
            date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            dates.append(date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp())
        except (ValueError, OverflowError, OSError):
            pass
    return max(dates, default=0)


def protected(app):
    name = re.sub(r'[^a-z0-9]', '', str(app.get('name', '')).lower())
    signing = ('ksign', 'esign', 'batsign', 'gbox', 'neosign', 'strongsign', 'ipastrongsign')
    return bool(app.get('_addedFromLink') or app.get('_featured') or
                any(name.startswith(word) for word in signing))


def apply_limit(source, root):
    policy_path = root / 'catalog-policy.json'
    policy = json.loads(policy_path.read_text()) if policy_path.exists() else {}
    maximum = policy.get('maxApps')
    if maximum is None:
        return {'removedApps': 0}
    if type(maximum) is not int or maximum < 1:
        raise ValueError('maxApps must be a positive integer')
    apps = source['apps']
    if len(apps) <= maximum:
        return {'removedApps': 0}
    state_path = root / 'source-health.json'
    try:
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        health = {v['url']: v.get('status') for v in state.get('links', {}).values()}
    except (ValueError, KeyError, AttributeError):
        health = {}
    pinned = [i for i, app in enumerate(apps) if protected(app)]
    if len(pinned) > maximum:
        raise ValueError('Protected owner apps exceed maxApps; refusing to discard them')
    pinned_set = set(pinned)
    # Missing/invalid links lose priority; otherwise prefer recent releases.
    ranked = sorted((i for i in range(len(apps)) if i not in pinned_set),
                    key=lambda i: (health.get(apps[i]['downloadURL']) not in ('missing', 'invalid'),
                                   release_date(apps[i]), -i), reverse=True)
    keep = pinned_set | set(ranked[:maximum - len(pinned)])
    source['apps'] = [app for i, app in enumerate(apps) if i in keep]
    return {'removedApps': len(apps) - len(source['apps']), 'maxApps': maximum,
            'protectedApps': len(pinned)}
