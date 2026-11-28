"""IPA Strong branding: remove other stores' credits/ads and show IPA Strong instead.

Rules (owner request):
- Text that advertises another store, repo, uploader or Telegram channel is removed.
- developerName that names another store/uploader (or is empty/Unknown) becomes "IPA Strong".
  Real app developers (Spotify, SayGames, Delta team ...) are kept: replacing them would be
  a false claim of authorship, and app names/tweak names (Regram, BHTwitter ...) stay so users
  can still recognise the build.
- Fields that only carry another store's monetisation/credits are dropped.
Everything is idempotent: running it twice gives the same result.
"""
import re

BRAND = 'IPA Strong'

# Stores, repos, uploaders and channels that must not be credited.
FOREIGN = (
    r'ipaomtk(?:\.com)?|apkomtk|ios ?vizor(?:\.com)?|ttjb(?: (?:ipa repo|team))?|thuthuatjb|nabz ?clan|nabzcraft|'
    r'karbin[- ]?store|neoncat[- ]og(?: ipa library)?|cypwn(?: ipa library)?|binnichtaktiv\'?s? ?ipa library|'
    r'ipa ?vault|owo source|ios tutorials \+ app cracks|iapps(?:bestlibrary)?|crack ?hub|cannon cracker|supercrack(?: inc\.)?|'
    r'apptesters(?: ipa repo)?|appdb|ipalibrary(?:\.me)?|ipawind|fayezupdates|sultan mods|hertzsign(?: ipa library)?|'
    r'trollstore appsupdates|zxcvbn[\'’]s tweaked ipas|karastore|esign\.yyyue\.xyz|sidelix|ikiraplus|ispot|ballermc|ipaspot|'
    r'ryuksign|kamohacks|rifty\'?s? ?(?:ipa ?library|repo)?|fastsign|certfish|cert\.fish|swaggyp36000 ipa library|'
    r'driftywinds\' altstore repo|ios_trollstore|dpixel|meemnon|ed0\.ipa|blatant|arianaminajj|'
    r'manpreet singh(?: @thisismanpreee?ts)?|lãng khách(?:🇻🇳)?|abodsyripa|dvntms?|تطبيقات ipa 🌙'
)
FOREIGN_RE = re.compile(FOREIGN, re.I)
PLACEHOLDER_DEV = re.compile(r'^\s*(?:|unknown|n/?a|null|none|-|ipa|iPAExtractor|reports\+|god mode.*)\s*$', re.I)
DEV_HANDLE = re.compile(r'(^|[\s/&,])(?:@[\w.]+|u/\w+)(?=$|[\s/&,])')

# Whole lines/sentences that are pure promotion for someone else.
LINE_DROP = [
    re.compile(r'^\s*Original app page:\s*https?://\S+\s*$', re.I),
    re.compile(r'^\s*Tham gia nhóm hỗ trợ của TTJB.*$', re.I),
    re.compile(r'^\s*https?://t\.me/(?!ipastrong\b)\S+\s*$', re.I),
    re.compile(r'^.*https?://t\.me/(?!ipastrong\b)\S+ for other [^\n]*$', re.I),
]
INLINE = [
    (re.compile(r'\s*\bListed by (?:IPAOMTK|iOSvizor)\.?', re.I), ''),
    (re.compile(r'^\s*ipaomtk\.com\s*\|\s*', re.I | re.M), ''),
    (re.compile(r'\s*-?\s*IPA đã được kiểm tra(?: và tổng hợp bởi[^\n]*)?$', re.I | re.M), ''),
    (re.compile(r'\s*-?\s*IPA đã được kiểm tra và tổng hợp bởi TT\w*(?: Team)?\.?', re.I), ''),
    (re.compile(r'Chức năng đã thêm:\s*', re.I), 'الميزة المضافة: '),
    (re.compile(r'\s*FastSign is operated by CertFish\.?(?:\s*The easy way to sideload:?\s*https?://cert\.fish/?)?', re.I), ''),
    (re.compile(r'\s*This was cracked by [^.\n]+\.', re.I), ''),
    (re.compile(r'\s*\b(?:Join|Follow)\b[^\n]*?(?:t\.me/(?!ipastrong\b)|telegram\.me/(?!ipastrong\b)|discord\.gg/)\S*(?: for more)?[.!]?', re.I), ''),
    (re.compile(r'\s*(?:tg)?@(?:ipavault|ipa_dark|kamohacks|riftysIPAlibrary)\b', re.I), ''),
    (re.compile(r'\s*\[?@ipavault\]?', re.I), ''),
    (re.compile(r'\s*[—-]\s*Sidelix App Store release\.?', re.I), ' — IPA Strong'),
    (re.compile(r'\bIPA ?Vault build\b', re.I), 'IPA Strong build'),
    (re.compile(r'\bAdded to IPA ?Vault source:', re.I), 'Added to IPA Strong:'),
    (re.compile(r'\s*(?:added )?by IPA ?Vault\b\.?', re.I), ''),
    (re.compile(r'\s*(?:Please )?report any crashes to our HelpDesk:?\s*https?://helpdesk\.nabzclan\S*', re.I), ''),
    (re.compile(r'\s*See app description on AppDB\.?', re.I), ''),
    (re.compile(r'\s*KamoHacks\b', re.I), ''),
    (re.compile(r'\s*\|?\s*If you want to donate(?: to me)?:?\s*-?\s*https?://(?:ko-fi\.com|www\.patreon\.com|patreon\.com|buymeacoffee\.com|paypal\.me)/\S+', re.I), ''),
]
# Tags inside app names such as "(IPAVault)" or "- IPAVault -".
# TGExtra is a tweak name (kept); IPAVault is a store tag (removed).
NAME_TAG = re.compile(r'\s*[\[(]\s*(?:IPAVault|driftywinds|tg@[\w]+|@[\w]+)\s*[\])]', re.I)
NAME_INNER = re.compile(r'\s*-\s*IPAVault\b|\s+IPAVault\s*$', re.I)

