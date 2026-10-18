#!/usr/bin/env python3
"""Read-only bounded IPA link check. Never modifies catalogs."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

ZIP_HEADERS = (bytes.fromhex("504b0304"), bytes.fromhex("504b0506"), bytes.fromhex("504b0708"))

def inspect(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Expected HTTPS URL without credentials")
    request = urllib.request.Request(url, headers={
        "Range": "bytes=0-3",
        "User-Agent": "IPA-Strong-Preflight/1.1",
        "Accept-Encoding": "identity",
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            magic = response.read(4)
            result = {
                "http": response.status,
                "header_hex": magic.hex(),
                "content_type": response.headers.get("Content-Type", ""),
                "content_range": response.headers.get("Content-Range", ""),
                "result": "zip_header" if magic in ZIP_HEADERS else "unrecognized_header",
                "note": "This checks only the header, not IPA structure, signature or installation.",
            }
            return result, magic in ZIP_HEADERS
    except urllib.error.HTTPError as error:
        return {"result": "http_error", "http": error.code}, False
    except (urllib.error.URLError, TimeoutError) as error:
        return {"result": "network_unavailable", "error": type(error).__name__}, False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 tools/ipa_url_preflight.py https://example.com/file.ipa")
    result, passed = inspect(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if passed else 1)
