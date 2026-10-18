#!/usr/bin/env python3
"""Inspect a public HTTPS IPA and emit JSON. Does not modify the store."""
import ipaddress
import json
import plistlib
import socket
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

MAX_BYTES = 180 * 1024 * 1024
MAX_PLIST = 2 * 1024 * 1024

def check_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A public HTTPS URL is required")
    if parsed.port not in (None, 443):
        raise ValueError("Only HTTPS port 443 is allowed")
    host = parsed.hostname
    if host.lower() in ("localhost",) or host.lower().endswith((".local", ".internal")):
        raise ValueError("Private host is not allowed")
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("Host did not resolve")
    for item in addresses:
        addr = ipaddress.ip_address(item[4][0])
        if not addr.is_global:
            raise ValueError("Non-public address is not allowed")
    return url

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def inspect(url):
    check_url(url)
    opener = urllib.request.build_opener(SafeRedirect())
    req = urllib.request.Request(url, headers={"User-Agent": "IPA-Strong-Metadata/1.0"})
    with tempfile.TemporaryDirectory() as temp:
        target = Path(temp) / "candidate.ipa"
        total = 0
        with opener.open(req, timeout=45) as response, target.open("wb") as output:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_BYTES:
                raise ValueError("IPA exceeds 180 MiB limit")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("IPA exceeds 180 MiB limit")
                output.write(chunk)
        with zipfile.ZipFile(target) as archive:
            matches = [info for info in archive.infolist()
                       if info.filename.startswith("Payload/")
                       and info.filename.count("/") == 2
                       and info.filename.endswith(".app/Info.plist")
                       and info.file_size <= MAX_PLIST]
            if len(matches) != 1:
                raise ValueError("Expected exactly one app Info.plist")
            with archive.open(matches[0]) as source:
                plist = plistlib.loads(source.read(MAX_PLIST + 1))
            def field(name):
                value = plist.get(name, "")
                return value if isinstance(value, str) else ""
            return {
                "name": field("CFBundleDisplayName") or field("CFBundleName"),
                "bundle_id": field("CFBundleIdentifier"),
                "version": field("CFBundleShortVersionString"),
                "build": field("CFBundleVersion"),
                "bytes": total,
                "status": "inspection_only",
                "note": "Not published. Signature, licensing and installation not verified."
            }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: ipa_metadata.py HTTPS_URL")
    try:
        print(json.dumps(inspect(sys.argv[1]), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"IPA inspection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
