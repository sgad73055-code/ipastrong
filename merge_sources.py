import json
import urllib.request
from pathlib import Path

BASE = Path("ipastrong-base.json")
OUT = Path("ipastrong.json")

SOURCES = [
    "https://repository.apptesters.org",
    "https://ipa.cypwn.xyz/cypwn.json",
    "https://apps.nabzclan.vip/repos/altstore.php",
    "https://ipa.thuthuatjb.com/repo",
    "https://repo.ethsign.fyi",
    "https://wuxu1.github.io/wuxu-complete-plus.json",
    "https://fastsign.dev/repo.json",
    "https://fastsign.dev/repo.lite.json",
]

def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ipastrong-source-merger/1.0"}
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8-sig"))

def app_key(app):
    # Prefer stable bundle IDs; fall back to AltStore IDs/names.
    for k in ("bundleIdentifier", "bundleId", "identifier", "id"):
        v = app.get(k)
        if isinstance(v, str) and v.strip():
            return k + ":" + v.strip().lower()
    name = app.get("name")
    return "name:" + str(name).strip().lower() if name else None

with BASE.open("r", encoding="utf-8") as f:
    base = json.load(f)

# Preserve ipastrong metadata and its app order.
base["name"] = "ipastrong"
apps = list(base.get("apps", []))
seen = {k for a in apps if (k := app_key(a))}

stats = []
for url in SOURCES:
    try:
        data = fetch_json(url)
        incoming = data.get("apps", []) if isinstance(data, dict) else []
        added = 0
        for app in incoming:
            if not isinstance(app, dict):
                continue
            k = app_key(app)
            if not k or k in seen:
                continue
            apps.append(app)
            seen.add(k)
            added += 1
        stats.append(f"{url} -> +{added} apps")
    except Exception as e:
        stats.append(f"{url} -> SKIPPED ({type(e).__name__}: {e})")

base["apps"] = apps

# Keep the user's own banner/news configuration.
with OUT.open("w", encoding="utf-8") as f:
    json.dump(base, f, ensure_ascii=False, indent=2)

print(f"Final app count: {len(apps)}")
for s in stats:
    print(s)
