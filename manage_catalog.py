"""Manage the live catalog from workflow inputs; no source writes before validation."""
import copy
import base64
import binascii
import hashlib
import html
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

import add_app_from_url as importer
import catalog_owner as owner
import source_guard


def env(name):
    return os.environ.get('MANAGE_' + name, '').strip()


def rows(apps):
    return [{'id': owner.app_id(a), 'name': a['name'], 'version': a.get('version'),
             'bundleIdentifier': a['bundleIdentifier'], 'downloadURL': a['downloadURL'],
             'iconURL': a.get('iconURL', ''), 'description': a.get('localizedDescription', '')} for a in apps]


def select(source, target):
    if not target:
        raise ValueError('Target is required: use the exact download URL, app ID, or unique exact name. Run list to find it.')
    matches = [a for a in source['apps'] if target in (a['downloadURL'], owner.app_id(a))]
    if not matches:
        matches = [a for a in source['apps'] if str(a.get('name', '')).casefold() == target.casefold()]
    if len(matches) != 1:
        raise ValueError(f'Target matched {len(matches)} apps; nothing changed. Run list and use the exact URL or ID.')
    return matches[0]


def prepare_icon(value):
    """Accept only bounded image bytes; never trust the supplied extension."""
    if not value.startswith('data:'):
        return value, None
    if len(value) > 45000:
        raise ValueError('Uploaded icon is too large; use the image picker to resize it.')
    try:
        prefix, encoded = value.split(',', 1)
        mime = {'data:image/jpeg;base64': ('jpg', b'\xff\xd8\xff'),
                'data:image/png;base64': ('png', bytes.fromhex('89504e470d0a1a0a'))}
        extension, magic = mime[prefix]
        data = base64.b64decode(encoded, validate=True)
        if not data.startswith(magic) or len(data) > 32768:
            raise ValueError('Invalid or oversized icon bytes')
    except (KeyError, ValueError, binascii.Error) as error:
        raise ValueError('Icon upload must be a small JPEG or PNG image') from error
    name = 'owner-' + hashlib.sha256(data).hexdigest()[:24] + '.' + extension
    url = 'https://raw.githubusercontent.com/sgad73055-code/ipastrong/main/assets/app-icons/' + name
    return url, ('assets/app-icons/' + name, data)


