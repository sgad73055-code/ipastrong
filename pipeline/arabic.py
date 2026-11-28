"""Arabic, tidy descriptions for every app.

Layout (plain text, works in ESign / Feather / KSign / AltStore and on the site):

    <one-line Arabic summary>
    ✨ المميزات: <features in Arabic>
    📱 يتطلب iOS <x> أو أحدث
    📝 الوصف الأصلي: <untranslated details, short>   (only until a translation exists)

- Feature lists ("Upstream variant", "Hack feature", "Injected with", Vietnamese "mở khoá"...)
  are translated with a glossary; unknown words (tweak names like RyukGram) stay as they are.
- Free-text descriptions are translated through translations/ar.json (filled by the owner or
  the daily maintenance task). Until an app has a translation, a short original excerpt is kept
  so no information is lost. Nothing is invented: no fake features, versions or claims.
- The upstream text is kept in _originalDescription so each refresh rebuilds from the source
  text and the result is identical every run (idempotent).
- Descriptions already written in Arabic (owner's own text) are left alone.
"""
import hashlib
import json
import re
from pathlib import Path

MARK = '✨'  # not used for detection; detection uses _originalDescription + HEADER_HINTS
HEADER_HINTS = ('✨ المميزات:', '📱 يتطلب iOS', '📝 الوصف الأصلي:', '— متوفر على IPA Strong')
EXCERPT = 420

WORDS = {
    'coins': 'العملات', 'coin': 'العملات', 'gems': 'الجواهر', 'gem': 'الجواهر', 'money': 'الأموال',
    'cash': 'النقود', 'gold': 'الذهب', 'energy': 'الطاقة', 'ammo': 'الذخيرة', 'currencies': 'العملات',
    'currency': 'العملات', 'hints': 'التلميحات', 'lives': 'الأرواح', 'life': 'الأرواح', 'keys': 'المفاتيح',
    'diamonds': 'الألماس', 'stars': 'النجوم', 'tickets': 'التذاكر', 'resources': 'الموارد', 'exp': 'الخبرة',
    'xp': 'الخبرة', 'hp': 'الصحة', 'health': 'الصحة', 'damage': 'الضرر', 'defense': 'الدفاع',
    'attack': 'الهجوم', 'atk': 'الهجوم', 'dmg': 'الضرر', 'speed': 'السرعة', 'moves': 'الحركات', 'credits': 'الرصيد',
    'shields': 'الدروع', 'nitro': 'النيترو', 'everything': 'كل شيء', 'all': 'كل شيء', 'points': 'النقاط',
    'boosters': 'المعززات', 'boosts': 'المعززات', 'spins': 'اللفات', 'skills': 'المهارات', 'mana': 'المانا',
    'stamina': 'القدرة', 'tokens': 'الرموز', 'cards': 'البطاقات', 'items': 'العناصر', 'time': 'الوقت',
    'fuel': 'الوقود', 'bullets': 'الطلقات', 'grenades': 'القنابل', 'upgrades': 'الترقيات', 'souls': 'الأرواح',
    'crystals': 'الكريستال', 'dna': 'الحمض النووي', 'rubies': 'الياقوت', 'pearls': 'اللؤلؤ', 'cookies': 'الكوكيز',
}

