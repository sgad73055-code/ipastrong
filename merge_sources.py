
import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
import re


# =========================
# SETTINGS
# =========================

FILE = "ipastrong.json"

# الحد الأقصى للتطبيقات
MAX_APPS = 9000

# ملفات التطبيقات الخاصة بك
BACKUP_FILES = [
    "IPA-STORE.json",
    "ipa-store.json",
    "IPA-AR.json",
    "ipastrong-base.json",
]

# المصادر الخارجية
SOURCES = [
    "https://repository.apptesters.org",
    "https://repo.apptesters.org",
    "https://ipa.cypwn.xyz/cypwn.json",
    "https://wuxu1.github.io/wuxu-complete.json",
    "https://wuxu1.github.io/wuxu-complete-plus.json",
    "https://repo.ikghd.me/repo.json",
    "https://check0ver.site/repo.json",
    "https://quarksources.github.io/dist/quantumsource%2B%2B.min.json",
    "https://cdn.altstore.io/file/altstore/apps.json",
    "https://alts.lao.sb/source.json",
    "https://apps.nabzclan.vip/repos/altstore.php",
    "https://ipa.thuthuatjb.com/repo",
    "https://repo.ethsign.fyi",
    "https://fastsign.dev/repo.json",
    "https://fastsign.dev/repo.lite.json",
]


STORE_INFO = {
    "name": "ipastrong",
    "identifier": "com.ipastrong.store",
    "subtitle": "ipastrong",
    "description": "Merged IPA sources",
    "website": "https://t.me/ipastrong",
    "sourceURL": (
        "https://raw.githubusercontent.com/"
        "sgad73055-code/ipastrong/main/ipastrong.json"
    ),
}


# =========================
# LOAD JSON
# =========================

def load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception as error:
        print(f"Could not read {path}: {error}")
        return None


def load_base_data():
    for filename in BACKUP_FILES:
        path = Path(filename)

        if not path.exists():
            continue

        data = load_json_file(path)

        if (
            isinstance(data, dict)
            and isinstance(data.get("apps"), list)
        ):
            print(f"Using base file: {filename}")
            return data

    if Path(FILE).exists():
        data = load_json_file(FILE)

        if isinstance(data, dict):
            print(f"Using existing file: {FILE}")
            return data

    print("No valid base file found.")

    return dict(STORE_INFO)


# =========================
# APP HELPERS
# =========================

def get_apps(data):
    if not isinstance(data, dict):
        return []

    apps = data.get("apps", [])

    if isinstance(apps, list):
        return apps

    return []


def fetch_json(url):
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:
            content = response.read().decode("utf-8")

        data = json.loads(content)

        if isinstance(data, dict):
            return data

        print(f"Invalid data format: {url}")
        return None

    except Exception as error:
        print(f"Failed source: {url}")
        print(error)
        return None


def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(item) for item in value)

    return str(value).strip()


def get_name(app):
    return clean_text(
        app.get("name")
        or app.get("title")
        or ""
    )


def get_bundle_id(app):
    return clean_text(
        app.get("bundleIdentifier")
        or app.get("bundleId")
        or ""
    )


def get_version(app):
    return clean_text(
        app.get("version")
        or app.get("versionName")
        or app.get("currentVersion")
        or ""
    )


def get_download_url(app):
    return clean_text(
        app.get("downloadURL")
        or app.get("ipaUrl")
        or app.get("ipaURL")
        or app.get("downloadUrl")
        or ""
    )


def get_version_date(app):
    return clean_text(
        app.get("versionDate")
        or app.get("date")
        or app.get("updatedDate")
        or app.get("lastUpdated")
        or ""
    )


def get_description(app):
    return clean_text(
        app.get("subtitle")
        or app.get("description")
        or app.get("localizedDescription")
        or ""
    )


# =========================
# VERSION COMPARISON
# =========================

def version_numbers(version):
    """
    يحول رقم الإصدار إلى أرقام قابلة للمقارنة.

    أمثلة:
    1.2.3       -> [1, 2, 3]
    2.0         -> [2, 0]
    v3.1.4      -> [3, 1, 4]
    """

    if not version:
        return [0]

    numbers = re.findall(r"\d+", str(version))

    if not numbers:
        return [0]

    try:
        return [int(number) for number in numbers]

    except Exception:
        return [0]


def compare_versions(first, second):
    """
    يرجع:
    1  إذا first أحدث
    -1 إذا second أحدث
    0  إذا متساويين
    """

    first_numbers = version_numbers(first)
    second_numbers = version_numbers(second)

    max_length = max(
        len(first_numbers),
        len(second_numbers)
    )

    first_numbers += [0] * (
        max_length - len(first_numbers)
    )

    second_numbers += [0] * (
        max_length - len(second_numbers)
    )

    if first_numbers > second_numbers:
        return 1

    if first_numbers < second_numbers:
        return -1

    return 0


# =========================
# APP IDENTITY
# =========================