def execute(root, action, target='', updates=None, dry_run=False, clear_description=False, clear_icon=False):
    updates = dict(updates or {})
    icon_asset = None
    if updates.get('iconURL'):
        updates['iconURL'], icon_asset = prepare_icon(updates['iconURL'])
    old = (root / 'ipastrong.json').read_bytes()
    source = json.loads(old)
    source_guard.validate(source)
    state = owner.load(root / 'catalog-owner.json')
    before = len(source['apps'])
    if action == 'list':
        query = target.casefold()
        matches = [a for a in source['apps'] if query in (' '.join(str(a.get(k, '')) for k in ('name', 'bundleIdentifier', 'downloadURL')) + ' ' + owner.app_id(a)).casefold()]
        return {'action': action, 'matched': len(matches), 'shown': min(len(matches), 200), 'apps': rows(matches[:200]), 'written': False}
    candidate = copy.deepcopy(source)
    state = copy.deepcopy(state)
    if action == 'restore':
        matches = [r for r in state['rules'] if target in r['urls'] or target in r['keys']] if target else []
        if len(matches) != 1:
            raise ValueError('Restore needs the exact original URL or ID from the earlier report; nothing changed.')
        rule = matches[0]
        state['rules'].remove(rule)
        if rule.get('seed'):
            candidate['apps'] = [a for a in candidate['apps'] if owner.app_id(a) not in rule['keys']]
            candidate['apps'].insert(0, copy.deepcopy(rule['seed']))
    elif action in ('edit', 'delete', 'add'):
        original = select(source, target) if action != 'add' else None
        if action == 'add' and not updates.get('downloadURL'):
            raise ValueError('Add requires a direct HTTPS IPA URL in url.')
        old_url = original['downloadURL'] if original else updates['downloadURL']
        prior = next((r for r in state['rules'] if (owner.app_id(original) in r['keys'] if original else old_url in r['urls'])), None)
        if action == 'add' and (any(a['downloadURL'] == old_url for a in source['apps']) or (prior and not prior.get('deleted'))):
            raise ValueError('URL already exists or has an active owner rule; use edit or restore.')
        if action == 'delete':
            urls = list(dict.fromkeys((prior['urls'] if prior else []) + [old_url] + [v['downloadURL'] for v in original.get('versions', [])]))
            rule = {'keys': list(dict.fromkeys((prior['keys'] if prior else []) + [owner.app_id(original)])), 'urls': urls, 'deleted': True, 'seed': copy.deepcopy(prior.get('seed', original) if prior else original)}
        else:
            patch = copy.deepcopy(prior.get('patch', {}) if prior else {})
            new_url = updates.get('downloadURL', old_url)
            if new_url != old_url and any(a['downloadURL'] == new_url for a in source['apps'] if a is not original):
                raise ValueError('Replacement URL belongs to another app; nothing changed.')
            if action == 'add' or new_url != old_url:
                # Verify bytes and metadata rather than accepting an HTML page or suffix.
                with tempfile.TemporaryDirectory() as d:
                    path = Path(d) / 'app.ipa'
                    size, digest = importer.download(new_url, path)
                    metadata = importer.inspect(path)
                    icon = importer.extract_release_icon(new_url, root, digest) or importer.extract_icon(path, root, metadata, digest)
                if original and metadata['bundle'].casefold() != original['bundleIdentifier'].casefold():
                    raise ValueError('Replacement IPA has a different bundle identifier; add it separately.')
                imported = importer.add(importer.fixture(), metadata, new_url, size, digest, icon=icon)['apps'][0]
                patch.update({k: v for k, v in imported.items() if k not in ('name', 'iconURL', 'localizedDescription', '_sourceURL', '_addedFromLink')})
                if action == 'add':
                    patch.update(imported)
                else:
                    for k in ('minOSVersion', 'maxOSVersion'):
                        if k not in imported:
                            patch.pop(k, None)
            for key in ('name', 'localizedDescription', 'iconURL'):
                if key in updates:
                    if key == 'iconURL':
                        importer.check_url(updates[key])
                    patch[key] = updates[key]
            if clear_description:
                patch['localizedDescription'] = ''
            if clear_icon:
                patch['iconURL'] = ''
            if action == 'edit' and not updates and not clear_description and not clear_icon:
                raise ValueError('No changes supplied. Fill name, description, icon or url.')
            rule = {'urls': list(dict.fromkeys((prior['urls'] if prior else []) + [old_url, new_url])),
                    'patch': patch, 'seed': copy.deepcopy(prior.get('seed', original) if prior else original or patch)}
        if action != 'delete':
            edited = copy.deepcopy(original or patch)
            edited.update(patch)
            rule['keys'] = list(dict.fromkeys((prior['keys'] if prior else []) + ([owner.app_id(original)] if original else []) + [owner.app_id(edited)]))
        if prior:
            state['rules'].remove(prior)
        state['rules'].append(rule)
    else:
        raise ValueError('Unknown operation; use list, edit, delete, add or restore.')
    owner.apply(candidate, state)
    if (root / 'catalog-policy.json').exists():
        from catalog_policy import apply_policy
        apply_policy(candidate, root / 'catalog-policy.json')
    source_guard.validate(candidate)
    # Owner rules must agree with existing policies before anything is written.
    if action in ('edit', 'add') and not any(a['downloadURL'] == rule['patch'].get('downloadURL', old_url) for a in candidate['apps']):
        raise ValueError('Existing catalog policy blocks this app; no changes written.')
    if action == 'delete':
        assert not any(owner.app_id(a) in rule['keys'] for a in candidate['apps'])
    report = {'action': action, 'dryRun': dry_run, 'before': before, 'after': len(candidate['apps']),
              'written': not dry_run, 'rules': len(state['rules'])}
    if action != 'restore':
        report['target'] = rows([original])[0] if original else rows([rule['seed']])[0]
        report['savedRule'] = rule
    if not dry_run:
        candidate['lastUpdated'] = datetime.now(timezone.utc).isoformat()
        # Both files are committed together by Actions; failed jobs never push.
        if icon_asset:
            source_guard.atomic_bytes(root / icon_asset[0], icon_asset[1])
        source_guard.atomic_bytes(root / 'catalog-owner.json', (json.dumps(state, ensure_ascii=False, indent=2) + '\n').encode())
        source_guard.publish(root, old, candidate)
    return report


def main():
    root = Path(__file__).resolve().parent
    updates = {k: env(v) for k, v in [('name', 'NAME'), ('localizedDescription', 'DESCRIPTION'), ('iconURL', 'ICON'), ('downloadURL', 'URL')] if env(v)}
    try:
        report = execute(root, env('ACTION') or 'list', env('TARGET'), updates, env('DRY_RUN') == 'true', env('CLEAR_DESCRIPTION') == 'true', env('CLEAR_ICON') == 'true')
    except (ValueError, OSError) as error:
        report = {'error': str(error), 'written': False}
        write_report(root, report)
        raise SystemExit('Operation failed; no commit was pushed. See catalog-management-report artifact.')
    write_report(root, report)
    print('Catalog operation complete. See the run summary and catalog-management-report artifact.')


def write_report(root, report):
    text = json.dumps(report, ensure_ascii=False, indent=2)
    (root / 'catalog-management-report.json').write_text(text + '\n', encoding='utf-8')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write('## IPA Strong — نتيجة إدارة التطبيقات\n\nالتقرير الكامل متاح ضمن Artifacts باسم catalog-management-report.\n\n<pre>' + html.escape(text[:150000]) + '</pre>\n')


if __name__ == '__main__':
    main()
