
import json
import urllib.request
from pathlib import Path

FILE = Path("ipastrong.json")

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
]

def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ipastrong-source-merger"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8-sig"))

def get_apps(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("apps", "data", "items"):
            if isinstance(data.get(key), list):
                return data[key]

    return []

def app_key(app):
    return json.dumps(
        app,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":")
    )

with FILE.open("r", encoding="utf-8") as file:
    result = json.load(file)

apps = result.get("apps", [])
seen = {
    app_key(app)
    for app in apps
    if isinstance(app, dict)
}

for url in dict.fromkeys(SOURCES):
    try:
        data = fetch_json(url)

        for app in get_apps(data):
            if not isinstance(app, dict):
                continue

            key = app_key(app)

            if key not in seen:
                apps.append(app)
                seen.add(key)

        print("Completed:", url)

    except Exception as error:
        print("Skipped:", url, error)

result["name"] = "ipastrong"
result["apps"] = apps

with FILE.open("w", encoding="utf-8") as file:
    json.dump(result, file, ensure_ascii=False, indent=2)

print("Total apps:", len(apps))