def normalize_name(name):
    """
    ينظف اسم التطبيق حتى نقدر نعرف
    إذا كان التطبيق نفسه أو إصدار جديد.

    لا نحذف علامات ++ حتى تبقى
    النسخ المعدلة المختلفة محفوظة.
    """

    name = clean_text(name).lower()

    name = re.sub(
        r"\bversion\s*[\d.]+\b",
        "",
        name
    )

    name = re.sub(
        r"\bv?\d+(?:\.\d+)+\b",
        "",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name.strip()


def get_variant_name(app):
    """
    يفرق بين النسخة العادية والمعدلة
    إذا كان اسم النسخة مختلفاً.

    مثال:
    Instagram
    Instagram++
    Instagram Rocket

    تبقى نسخ منفصلة إذا اختلف اسمها.
    """

    name = normalize_name(get_name(app))

    if name:
        return name

    return "unknown-app"


def get_source_host(download_url):
    """
    يأخذ اسم الموقع من رابط التحميل.
    يستخدم كمعلومة مساعدة فقط.
    """

    if not download_url:
        return ""

    try:
        parsed = urlparse(download_url)
        return parsed.netloc.lower()

    except Exception:
        return ""


def app_identity(app):
    """
    هوية التطبيق التي نستخدمها للتحديث.

    إذا توفر Bundle ID:
      Bundle ID + اسم النسخة

    إذا ما توفر:
      اسم النسخة + اسم التطبيق

    رابط التحميل لا يدخل في الهوية،
    لأن الرابط قد يتغير عند تحديث التطبيق.
    """

    bundle_id = get_bundle_id(app)
    variant_name = get_variant_name(app)

    if bundle_id:
        return (
            "bundle:"
            + bundle_id.lower()
            + "|variant:"
            + variant_name
        )

    if variant_name:
        return "name:" + variant_name

    return None


# =========================
# SELECT NEWEST APP
# =========================

def choose_newest(existing, incoming):
    """
    يختار الإصدار الأحدث بين تطبيقين
    لهما الهوية نفسها.

    إذا كان الإصداران متساويين:
    نفضل التطبيق الوارد حديثاً إذا
    كان يحتوي على رابط تحميل أفضل.
    """

    existing_version = get_version(existing)
    incoming_version = get_version(incoming)

    comparison = compare_versions(
        incoming_version,
        existing_version
    )

    if comparison > 0:
        print(
            "Updated app: "
            + get_name(incoming)
            + " "
            + incoming_version
        )

        return incoming

    if comparison < 0:
        return existing

    existing_url = get_download_url(existing)
    incoming_url = get_download_url(incoming)

    if incoming_url and not existing_url:
        return incoming

    existing_date = get_version_date(existing)
    incoming_date = get_version_date(incoming)

    if incoming_date > existing_date:
        return incoming

    return existing


# =========================
# MERGE APPS
# =========================

def merge_apps(base_apps, external_apps):
    """
    يدمج التطبيقات مع تحديث الإصدارات.

    تطبيقاتك الأساسية لها الأولوية
    عند وجود تطبيق مطابق.

    النسخ المعدلة ذات الاسم المختلف
    تبقى منفصلة.
    """

    merged = []
    positions = {}
    identities = {}

    # -------------------------
    # ADD BASE APPS FIRST
    # -------------------------

    for app in base_apps:
        if not isinstance(app, dict):
            continue

        identity = app_identity(app)

        if not identity:
            continue

        if identity not in positions:
            positions[identity] = len(merged)
            identities[identity] = app
            merged.append(app)

        else:
            index = positions[identity]

            identities[identity] = choose_newest(
                identities[identity],
                app
            )

            merged[index] = identities[identity]

    # -------------------------
    # ADD EXTERNAL APPS
    # -------------------------

    for app in external_apps:
        if not isinstance(app, dict):
            continue

        identity = app_identity(app)

        if not identity:
            continue

        if identity not in positions:
            positions[identity] = len(merged)
            identities[identity] = app
            merged.append(app)

        else:
            index = positions[identity]

            selected = choose_newest(
                identities[identity],
                app
            )

            identities[identity] = selected
            merged[index] = selected

    return merged


# =========================
# LIMIT APPS
# =========================

def limit_apps(apps):
    """
    يحافظ على الحد الأقصى.
    """

    return apps[:MAX_APPS]


# =========================
# STORE METADATA
# =========================

def preserve_store_metadata(data):
    result = {}

    if isinstance(data, dict):
        result.update(data)

    for key, value in STORE_INFO.items():
        result[key] = value

    return result


# =========================
# SAVE JSON
# =========================

def save_json_file(data):
    with open(FILE, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        )

    print(f"Saved {FILE}")


# =========================
# MAIN
# =========================

def main():
    print("Starting IPA source merger...")
    print(f"Maximum apps: {MAX_APPS}")

    base_data = load_base_data()
    base_apps = get_apps(base_data)

    print(
        f"Your apps before update: "
        f"{len(base_apps)}"
    )

    external_apps = []

    for source in SOURCES:
        print(f"Loading source: {source}")

        data = fetch_json(source)

        if not data:
            continue

        apps = get_apps(data)

        print(
            f"Found {len(apps)} apps from source"
        )

        external_apps.extend(apps)

    print(
        f"External apps collected: "
        f"{len(external_apps)}"
    )

    merged_apps = merge_apps(
        base_apps,
        external_apps
    )

    print(
        f"Apps after merging and updates: "
        f"{len(merged_apps)}"
    )

    merged_apps = limit_apps(merged_apps)

    output = preserve_store_metadata(base_data)

    output["apps"] = merged_apps

    if not isinstance(
        output.get("news"),
        list
    ):
        output["news"] = []

    if not isinstance(
        output.get("permissions"),
        list
    ):
        output["permissions"] = []

    output["lastUpdated"] = datetime.now(
        timezone.utc
    ).isoformat()

    save_json_file(output)

    print(
        f"Final apps count: "
        f"{len(merged_apps)}"
    )

    print("Merge completed successfully.")


if __name__ == "__main__":
    main()
