
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
    "ipastrong-base.json",
    "IPA-STORE.json",
    "ipa-store.json",
    "IPA-AR.json",
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
    except Exception:
        return None


def load_base_data():
    for filename in BACKUP_FILES:
        path = Path(filename)

        if path.exists():
            data = load_json_file(path)

            if isinstance(data, dict):
                print(f"Using base file: {filename}")
                return data

    if Path(FILE).exists():
        data = load_json_file(FILE)

        if isinstance(data, dict):
            print(f"Using existing file: {FILE}")
            return data

    print("No base file found. Creating a new store.")
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

        return None

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
        print(f"Failed source: {url}")
        print(error)
        return None

    except Exception as error:
        print(f"Invalid source: {url}")
        print(error)
        return None


# =========================
# DUPLICATE CHECK
# =========================

def app_key(app):
    if not isinstance(app, dict):
        return None

    identifier = app.get("bundleIdentifier")

    if identifier:
        return f"id:{identifier}"

    name = app.get("name")

    if name:
        return f"name:{name.lower().strip()}"

    return None


def merge_apps(base_apps, new_apps):
    merged = []
    seen = set()

    # Base apps have priority.
    for app in base_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if key and key not in seen:
            seen.add(key)
            merged.append(app)

    # External apps are added after base apps.
    for app in new_apps:
        if not isinstance(app, dict):
            continue

        key = app_key(app)

        if key and key not in seen:
            seen.add(key)
            merged.append(app)

    return merged


# =========================
# LIMIT APPS
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
            indent=2
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

    print(f"Base apps: {len(base_apps)}")

    external_apps = []

    for source in SOURCES:
        print(f"Loading source: {source}")

        data = fetch_json(source)

        if not data:
            continue

        apps = get_apps(data)

        print(f"Found {len(apps)} apps")

        external_apps.extend(apps)

    print(f"External apps collected: {len(external_apps)}")

    merged_apps = merge_apps(
        base_apps,
        external_apps
    )

    merged_apps = limit_apps(merged_apps)

    output = preserve_store_metadata(base_data)
    output["apps"] = merged_apps

    output["news"] = output.get("news", [])
    output["permissions"] = output.get("permissions", [])

    output["lastUpdated"] = datetime.now(
        timezone.utc
    ).isoformat()

    save_json_file(output)

    print(f"Final apps count: {len(merged_apps)}")
    print("Merge completed successfully.")


if __name__ == "__main__":
    main()