PHRASES = {
    'premium': 'بريميوم مفتوح', 'pro': 'نسخة Pro مفتوحة', 'vip': 'VIP مفتوح', 'plus': 'Plus مفتوح',
    'gold': 'Gold مفتوح', 'unlocked': 'مفتوح بالكامل', 'premium unlocked': 'بريميوم مفتوح',
    'pro unlocked': 'نسخة Pro مفتوحة', 'vip unlocked': 'VIP مفتوح', 'plus unlocked': 'Plus مفتوح',
    'subscription unlocked': 'الاشتراك مفتوح', 'subscription mở khoá': 'الاشتراك مفتوح',
    'subscription mở khóa': 'الاشتراك مفتوح', 'unlocked features': 'المميزات مفتوحة',
    'unlocked all': 'كل شيء مفتوح', 'unlocked all functions': 'كل المميزات مفتوحة',
    'mở khoá all functions': 'كل المميزات مفتوحة', 'open features': 'المميزات مفتوحة',
    'full game unlocked': 'اللعبة كاملة مفتوحة', 'modified features': 'مميزات معدّلة', 'mod': 'نسخة معدّلة',
    'mod.': 'نسخة معدّلة', 'mods': 'نسخة معدّلة', 'tweaked': 'نسخة معدّلة', 'original': 'النسخة الأصلية',
    'original.': 'النسخة الأصلية', 'no ads': 'بدون إعلانات', 'noads': 'بدون إعلانات', 'ads no': 'بدون إعلانات',
    'auto ads no': 'بدون إعلانات', 'without ads': 'بدون إعلانات', 'remove ads': 'بدون إعلانات',
    'iap': 'شراء داخل التطبيق مجاني', 'free iap': 'شراء داخل التطبيق مجاني',
    'free in-app purchases': 'شراء داخل التطبيق مجاني', 'free purchase': 'شراء مجاني',
    'free purchases': 'شراء مجاني', 'fake purchase': 'شراء مجاني', 'free shopping': 'تسوق مجاني',
    'free shop': 'متجر مجاني', 'free store': 'متجر مجاني', 'free store (buy then cancel)': 'متجر مجاني (اضغط شراء ثم إلغاء)',
    'unlocked features (buy then cancel)': 'المميزات مفتوحة (اضغط شراء ثم إلغاء)',
    'hack mua hàng trong ứng dụng (bấm mua rồi huỷ)': 'شراء مجاني داخل التطبيق (اضغط شراء ثم إلغاء)',
    'paid on the apple store': 'مدفوع بالمتجر الرسمي — هنا مجاني', 'paid in apple store': 'مدفوع بالمتجر الرسمي — هنا مجاني',
    'paid': 'مدفوع بالمتجر الرسمي — هنا مجاني', 'free': 'مجاني', 'everything is free': 'كل شيء مجاني',
    'never die': 'عدم الموت', 'god mode': 'وضع الخلود', 'one hit kill': 'قتل بضربة وحدة',
    'one-hit kill': 'قتل بضربة وحدة', 'ohk': 'قتل بضربة وحدة', 'auto win': 'فوز تلقائي', 'always win': 'فوز دائم',
    'high damage': 'ضرر عالي', 'multiply attack': 'مضاعفة الهجوم', 'high attack speed': 'سرعة هجوم عالية',
    'atk max': 'أقصى هجوم', 'gems max': 'أقصى جواهر', 'no reload': 'بدون إعادة تعبئة',
    'no skills cooldown': 'بدون وقت انتظار للمهارات', 'stupid enemies': 'أعداء أغبياء',
    'weak enemies': 'أعداء ضعاف', "enemy don't move": 'الأعداء ما يتحركون', 'freeze moves': 'تجميد الحركات',
    'debug menu': 'قائمة المطوّر', 'dev tool': 'أدوات المطوّر', 'menu': 'قائمة غش', 'mega menu': 'قائمة غش كبيرة',
    'esp': 'كشف الأعداء (ESP)', 'emulator': 'محاكي', 'igg': 'قائمة IGG', 'igg added': 'قائمة IGG',
    'việt hóa': 'ترجمة فيتنامية', 'enough currency': 'عملات كافية', 'add gold': 'إضافة ذهب',
    'add currency': 'إضافة عملات', '9 million coins': '9 مليون عملة', '9 million cash': '9 مليون نقود',
    'download videos': 'تحميل الفيديوهات', 'nothing': '', 'gain': '', 'general': '', 'settings': '', 's': '',
}

