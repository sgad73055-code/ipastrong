#!/usr/bin/env python3
"""Read-only bounded IPA URL probe; does not download full IPA or change catalogs."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

def inspect(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Expected public HTTPS URL without credentials")
    request = urllib.request.Request(url, headers={
        "Range": "bytes=0-3",
        "User-Agent": "IPA-Strong-Preflight/1.0",
        "Accept-Encoding": "identity",
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            magic = response.read(4)
            is_zip = magic in (b"PK\\x03\\x04", b"PK\\x05\\x06", b"PK\\x07\\x08")
            return {"result": "zip_header" if is_zip else "not_zip_header",
                    "http": response.status, "content_type": response.headers.get("Content-Type", ""),
                    "content_range": response.headers.get("Content-Range", ""),
                    "note": "ZIP signature alone does not prove installability or signing"}
    except urllib.error.HTTPError as error:
        return {"result": "http_error", "http": error.code}
    except (urllib.error.URLError, TimeoutError) as error:
        return {"result": "network_unavailable", "error": type(error).__name__}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 tools/ipa_url_preflight.py https://example.com/file.ipa")
    print(json.dumps(inspect(sys.argv[1]), ensure_ascii=False))
