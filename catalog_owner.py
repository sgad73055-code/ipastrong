"""Persistent owner edits, applied after upstream maintenance. Standard library only."""
import copy
import hashlib
import json


def app_id(app):
    identity = [str(app.get(k, '')) for k in ('downloadURL', 'bundleIdentifier', 'name', '_sourceURL')]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:16]


def load(path):
    state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema': 1, 'rules': []}
    if state.get('schema') != 1 or not isinstance(state.get('rules'), list):
        raise ValueError('Invalid owner catalog schema')
    for rule in state['rules']:
        if not isinstance(rule, dict) or not isinstance(rule.get('keys'), list) or not rule['keys'] or not isinstance(rule.get('urls'), list) or not rule['urls'] or not all(isinstance(u, str) and u for u in rule['urls']):
            raise ValueError('Invalid owner catalog URL rule')
        if rule.get('deleted') is not True and (not isinstance(rule.get('patch'), dict) or not isinstance(rule.get('seed'), dict)):
            raise ValueError('Invalid owner catalog edit')
    return state


def apply(source, state):
    """Keep unrelated records intact; idempotent across repeated publish calls."""
    for rule in state['rules']:
        keys = set(rule['keys'])
        if rule.get('deleted'):
            source['apps'] = [a for a in source['apps'] if app_id(a) not in keys]
            continue
        matches = [a for a in source['apps'] if app_id(a) in keys]
        app = copy.deepcopy(matches[0] if matches else rule['seed'])
        patch = copy.deepcopy(rule['patch'])
        # Metadata fields from an inspected replacement IPA stay consistent.
        if 'versions' in patch:
            for key in ('sha256', 'minOSVersion', 'maxOSVersion'):
                if key not in patch:
                    app.pop(key, None)
        app.update(patch)
        source['apps'] = [a for a in source['apps'] if app_id(a) not in keys]
        source['apps'].insert(0, app)
    return source


def apply_file(source, root):
    return apply(source, load(root / 'catalog-owner.json'))