CATEGORY = {
    'games': 'لعبة', 'game': 'لعبة', 'other': 'تطبيق', 'utilities': 'أداة', 'entertainment': 'تطبيق ترفيه',
    'productivity': 'تطبيق إنتاجية', 'photo editing': 'تطبيق تعديل صور', 'music & audio': 'تطبيق موسيقى وصوتيات',
    'photo & video': 'تطبيق صور وفيديو', 'security & privacy': 'تطبيق حماية وخصوصية', 'education': 'تطبيق تعليمي',
    'social media': 'تطبيق تواصل اجتماعي', 'social': 'تطبيق تواصل اجتماعي', 'video editing': 'تطبيق مونتاج فيديو',
    'browsers': 'متصفح', 'customization': 'أداة تخصيص', 'messaging': 'تطبيق مراسلة', 'business': 'تطبيق أعمال',
    'developer': 'أداة مطوّرين', 'lifestyle': 'تطبيق نمط حياة', 'downloads': 'أداة تحميل', 'photo-video': 'تطبيق صور وفيديو',
}

FEATURE_LINE = re.compile(
    r'(?im)^\s*(?:upstream variant|hack features?|injected with|features?|mod(?: info)?|tweaks?|variant|'
    r'الميزة المضافة|chức năng đã thêm)\s*:?\s*(.+?)\s*$')
SEO = [
    re.compile(r'^\s*What is [^?\n]{1,120}\?\s*', re.I),
    re.compile(r'^[^.\n]{1,120}\bIPA is the iOS install(?:ation|able)(?: file| version| package)? (?:of|for) ', re.I),
]
ABOUT = re.compile(r'^\s*About [^\n]{1,80}\n+', re.I)
VI_CHARS = re.compile(r'[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]', re.I)
ARABIC = re.compile(r'[؀-ۿ]')
LATIN = re.compile(r'[A-Za-z]')


KURDISH = re.compile(r'[ێڕۆڤەڵ]')


def is_arabic(text):
    # Kurdish (Sorani) uses Arabic letters but is not Arabic: it gets translated like English.
    return len(ARABIC.findall(text)) > len(LATIN.findall(text)) and len(KURDISH.findall(text)) < 3


def base_name(name):
    return re.sub(r'\s+—\s+[\w.\-]+$', '', str(name or '')).strip()


def key(app):
    return f"{str(app.get('bundleIdentifier', '')).casefold()}|{base_name(app.get('name')).casefold()}"


def _word(w):
    return WORDS.get(w.casefold().strip())


def translate_feature(raw):
    f = raw.strip(' .:•-▎()[]"\'“”').strip()
    low = re.sub(r'\s+', ' ', f.casefold())
    if not low:
        return ''
    if low in PHRASES:
        return PHRASES[low]
    m = re.fullmatch(r'(?:unlimited|infinite|max) (.+)', low)
    if m and _word(m.group(1)):
        return f'{_word(m.group(1))} غير محدودة'
    if low in ('unlimited', 'unlimited everything', 'unlimited all'):
        return 'كل شيء غير محدود'
    m = re.fullmatch(r'(.+?) multiplier', low)
    if m and _word(m.group(1)):
        return f'مضاعفة {_word(m.group(1))}'
    m = re.fullmatch(r'(?:freeze|frozen) (.+)', low) or re.fullmatch(r'(.+?) freeze', low)
    if m and _word(m.group(1)):
        return f'تجميد {_word(m.group(1))}'
    m = re.fullmatch(r'(.+?) max', low)
    if m and _word(m.group(1)):
        return f'أقصى {_word(m.group(1))}'
    m = re.fullmatch(r'(?:high|more|x\d+|\d+x) (.+)', low)
    if m and _word(m.group(1)):
        return f'{_word(m.group(1))} أعلى'
    if _word(low):
        return _word(low)
    if VI_CHARS.search(f):
        return ''  # Vietnamese leftovers are not shown untranslated
    return f  # tweak / product names stay as they are (RyukGram, Satella, ASJTikTok ...)


BUY_CANCEL = re.compile(r'free purchases?:?\s*click\s*["“]?buy,?["”]?\s*then\s*["“]?cancel\.?["”]?\.?', re.I)