TEXT_FIELDS = ('localizedDescription', 'subtitle', 'versionDescription')
DROP_KEYS = ('patreon', 'contact', 'information', 'META', 'vipOnly', 'vipMinTier', 'freeAccess',
             'disableGuest', 'disableGuestAds', 'disableAdCode', 'popupAccess', 'latest_appstore_app')


def clean_text(value):
    if not isinstance(value, str) or not value:
        return value
    lines = [l for l in value.split('\n') if not any(p.match(l) for p in LINE_DROP)]
    text = '\n'.join(lines)
    for pattern, repl in INLINE:
        text = pattern.sub(repl, text)
    if text == value:
        return value  # nothing foreign: leave the owner's/upstream formatting untouched
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def clean_developer(value):
    value = str(value or '')
    if PLACEHOLDER_DEV.match(value) or FOREIGN_RE.search(value) or DEV_HANDLE.search(value):
        return BRAND
    return value.strip()


def clean_name(value):
    name = NAME_INNER.sub('', NAME_TAG.sub('', str(value or '')))
    name = re.sub(r'\s{2,}', ' ', re.sub(r'\(\s*\)', '', name)).strip()
    return name or str(value or '').strip()


def brand_app(app):
    changed = False
    def put(obj, key, new):
        nonlocal changed
        if obj.get(key) != new:
            obj[key] = new
            changed = True
    put(app, 'name', clean_name(app.get('name')))
    put(app, 'developerName', clean_developer(app.get('developerName')))
    for item in [app] + list(app.get('versions') or []):
        for field in TEXT_FIELDS:
            if field in item and isinstance(item[field], str):
                had_text = bool(item[field].strip())
                new = clean_text(item[field])
                if had_text and not new and item is app and field == 'localizedDescription':
                    new = f"{app.get('name', '')} — متوفر على {BRAND}"
                put(item, field, new)
    for key in DROP_KEYS:
        if key in app:
            del app[key]
            changed = True
    if isinstance(app.get('badges'), list):
        badges = [b for b in app['badges'] if not FOREIGN_RE.search(str(b.get('key', '')) + str(b.get('label', '')))]
        if badges != app['badges']:
            app['badges'] = badges
            changed = True
    return changed


def brand_source(source):
    changed = sum(brand_app(app) for app in source.get('apps', []))
    for item in source.get('news', []) or []:
        for field in ('title', 'caption'):
            if FOREIGN_RE.search(str(item.get(field, ''))):
                item[field] = clean_text(FOREIGN_RE.sub(BRAND, item[field]))
    return {'brandedApps': changed}


def foreign_mentions(source):
    """Visible text that still credits another store (used by the publish guard)."""
    hits = []
    for app in source.get('apps', []):
        visible = [app.get('name'), app.get('developerName')]
        for item in [app] + list(app.get('versions') or []):
            visible += [item.get(f) for f in TEXT_FIELDS]
        text = '\n'.join(str(v) for v in visible if v)
        if re.search(r'ipaomtk|iosvizor|ttjb|fastsign|certfish|t\.me/\+rvcO|riftysIPAlibrary', text, re.I):
            hits.append(app.get('name'))
    return hits
