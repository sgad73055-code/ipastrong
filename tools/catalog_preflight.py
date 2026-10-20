#!/usr/bin/env python3
"""Read-only catalog preflight for IPA Strong. Never writes source files."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("IPA-STORE.json", "ipastrong.json")

def check(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("apps"), list):
        raise ValueError("Missing apps array")
    apps = raw["apps"]
    missing = []
    duplicate_urls = []
    urls = Counter()
    for index, app in enumerate(apps):
        if not isinstance(app, dict):
            missing.append(index)
            continue
        if not app.get("name") or not (app.get("bundleIdentifier") or app.get("bundleId")):
            missing.append(index)
        url = app.get("downloadURL")
        if isinstance(url, str) and url:
            urls[url] += 1
    duplicate_urls = sum(count - 1 for count in urls.values() if count > 1)
    return {"file": path.name, "apps": len(apps), "missing_identity": len(missing),
            "reused_download_urls": duplicate_urls, "bytes": path.stat().st_size}

def main():
    for filename in FILES:
        path = ROOT / filename
        if not path.exists():
            print(f"{filename}: NOT FOUND")
            continue
        try:
            print(json.dumps(check(path), ensure_ascii=False))
        except (ValueError, UnicodeError, OSError) as exc:
            print(f"{filename}: ERROR: {exc}", file=sys.stderr)
            return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