def split_features(text):
    text = BUY_CANCEL.sub('free store (buy then cancel)', text)
    parts = re.split(r'\s*(?:,|،|;|\+| - |•|▎|\||/)\s*', text)
    out = []
    for p in parts:
        t = translate_feature(p)
        if t and t not in out:
            out.append(t)
    return out


def parse(original, name):
    features, rest = [], []
    for line in original.split('\n'):
        m = FEATURE_LINE.match(line)
        if m:
            features += [f for f in split_features(m.group(1)) if f not in features]
        else:
            rest.append(line)
    prose = '\n'.join(rest).strip()
    for pattern in SEO:
        prose = pattern.sub('', prose, count=1)
    prose = ABOUT.sub('', prose, count=1).strip()
    prose = re.sub(r'\s*[—-]\s*متوفر على IPA Strong\s*$', '', prose).strip()
    prose = re.sub(r'\s*Last updated:\s*[\d-]+\s*(?:Status:\s*\S+)?\s*⭐?', '', prose).strip()
    simple = re.sub(r'\W', '', prose).casefold()
    plain_name = re.sub(r'\W', '', base_name(name)).casefold()
    if not simple or simple in (plain_name, plain_name + 'ios', plain_name + 'foriOS'.casefold()) or ARABIC.search(prose) and is_arabic(prose) and len(prose) < 60:
        prose = ''
    if VI_CHARS.search(prose) and not features:
        features = split_features(prose)
        prose = ''
    return features, prose


