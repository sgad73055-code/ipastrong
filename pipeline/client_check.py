"""Make sure the published source opens in the installers subscribers use.

AltStore / SideStore need: name, bundleIdentifier, developerName, iconURL, localizedDescription
and versions[] with version, date, downloadURL, size (int).
ESign / Feather / KSign / Scarlet also read the top-level version, versionDate, downloadURL, size.
Anything that would make one of these apps reject the whole source is a hard error; the old
source then stays online. Softer problems are only counted for the report.
"""
import json
import re
from datetime import datetime
from urllib.parse import urlsplit

APP_TEXT = ('name', 'bundleIdentifier', 'developerName', 'version', 'downloadURL')
MAX_BYTES = 40 * 1024 * 1024  # very large sources time out on slow mobile connections


def _https(url):
    try:
        part = urlsplit(str(url))
        return part.scheme == 'https' and bool(part.netloc)
    except ValueError:
        return False


def _date(value):
    try:
        datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return True
    except ValueError:
        return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value)))


def check(source):
    errors, warnings = [], {}
    def warn(kind):
        warnings[kind] = warnings.get(kind, 0) + 1
    for key in ('name', 'identifier', 'sourceURL'):
        if not isinstance(source.get(key), str) or not source[key].strip():
            errors.append(f'source.{key} missing')
    apps = source.get('apps')
    if not isinstance(apps, list) or not apps:
        return {'ok': False, 'errors': errors + ['apps missing or empty'], 'warnings': warnings}
    for index, app in enumerate(apps):
        where = f"apps[{index}] {str(app.get('name', ''))[:40]!r}"
        for key in APP_TEXT:
            if not isinstance(app.get(key), str) or not app[key].strip():
                errors.append(f'{where}: {key} missing')
        if not isinstance(app.get('localizedDescription'), str):
            errors.append(f'{where}: localizedDescription must be text')
        if not _https(app.get('downloadURL')):
            errors.append(f'{where}: downloadURL is not https')
        if not _https(app.get('iconURL')):
            warn('iconMissingOrNotHttps')
        if type(app.get('size')) is not int or app['size'] < 0:
            errors.append(f'{where}: size must be a non-negative integer')
        versions = app.get('versions')
        if not isinstance(versions, list) or not versions:
            errors.append(f'{where}: versions missing')
            continue
        for v in versions:
            if not all(isinstance(v.get(k), str) and v[k] for k in ('version', 'downloadURL')):
                errors.append(f'{where}: version entry incomplete')
            if type(v.get('size')) is not int:
                errors.append(f'{where}: version size must be integer')
            if not _date(v.get('date')):
                warn('versionDateUnparsed')
        if not (app.get('localizedDescription') or '').strip():
            warn('emptyDescription')
    size = len(json.dumps(source, ensure_ascii=False, separators=(',', ':')).encode())
    if size > MAX_BYTES:
        errors.append(f'source is {size // 1048576} MB (> {MAX_BYTES // 1048576} MB)')
    return {'ok': not errors, 'errors': errors[:50], 'errorCount': len(errors),
            'warnings': warnings, 'bytes': size, 'apps': len(apps)}
