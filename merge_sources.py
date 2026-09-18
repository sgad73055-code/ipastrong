
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime


# ==========================================
# إعدادات الملفات
# ==========================================

FILE = Path("ipastrong.json")

BACKUP_FILES = [
    Path("ipastrong-base.json"),
    Path("IPA-STORE.json"),
    Path("ipa-store.json"),
    Path("IPA-AR.json"),
]


# ==========================================
# مصادر JSON
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
# معلومات المصدر الناتج
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
# قراءة JSON من ملف
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
            return json.load(file)

    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        print(
            f"Invalid JSON file skipped: "
            f"{file_path} - {error}"
        )
        return None

    except OSError as error:
        print(
            f"Could not read file: "
            f"{file_path} - {error}"
        )
        return None


# ==========================================
# تحميل الملف الأساسي
# ==========================================

def load_base_data():
    # محاولة قراءة الملف الرئيسي
    data = load_json_file(FILE)

    if isinstance(data, dict):
        print(f"Loaded base file: {FILE}")
        return data

    # إذا كان الملف الرئيسي تالفاً،
    # نجرب ملفات النسخ الاحتياطية
    for backup_file in BACKUP_FILES:
        data = load_json_file(backup_file)

        if isinstance(data, dict):
            print(
                f"Loaded backup file: "
                f"{backup_file}"
            )
            return data

    # إذا لم نجد ملفاً صالحاً،
    # نبدأ بملف فارغ
    print(
        "Warning: No valid base JSON file found."
    )

    return {
        **STORE_INFO,
        "apps": []
    }


# ==========================================
# استخراج التطبيقات من JSON
# ==========================================

def get_apps(data):
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    # الصيغة المعتادة لمصادر AltStore
    apps = data.get("apps")

    if isinstance(apps, list):
        return apps

    # بعض المصادر تستخدم data
    data_items = data.get("data")

    if isinstance(data_items, list):
        return data_items

    if isinstance(data_items, dict):
        nested_apps = data_items.get("apps")

        if isinstance(nested_apps, list):
            return nested_apps

    # بعض المصادر تستخدم items
    items = data.get("items")

    if isinstance(items, list):
        return items

    return []


# ==========================================
# جلب JSON من الإنترنت
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
        return None

    except urllib.error.URLError as error:
        print(
            f"URL error: {url} - {error.reason}"
        )
        return None

    except TimeoutError:
        print(f"Timeout: {url}")
        return None

    except json.JSONDecodeError as error:
        print(
            f"Invalid JSON from source: "
            f"{url} - {error}"
        )
        return None

    except Exception as error:
        print(
            f"Could not fetch source: "
            f"{url} - {error}"
        )
        return None


# ==========================================
# إنشاء مفتاح لمنع التكرار
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
# دمج التطبيقات بدون تكرار
# ==========================================

def merge_apps(base_apps, new_apps):
    merged = []
    existing_keys = set()

    # إضافة التطبيقات الموجودة مسبقاً
    for app in base_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if key not in existing_keys:
            existing_keys.add(key)
            merged.append(app)

    # إضافة التطبيقات الجديدة
    for app in new_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if key not in existing_keys:
            existing_keys.add(key)
            merged.append(app)

    return merged


# ==========================================
# حفظ الملف بطريقة آمنة
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

    # حماية: لا نستبدل ملفاً يحتوي على تطبيقات
    # بملف فارغ إذا فشلت كل المصادر
    if (
        len(merged_apps) == 0
        and len(base_apps) > 0
    ):
        print(
            "Update cancelled: "
            "merged result is empty"
        )
        return

    result = {
        **STORE_INFO,
        "apps": merged_apps
    }

    result["lastUpdated"] = (
        datetime.utcnow().isoformat()
        + "Z"
    )

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
        f"Saved file: {FILE}"
    )


# ==========================================
# تشغيل البرنامج
# ==========================================

if __name__ == "__main__":
    main()