# Recurring English sentences from mod sources, translated by pattern. Order matters.
_T = lambda p, r: (re.compile(p, re.I), r)
TEMPLATES = [
    _T(r'「✓𝐏𝐀𝐈𝐃 𝐀𝐏𝐏」', 'تطبيق مدفوع بالمتجر الرسمي — هنا مجاني. '),
    _T(r'\bStatus:\s*[✅❌⭐🌟🔥]+', ''),
    _T(r'\bYou can read more about it here:?\s*\S+', ''),
    _T(r'\bThis mod was created by [^.!\n]+[.!]*', ''),
    _T(r'\b(?:This was )?cracked by [^.!\n]+?(?:\([^)]*\))?(?:[.!]+|$)', ''),
    _T(r'\bMade by [^.!\n]+ on github!?', ''),
    _T(r'\b[^.\n]{1,80} IPA is an? (?:iOS )?[^.\n]{0,60}?(?:package|file)(?: designed for iPhone and iPad)?(?: that (?:allows|enables) [^.\n]*)?\.?', ''),
    _T(r'\bThis is a modded version of ([^.!\n]+?)\s*(?:with the following tweaks:\s*([^\n]+))?[.!]*(?=\s|$)', lambda m: f'نسخة معدّلة من {m.group(1)}.' + (f' التويكات المضافة: {m.group(2).strip(" .")}.' if m.group(2) else '')),
    _T(r'\bThis is a mod for ([^.!\n,]+?)(?: on iOS/iPadOS)?, featuring over hundred customizable options[^.\n]*\.?', r'مود لـ \1 بأكثر من 100 خيار تخصيص، مع آخر إصدار من YTPlus/YTLite مفتوح.'),
    _T(r'\bThis is the cracked version of ([^,.\n]+), without the (?:Patreon DRM|Dan Account System DRM|paywall)[.!]*', r'نسخة \1 مفتوحة بدون قفل الاشتراك.'),
    _T(r'\bTHIS IS A BETA BUILD OF [^\n!]+? SO EXPECT BUGS/GLITCHES!*', 'نسخة تجريبية (Beta)، ممكن تطلع بيها أخطاء.'),
    _T(r'\bThis (?:includes|comes with) the following tweaks:\s*([^\n]+?)(?:\.\s|\.$|$)', r'التويكات المضافة: \1. '),
    _T(r'\bAdded Tweaks:\s*([^\n]+)', r'التويكات المضافة: \1'),
    _T(r'\bThis includes both ([^\n]+?) and ([^\n]+?)\.(?=\s|$)', r'تحتوي على \1 و \2.'),
    _T(r'\bThis includes (?:just )?([^\n]+?)(?:\.(?=\s|$)|$)', r'تحتوي على \1.'),
    _T(r'\bThis is a modded version of ([^.\n]+?) with ([^.\n]+?) added\.?', r'نسخة معدّلة من \1 مع \2.'),
    _T(r'\bThis works with sidestore!*', 'تشتغل على SideStore.'),
    _T(r'\bThis does not work with sidestore or livecontainer!*', 'ما تشتغل على SideStore ولا LiveContainer.'),
    _T(r'\bThis does not work with sidestore!*', 'ما تشتغل على SideStore.'),
    _T(r'\*\*?This does not work with sidestore!*\*\*?', 'ما تشتغل على SideStore.'),
    _T(r'\bSidestore is (?:no longer|not) supported\.?', 'ما تدعم SideStore.'),
    _T(r'\bThis requires a paid dev cert to work!*', 'تحتاج شهادة مطوّر مدفوعة حتى تشتغل.'),
    _T(r'\bThis enables Liquid Glass effect on the app\.?', 'تفعّل تأثير Liquid Glass بالتطبيق.'),
    _T(r'\biOS (\d+)\+ (?:is )?(?:Support(?:ed)?)!*', r'يدعم iOS \1 وأحدث.'),
    _T(r'\bThis version has original ([^.\n]+?) bundle ID\.?', r'هذي النسخة بنفس Bundle ID مال \1 الأصلي.'),
    _T(r'\bThis is a duplicated app, it can be installed alongside original ([^.(\n]+)[^.\n]*\.?', r'نسخة مكررة، تنصب جنب \1 الأصلي.'),
    _T(r'\bThis is an original version, it has original ([^.\n(]+?) bundle ID[^.\n]*\.?', r'نسخة بنفس Bundle ID مال \1 الأصلي.'),
    _T(r'(?m)^\s*([A-Z][\w+ ]{1,30}?) v?([\d.]+) with ([^\n(]+?)\s*(?:\(([^)\n]*iOS[^)\n]*)\))?\s*$', lambda m: {'YouTube': 'يوتيوب', 'YouTube Music': 'يوتيوب ميوزك', 'TikTok': 'تيك توك', 'Instagram': 'انستغرام', 'Facebook': 'فيسبوك', 'Telegram': 'تيليگرام', 'WhatsApp': 'واتساب', 'SoundCloud': 'ساوند كلاود', 'Spotify': 'سبوتيفاي'}.get(m.group(1).strip(), m.group(1).strip()) + f' {m.group(2)} مع {m.group(3).strip()}' + (f' ({m.group(4)})' if m.group(4) else '') + '.'),
    _T(r'\bDownloaded? (?:videos|videos?, audio)[^\n]*', None),
]
_MODLINE = re.compile(r'^\s*(?:[-•]\s*)?(?:Premium|Pro|VIP) Unlocked\s*$', re.I)


