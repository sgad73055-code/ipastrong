
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone


# ==========================================
# إعدادات
# ==========================================

FILE = Path("ipastrong.json")
MAX_APPS = 12000

BACKUP_FILES = [
    Path("ipastrong-base.json"),
    Path("IPA-STORE.json"),
    Path("ipa-store.json"),
    Path("IPA-AR.json"),
]


# ==========================================
# المصادر
# ==========================================

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


# ==========================================
# معلومات المصدر
# ==========================================

STORE_INFO = {
    "name": "ipastrong",
    "identifier": "com.ipastrong.store",
    "subtitle": "IPA Store",
    "description": "Merged IPA sources",
    "website": "https://t.me/ipastrong",
    "sourceURL": (
        "https://raw.githubusercontent.com/"
        "sgad73055-code/ipastrong/main/ipastrong.json"
    ),
}


# ==========================================
# قراءة ملف JSON
# ==========================================

def load_json_file(file_path):
    try:
        if not file_path.exists():
            return None

        if file_path.stat().st_size == 0:
            return None

        with file_path.open(
            "r",
            encoding="utf-8-sig"
        ) as file:
            data = json.load(file)

        return data

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        OSError
    ) as error:
        print(
            f"Could not read JSON: "
            f"{file_path} - {error}"
        )
        return None


# ==========================================
# تحميل الملف الأساسي
# ==========================================

def load_base_data():
    data = load_json_file(FILE)

    if isinstance(data, dict):
        print(f"Loaded base file: {FILE}")
        return data

    for backup_file in BACKUP_FILES:
        data = load_json_file(backup_file)

        if isinstance(data, dict):
            print(
                f"Loaded backup file: "
                f"{backup_file}"
            )
            return data

    print(
        "Warning: No valid base JSON file found."
    )

    return {
        **STORE_INFO,
        "apps": []
    }


# ==========================================
# استخراج التطبيقات
# ==========================================

def get_apps(data):
    if isinstance(data, list):
        return [
            app for app in data
            if isinstance(app, dict)
        ]

    if not isinstance(data, dict):
        return []

    apps = data.get("apps")

    if isinstance(apps, list):
        return [
            app for app in apps
            if isinstance(app, dict)
        ]

    data_items = data.get("data")

    if isinstance(data_items, list):
        return [
            app for app in data_items
            if isinstance(app, dict)
        ]

    if isinstance(data_items, dict):
        nested_apps = data_items.get("apps")

        if isinstance(nested_apps, list):
            return [
                app for app in nested_apps
                if isinstance(app, dict)
            ]

    items = data.get("items")

    if isinstance(items, list):
        return [
            app for app in items
            if isinstance(app, dict)
        ]

    return []


# ==========================================
# جلب المصادر
# ==========================================

def fetch_json(url):
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "ipastrong-source-updater"
                ),
                "Accept": "application/json"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            content = response.read()

            if not content:
                print(f"Empty response: {url}")
                return None

            text = content.decode(
                "utf-8-sig",
                errors="replace"
            )

            return json.loads(text)

    except urllib.error.HTTPError as error:
        print(
            f"HTTP error {error.code}: {url}"
        )

    except urllib.error.URLError as error:
        print(
            f"URL error: {url} - {error.reason}"
        )

    except TimeoutError:
        print(f"Timeout: {url}")

    except json.JSONDecodeError as error:
        print(
            f"Invalid JSON: {url} - {error}"
        )

    except Exception as error:
        print(
            f"Could not fetch source: "
            f"{url} - {error}"
        )

    return None


# ==========================================
# مفتاح منع التكرار
# ==========================================

def app_key(app):
    try:
        return json.dumps(
            app,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":")
        )

    except (TypeError, ValueError):
        return str(app)


# ==========================================
# الدمج بدون حذف التطبيقات المختلفة
# ==========================================

def merge_apps(base_apps, new_apps):
    merged = []
    existing_keys = set()

    for app in base_apps + new_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if key not in existing_keys:
            existing_keys.add(key)
            merged.append(app)

    return merged


