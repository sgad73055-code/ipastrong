"""IPA Strong merger. Python standard library only."""
import argparse, copy, json, re, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urljoin

SOURCES = ['https://repository.apptesters.org', 'https://ipa.cypwn.xyz/cypwn.json', 'https://wuxu1.github.io/wuxu-complete.json', 'https://wuxu1.github.io/wuxu-complete-plus.json', 'https://repo.ikghd.me/repo.json', 'https://check0ver.site/repo.json', 'https://quarksources.github.io/dist/quantumsource%2B%2B.min.json', 'https://cdn.altstore.io/file/altstore/apps.json', 'https://alts.lao.sb/source.json', 'https://apps.nabzclan.vip/repos/altstore.php', 'https://ipa.thuthuatjb.com/repo', 'https://repo.ethsign.fyi', 'https://fastsign.dev/repo.json']
OUTPUT = Path("ipastrong.json")
BLOCKLIST = Path(__file__).with_name("excluded-downloads.json")
BLOCKED = set(json.loads(BLOCKLIST.read_text()).get("urls", [])) if BLOCKLIST.exists() else set()
CURATED_FILE = Path(__file__).with_name("curated-sources.json")
CURATED = json.loads(CURATED_FILE.read_text()).get("sources", {}) if CURATED_FILE.exists() else {}
SOURCES = list(dict.fromkeys(SOURCES + list(CURATED)))
SOURCES = list(dict.fromkeys(SOURCES + ['https://raw.githubusercontent.com/927tx/IPA-Vault/refs/heads/main/ipavaultsource.json']))

def text(value):
    return str(value or "").strip()

def url(value, source):
    value = text(value)
    if not value:
        return ""
    value = urljoin(source, value)
    return value if urlsplit(value).scheme in ("http", "https") and urlsplit(value).netloc else ""

def version_key(v):
    numbers = [int(n) for n in re.findall(r"\d+", text(v))][:12]
    return tuple(numbers + [0] * (12 - len(numbers)))