def auto_translate(prose):
    """Translate common mod-source sentences. Returns Arabic text, or None if English is left."""
    text = prose
    for pattern, repl in TEMPLATES:
        if repl is None:
            continue
        text = pattern.sub(repl, text) if not callable(repl) else pattern.sub(repl, text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s*\n\s*', '\n', text).strip(' \n.')
    if not text:
        return ''
    # what is left after removing tweak lists / product names?
    leftover = re.sub(r'التويكات المضافة:[^\n]*', '', text)
    leftover = re.sub(r'[\u0600-\u06FF]+', '', leftover)
    leftover = re.sub(r'\b(?:[A-Z][\w.+-]*|[\w.+-]*\d[\w.+-]*|iOS|SideStore|LiveContainer|Bundle|ID)\b', '', leftover)
    if len(re.findall(r'[a-z]{3,}', leftover)) <= 1:
        return text if text.endswith(('.', '!', '؟')) else text + '.'
    return None


def kind(app):
    category = str(app.get('_category') or app.get('category') or '').casefold()
    return CATEGORY.get(category, '')


def is_modded(app, features):
    return bool(features) or bool(re.search(r'(?i)\b(mod|plus|premium|pro|vip|hack|cracked|tweak|\+\+)', str(app.get('name'))))


def display_name(name):
    name = re.sub(r'\s*-?\s*\((?:Hacked|Free paid|Cracked)\)\s*$', '', base_name(name), flags=re.I)
    return name.strip(' -') or base_name(name)


def build(app, original, translation=None):
    name = display_name(app.get('name'))
    features, prose = parse(original, app.get('name'))
    if not translation and prose:
        auto = auto_translate(prose)
        if auto is not None:
            translation = auto or None
            prose = '' if auto is not None else prose
    if translation:
        summary = translation.strip()
    else:
        summary = f"{kind(app)} {name}".strip() + (' — نسخة معدّلة.' if is_modded(app, features) else '.')
        features = [f for f in features if f != 'نسخة معدّلة']
    lines = [summary]
    if features:
        lines.append('✨ المميزات: ' + '، '.join(features))
    min_os = str(app.get('minOSVersion') or '').strip()
    if re.fullmatch(r'\d+(?:\.\d+)*', min_os):
        lines.append(f'📱 يتطلب iOS {min_os} أو أحدث')
    if prose and not translation:
        excerpt = prose if len(prose) <= EXCERPT else prose[:EXCERPT].rsplit(' ', 1)[0] + '…'
        lines.append('📝 الوصف الأصلي: ' + re.sub(r'\n{2,}', '\n', excerpt))
    return '\n'.join(lines)


def load_translations(root):
    path = Path(root) / 'translations' / 'ar.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    except ValueError:
        data = {}
    return {k.casefold(): v for k, v in data.items() if isinstance(v, str) and v.strip() and not k.startswith('_')}


def _hash(text):
    return hashlib.sha1(str(text).encode()).hexdigest()[:12]


def arabize_app(app, translations):
    current = app.get('localizedDescription')
    if not isinstance(current, str):
        return False
    stored = app.get('_originalDescription')
    if stored is not None and app.get('_descriptionHash') == _hash(current):
        original = stored  # current text is our own previous build
    elif is_arabic(current) and not FEATURE_LINE.match(current.split('\n', 1)[0]):
        return False  # owner's Arabic text: keep as written
    else:
        original = current
    text = build(app, original, translations.get(key(app)))
    changed = text != current or stored != original
    app['localizedDescription'] = text
    app['_originalDescription'] = original
    app['_descriptionHash'] = _hash(text)
    # subtitle shown under the name on some installers: keep it short and Arabic too
    sub = app.get('subtitle')
    if isinstance(sub, str) and sub.strip() and not is_arabic(sub):
        app['subtitle'] = text.split('\n', 1)[0][:120]
    return changed


def arabize_source(source, root):
    translations = load_translations(root)
    changed = sum(arabize_app(app, translations) for app in source.get('apps', []))
    for app in source.get('apps', []):
        for v in app.get('versions') or []:
            if isinstance(v.get('localizedDescription'), str) and v['localizedDescription'] and not is_arabic(v['localizedDescription']):
                v['localizedDescription'] = app['localizedDescription'].split('\n', 1)[0]
    return {'arabizedApps': changed, 'translations': len(translations)}


def untranslated(source, root='.', limit=None):
    """Apps whose original text still needs an Arabic translation (for the daily task)."""
    done = load_translations(root)
    out, seen = [], set()
    for app in source.get('apps', []):
        if key(app) in done or key(app) in seen:
            continue
        original = app.get('_originalDescription') or ''
        _, prose = parse(original, app.get('name'))
        if prose and auto_translate(prose) is None:
            seen.add(key(app))
            out.append({'key': key(app), 'name': app.get('name'), 'text': prose[:1500]})
            if limit and len(out) >= limit:
                break
    return out
