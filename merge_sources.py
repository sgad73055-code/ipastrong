
import json
import urllib.request
import urllib.error
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
    "sourceURL": "https://raw.githubusercontent.com/sgad73055-code/ipastrong/main/ipastrong.json",
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

        if isinstance(data, dict) and isinstance(data.get("apps"), list):
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
# APPS
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

        with urllib.request.urlopen(request, timeout=30) as response:
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


# =========================
# DUPLICATE CHECK
# =========================

def app_key(app):
    if not isinstance(app, dict):
        return None

    bundle_id = (
        app.get("bundleIdentifier")
        or app.get("bundleId")
        or ""
    ).strip()

    name = str(app.get("name", "")).strip().lower()

    version = str(
        app.get("version")
        or app.get("versionName")
        or ""
    ).strip()

    download_url = (
        app.get("downloadURL")
        or app.get("ipaUrl")
        or app.get("ipaURL")
        or ""
    ).strip()

    # Different download links are treated as different app versions/mods.
    if bundle_id and download_url:
        return (
            "bundle:"
            + bundle_id.lower()
            + "|url:"
            + download_url.lower()
        )

    # If no download URL exists, include the version.
    if bundle_id:
        return (
            "bundle:"
            + bundle_id.lower()
            + "|version:"
            + version.lower()
            + "|name:"
            + name
        )

    if name and download_url:
        return (
            "name:"
            + name
            + "|url:"
            + download_url.lower()
        )

    if name:
        return "name:" + name + "|version:" + version.lower()

    return None


def merge_apps(base_apps, external_apps):
    merged = []
    seen = set()

    # Your own apps come first.
    for app in base_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if key and key not in seen:
            seen.add(key)
            merged.append(app)

    # External apps come after your own apps.
    for app in external_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if key and key not in seen:
            seen.add(key)
            merged.append(app)

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

    print(f"Your apps: {len(base_apps)}")

    external_apps = []

    for source in SOURCES:
        print(f"Loading source: {source}")

        data = fetch_json(source)

        if not data:
            continue

        apps = get_apps(data)

        print(f"Found {len(apps)} apps from source")

        external_apps.extend(apps)

    print(f"External apps collected: {len(external_apps)}")

    merged_apps = merge_apps(
        base_apps,
        external_apps
    )

    merged_apps = limit_apps(merged_apps)

    output = preserve_store_metadata(base_data)

    output["apps"] = merged_apps

    if not isinstance(output.get("news"), list):
        output["news"] = []

    if not isinstance(output.get("permissions"), list):
        output["permissions"] = []

    output["lastUpdated"] = datetime.now(
        timezone.utc
    ).isoformat()

    save_json_file(output)

    print(f"Final apps count: {len(merged_apps)}")
    print("Merge completed successfully.")


if __name__ == "__main__":
    main()