def date_key(v):
    try:
        parsed = datetime.fromisoformat(text(v).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (ValueError, OverflowError):
        return 0

def normalize(raw, source):
    if not isinstance(raw, dict):
        return None
    app = copy.deepcopy(raw)
    primary_url = url(app.get("downloadURL") or app.get("ipaUrl") or app.get("down"), source)
    if primary_url in BLOCKED:
        return None
    name = text(app.get("name") or app.get("title"))
    bundle = text(app.get("bundleIdentifier") or app.get("bundleId") or app.get("bundleID") or app.get("bundleid"))
    if not name or not bundle:
        return None
    versions = []
    candidates = app.get("versions", [])
    if not isinstance(candidates, list):
        candidates = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        item = copy.deepcopy(item)
        link = url(item.get("downloadURL") or item.get("ipaUrl") or item.get("down"), source)
        if link and link not in BLOCKED and text(item.get("version")):
            item["downloadURL"] = link
            item["date"] = text(item.get("date") or item.get("versionDate"))
            versions.append(item)
    link = url(app.get("downloadURL") or app.get("ipaUrl") or app.get("ipaURL") or app.get("downloadUrl") or app.get("down"), source)
    if link and link not in BLOCKED and text(app.get("version")):
        current = {"version": text(app["version"]), "downloadURL": link,
                   "date": text(app.get("versionDate") or app.get("date")), "size": app.get("size", 0)}
        for field in ("minOSVersion", "maxOSVersion", "sha256", "absoluteVersion"):
            if field in app:
                current[field] = app[field]
        # Keep the richer upstream entry when URL and version already match.
        if not any(v["downloadURL"] == link and v["version"] == current["version"] and date_key(v.get("date")) for v in versions):
            versions.append(current)
    # Strict source readers require a real date and an integer size on every version.
    valid_versions = []
    for item in versions:
        item["version"] = text(item.get("version"))
        item["date"] = text(item.get("date"))
        if not date_key(item["date"]):
            continue
        try:
            item["size"] = max(0, int(item.get("size") or 0))
        except (ValueError, TypeError):
            item["size"] = 0
        valid_versions.append(item)
    versions = valid_versions
    if not versions:
        return None
    versions.sort(key=lambda v: (date_key(v.get("date")), version_key(v.get("version"))), reverse=True)
    unique = {}
    for v in versions:
        unique.setdefault((v["version"], v["downloadURL"]), v)
    versions = list(unique.values())
    latest = versions[0]
    app.update(name=name, bundleIdentifier=bundle, version=latest["version"],
               versionDate=latest.get("date", ""), downloadURL=latest["downloadURL"],
               versions=versions, _sourceURL=source)
    for field in ("minOSVersion", "maxOSVersion", "sha256", "absoluteVersion"):
        app.pop(field, None)
        if field in latest:
            app[field] = latest[field]
    try:
        app["size"] = max(0, int(latest.get("size", 0)))
    except (ValueError, TypeError):
        app["size"] = 0
    app["iconURL"] = url(app.get("iconURL") or app.get("icon"), source)
    app["localizedDescription"] = text(app.get("localizedDescription") or app.get("description"))
    # Synchronize legacy fields consumed by existing storefronts.
    for field in ("ipaUrl", "ipaURL", "downloadUrl", "down"):
        if field in app:
            app[field] = app["downloadURL"]
    return app

def identity(app):
    source = app.get("_sourceURL", "")
    name = app["name"].casefold()
    # CyPwn embeds the app version in some display names.
    if "cypwn" in source:
        name = re.sub(r"[-_ ]v?" + re.escape(app["version"]) + r"$", "", name)
    variant = app["localizedDescription"].casefold() if "apptesters" in source else ""
    return source, app["bundleIdentifier"].casefold(), name, variant, text(app.get("developerName")).casefold()

def merge(records):
    groups = {}
    rejected = 0
    for raw, source in records:
        app = normalize(raw, source)
        if app is None:
            rejected += 1
            continue
        key = identity(app)
        if key not in groups:
            groups[key] = app
            continue
        old = groups[key]
        winner = max((old, app), key=lambda a: (date_key(a["versionDate"]), version_key(a["version"])))
        combined = copy.deepcopy(winner)
        combined["versions"] = old["versions"] + app["versions"]
        groups[key] = normalize(combined, source)
    result = []
    for app in groups.values():
        app["versions"] = app["versions"][:20]
        result.append(app)
    result.sort(key=lambda a: (a.get("_sourceURL") != "local", -date_key(a["versionDate"]), a["name"].casefold()))
    return result, rejected

def selection_key(app):
    return app["bundleIdentifier"].casefold() + "|" + app["name"].casefold()

def filter_curated(apps, source):
    if source not in CURATED:
        return apps
    allowed = set(CURATED[source])
    return [raw for raw in apps if (app := normalize(raw, source)) is not None and selection_key(app) in allowed]

def fetch(source):
    try:
        request = urllib.request.Request(source, headers={"User-Agent": "IPA-Strong/2.0"})
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
        apps = data.get("apps") if isinstance(data, dict) else data
        if not isinstance(apps, list) or not apps or not any(normalize(a, source) for a in apps):
            raise ValueError("Source returned no usable apps")
        return source, apps, None
    except Exception as error:
        return source, None, str(error)

def build(base, responses):
    records, status = [], []
    filtered = []
    for source, apps, error in responses:
        if apps is not None and source in CURATED:
            apps = filter_curated(apps, source)
            if not apps:
                apps, error = None, "Selected apps unavailable; retaining previous entries"
        filtered.append((source, apps, error))
    responses = filtered
    successful = {source for source, apps, error in responses if apps is not None}
    for app in base.get("apps", []):
        if isinstance(app, dict) and app.get("_expandedSocial"):
            continue
        if not isinstance(app, dict):
            continue
        source = app.get("_sourceURL", "local")
        # Migrate old imported AppTesters records to their canonical source.
        if "github.com/apptesters-org/" in text(app.get("downloadURL")):
            source = SOURCES[0]
        if source not in successful:
            records.append((app, source))
    for source, apps, error in responses:
        status.append({"source": source, "apps": len(apps or []), "error": error})
        records.extend((app, source) for app in (apps or []))
    apps, rejected = merge(records)
    if not apps:
        raise ValueError("Refusing to replace source with an empty result")
    output = copy.deepcopy(base)
    # Put selected additions ahead of the large imported catalog, after owner entries.
    for app in apps:
        if app.get("_sourceURL") in CURATED:
            app["_featured"] = True
    # A mirrored download is the same package. Keep owner metadata first, then curated metadata.
    apps.sort(key=lambda a: (a.get("_sourceURL") != "local", not a.get("_featured", False), -date_key(a["versionDate"]), a["name"].casefold()))
    unique = {}
    for app in apps:
        key = (app["bundleIdentifier"].casefold(), app["downloadURL"])
        if key not in unique:
            unique[key] = app
        elif app.get("_featured"):
            unique[key]["_featured"] = True
    apps = list(unique.values())
    apps = expand_social(apps)
    output["apps"] = apps
    output["iconURL"] = 'https://raw.githubusercontent.com/sgad73055-code/ipastrong/main/source-icon.jpeg'
    metadata = output.get("META")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["repoName"] = output["name"]
    metadata["repoIcon"] = output["iconURL"]
    output["META"] = metadata
    output["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    return output, {"sources": status, "inputRecords": len(records), "outputApps": len(apps), "rejectedRecords": rejected}

def social_kind(app):
    name = text(app.get("name"))
    if re.search(r"tiktok|tik tok", name, re.I):
        return "tiktok"
    if re.search(r"instagram|^insta|regram|igrocket|ryukgram|ريكرام|بيكرام", name, re.I) and not re.search(r"reels maker|followers|unfollowers|tracker|analytics|install", name, re.I):
        return "instagram"
    return None

def expand_social(apps, limit_per_kind=60):
    # Keep the true bundle ID. Only expose genuine upstream release URLs.
    existing = {a["downloadURL"] for a in apps}
    candidates = []
    for app in apps:
        kind = social_kind(app)
        if kind is None or app.get("_expandedSocial"):
            continue
        for version in app.get("versions", [])[1:]:
            if version.get("downloadURL") in existing or date_key(version.get("date")) < date_key("2024-01-01"):
                continue
            candidates.append((date_key(version.get("date")), kind, app, version))
    candidates.sort(key=lambda entry: entry[0], reverse=True)
    counts = {"instagram": 0, "tiktok": 0}
    additions = []
    for _, kind, parent, release in candidates:
        link = release["downloadURL"]
        if link in existing or counts[kind] >= limit_per_kind:
            continue
        clone = copy.deepcopy(parent)
        clone["name"] = parent["name"] + " — " + text(release["version"])
        clone["versions"] = [copy.deepcopy(release)]
        clone["version"] = text(release["version"])
        clone["versionDate"] = release["date"]
        clone["downloadURL"] = link
        clone["size"] = release.get("size", 0)
        for field in ("minOSVersion", "maxOSVersion", "sha256", "absoluteVersion"):
            clone.pop(field, None)
            if field in release:
                clone[field] = release[field]
        for field in ("id", "_rowKey", "fullDate", "addedAt", "updatedAt"):
            clone.pop(field, None)
        for field in ("ipaUrl", "ipaURL", "downloadUrl", "down"):
            if field in clone:
                clone[field] = link
        clone["_expandedSocial"] = True
        additions.append(clone)
        existing.add(link)
        counts[kind] += 1
    output = apps + additions
    output.sort(key=lambda a: (social_kind(a) is None, -date_key(a.get("versionDate")), a["name"].casefold()))
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-dir", type=Path, help="Directory containing snapshots named 0.json, 1.json, etc. in SOURCES order")
    args = parser.parse_args()
    base = json.loads(OUTPUT.read_text(encoding="utf-8"))
    if args.offline_dir:
        responses = []
        for i, source in enumerate(SOURCES):
            path = args.offline_dir / (str(i) + ".json")
            responses.append((source, json.loads(path.read_text()).get("apps", []), None) if path.exists() else (source, None, "Snapshot unavailable"))
    else:
        with ThreadPoolExecutor(max_workers=6) as pool:
            responses = list(pool.map(fetch, SOURCES))
    output, report = build(base, responses)
    temp = OUTPUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(OUTPUT)
    Path("merge-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))

if __name__ == "__main__":
    main()