# ==========================================
# تحديد العدد
# ==========================================

def limit_apps(apps):
    if len(apps) <= MAX_APPS:
        return apps

    print(
        f"Limiting applications from "
        f"{len(apps)} to {MAX_APPS}"
    )

    return apps[:MAX_APPS]


# ==========================================
# الحفاظ على معلومات الإعلانات
# ==========================================

def preserve_store_metadata(base_data):
    """
    الحفاظ على معلومات المصدر القديمة،
    مثل صورة الإعلان والأخبار.

    يتم الاحتفاظ بكل الحقول القديمة
    ما عدا apps و lastUpdated.
    """

    if not isinstance(base_data, dict):
        return {}

    metadata = {}

    for key, value in base_data.items():
        if key not in [
            "apps",
            "lastUpdated"
        ]:
            metadata[key] = value

    return metadata


# ==========================================
# حفظ آمن
# ==========================================

def save_json_file(file_path, data):
    temporary_file = file_path.with_suffix(
        ".tmp.json"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

        file.write("\n")

    temporary_file.replace(file_path)


# ==========================================
# البرنامج الرئيسي
# ==========================================

def main():
    print("=" * 50)
    print("Starting ipastrong source updater")
    print("=" * 50)

    base_data = load_base_data()

    base_apps = get_apps(base_data)

    print(
        f"Base applications: "
        f"{len(base_apps)}"
    )

    all_apps = []

    successful_sources = 0
    failed_sources = 0

    for index, url in enumerate(
        SOURCES,
        start=1
    ):

        print()
        print(
            f"[{index}/{len(SOURCES)}] "
            f"Fetching: {url}"
        )

        source_data = fetch_json(url)

        if source_data is None:
            failed_sources += 1
            print("Source failed")
            continue

        source_apps = get_apps(source_data)

        if not source_apps:
            print(
                "Source loaded, "
                "but no applications found"
            )
            successful_sources += 1
            continue

        all_apps.extend(source_apps)

        successful_sources += 1

        print(
            f"Applications received: "
            f"{len(source_apps)}"
        )

    print()
    print("=" * 50)
    print("Merging applications")
    print("=" * 50)

    merged_apps = merge_apps(
        base_apps,
        all_apps
    )

    if (
        len(merged_apps) == 0
        and len(base_apps) > 0
    ):
        print(
            "Update cancelled: "
            "merged result is empty"
        )
        return

    merged_apps = limit_apps(
        merged_apps
    )

    # ======================================
    # إنشاء النتيجة مع الحفاظ على الإعلانات
    # ======================================

    old_metadata = preserve_store_metadata(
        base_data
    )

    result = {
        **old_metadata,
        **STORE_INFO,
        "apps": merged_apps,
        "lastUpdated": (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    }

    # ======================================
    # التحقق قبل الحفظ
    # ======================================

    if not isinstance(
        result.get("apps"),
        list
    ):
        print(
            "Update cancelled: "
            "apps is not a list"
        )
        return

    if len(result["apps"]) == 0:
        print(
            "Update cancelled: "
            "no applications available"
        )
        return

    save_json_file(
        FILE,
        result
    )

    print()
    print("=" * 50)
    print("Update completed successfully")
    print("=" * 50)

    print(
        f"Base applications: "
        f"{len(base_apps)}"
    )

    print(
        f"Fetched applications: "
        f"{len(all_apps)}"
    )

    print(
        f"Final applications: "
        f"{len(merged_apps)}"
    )

    print(
        f"Successful sources: "
        f"{successful_sources}"
    )

    print(
        f"Failed sources: "
        f"{failed_sources}"
    )

    print(
        f"Maximum applications: "
        f"{MAX_APPS}"
    )

    print(
        "Advertisement metadata preserved "
        "when available."
    )

    print(
        f"Saved file: {FILE}"
    )


# ==========================================
# التشغيل
# ==========================================

if __name__ == "__main__":
    main()
