#!/usr/bin/env python3
"""Read-only IPA metadata inspection for trusted test URLs; no catalog writes."""
import json
import plistlib
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

MAX_BYTES = 180 * 1024 * 1024
MAX_PLIST = 2 * 1024 * 1024

def inspect(url):
    req = urllib.request.Request(url, headers={"User-Agent": "IPA-Strong-Metadata/1.0"})
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "candidate.ipa"
        total = 0
        with urllib.request.urlopen(req, timeout=45) as response, target.open("wb") as output:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > MAX_BYTES:
                raise ValueError("File exceeds size limit")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("File exceeds size limit")
                output.write(chunk)
        with zipfile.ZipFile(target) as archive:
            matches = [item for item in archive.infolist()
                       if item.filename.startswith("Payload/")
                       and item.filename.count("/") == 2
                       and item.filename.endswith(".app/Info.plist")
                       and item.file_size <= MAX_PLIST]
            if len(matches) != 1:
                raise ValueError("Expected exactly one Payload/*.app/Info.plist")
            with archive.open(matches[0]) as file:
                plist = plistlib.loads(file.read(MAX_PLIST + 1))
            def value(key):
                item = plist.get(key, "")
                return item if isinstance(item, str) else ""
            return {"bytes": total, "name": value("CFBundleDisplayName") or value("CFBundleName"),
                    "bundle_id": value("CFBundleIdentifier"),
                    "version": value("CFBundleShortVersionString"),
                    "build": value("CFBundleVersion"),
                    "note": "Metadata only; does not verify signature, licensing or device installation."}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: ipa_metadata.py URL")
    try:
        print(json.dumps(inspect(sys.argv[1]), ensure_ascii=False))
    except Exception as error:
        print(f"Inspection failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
