
import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone


# =========================
# SETTINGS
# =========================

FILE = "ipastrong.json"

MAX_APPS = 9000

BACKUP_FILES = [
    "IPA-STORE.json",
    "ipa-store.json",
    "IPA-AR.json",
    "ipastrong-base.json",
]


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
# LOAD JSON FILE
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
        return " ".join(str(item) for item in value)

    return str(value).strip()


def get_bundle_id(app):
    return clean_text(
        app.get("bundleIdentifier")
        or app.get("bundleId")
        or ""
    )


def get_name(app):
    return clean_text(
        app.get("name")
        or app.get("title")
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


# =========================
# APP KEY
# =========================

def app_key(app):
    """
    يحافظ على النسخ المختلفة.

    نفس Bundle ID + نفس رابط التحميل
    = نفس التطبيق.

    إذا اختلف رابط التحميل:
    تبقى النسخة منفصلة.

    هذا يمنع دمج النسخ المعدلة
    المختلفة بالغلط.
    """

    if not isinstance(app, dict):
        return None

    bundle_id = get_bundle_id(app).lower()
    name = get_name(app).lower()
    version = get_version(app).lower()
    download_url = get_download_url(app).lower()

    # المفتاح الأساسي:
    # Bundle ID + رابط التحميل
    if bundle_id and download_url:
        return (
            "bundle:"
            + bundle_id
            + "|url:"
            + download_url
        )

    # إذا ماكو رابط تحميل
    if bundle_id:
        return (
            "bundle:"
            + bundle_id
            + "|name:"
            + name
            + "|version:"
            + version
        )

    # إذا ماكو Bundle ID
    if name and download_url:
        return (
            "name:"
            + name
            + "|url:"
            + download_url
        )

    if name:
        return (
            "name:"
            + name
            + "|version:"
            + version
        )

    return None


# =========================
# VERSION COMPARISON
# =========================

def version_numbers(version):
    """
    يحول رقم الإصدار إلى قائمة أرقام.

    1.2.3 -> [1, 2, 3]
    2.0   -> [2, 0]
    """

    if not version:
        return [0]

    numbers = []

    current_number = ""

    for character in str(version):
        if character.isdigit():
            current_number += character

        else:
            if current_number:
                numbers.append(int(current_number))
                current_number = ""

    if current_number:
        numbers.append(int(current_number))

    return numbers or [0]


def compare_versions(first, second):
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
# CHOOSE APP
# =========================

def choose_newest(existing, incoming):
    """
    إذا كانت الهوية نفسها، نختار الإصدار الأحدث.

    إذا الإصدار متساوي:
    نفضل البيانات التي تحتوي رابط تحميل.
    """

    existing_version = get_version(existing)
    incoming_version = get_version(incoming)

    comparison = compare_versions(
        incoming_version,
        existing_version
    )

    if comparison > 0:
        print(
            "Updated: "
            + get_name(incoming)
            + " "
            + incoming_version
        )

        return incoming

    if comparison < 0:
        return existing

    existing_date = get_version_date(existing)
    incoming_date = get_version_date(incoming)

    if incoming_date > existing_date:
        return incoming

    existing_url = get_download_url(existing)
    incoming_url = get_download_url(incoming)

    if incoming_url and not existing_url:
        return incoming

    return existing


# =========================
# MERGE APPS
# =========================

def merge_apps(base_apps, external_apps):
    """
    دمج آمن:

    - تطبيقاتك الأساسية أولاً.
    - النسخ المختلفة تبقى منفصلة.
    - نفس الرابط لا يتكرر.
    - الإصدارات الأحدث تحل محل القديمة
      عندما تكون الهوية نفسها.
    """

    merged = []
    positions = {}
    selected_apps = {}

    # -------------------------
    # BASE APPS
    # -------------------------

    for app in base_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if not key:
            continue

        if key not in positions:
            positions[key] = len(merged)
            selected_apps[key] = app
            merged.append(app)

        else:
            index = positions[key]

            selected = choose_newest(
                selected_apps[key],
                app
            )

            selected_apps[key] = selected
            merged[index] = selected

    # -------------------------
    # EXTERNAL APPS
    # -------------------------

    for app in external_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if not key:
            continue

        if key not in positions:
            positions[key] = len(merged)
            selected_apps[key] = app
            merged.append(app)

        else:
            index = positions[key]

            selected = choose_newest(
                selected_apps[key],
                app
            )

            selected_apps[key] = selected
            merged[index] = selected

    return merged


# =========================
# LIMIT
# =========================

def limit_apps(apps):
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
# SAVE
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
        f"Base apps collected: "
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
        f"Apps after merging: "
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
