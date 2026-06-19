"""Download CMS images and rewrite URLs to local paths."""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests

from util import DATA_DIR, IMAGES_CMS, ROOT, clean_text

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "superteam-cms-build/1.0"})

WEBFLOW_HOSTS = (
    "uploads-ssl.webflow.com",
    "cdn.prod.website-files.com",
    "assets.website-files.com",
)

IMAGE_COLLECTIONS = {
    "projects": "projects",
    "bounties": "bounties",
    "missions": "missions",
    "instagrants": "instagrants",
}

IMG_SRC_RE = re.compile(
    r'(<img\b[^>]*\bsrc=["\'])([^"\']+)(["\'])',
    re.IGNORECASE,
)

URL_IN_TEXT_RE = re.compile(
    r"https?://[^\s\"'<>]+",
    re.IGNORECASE,
)

AUDIT_PATTERNS = (
    "uploads-ssl.webflow.com",
    "cdn.prod.website-files.com",
    "assets.website-files.com",
    "d3e54v103j8qbb.cloudfront.net",
)


def is_webflow_asset_url(url: str) -> bool:
    url = clean_text(url)
    if not url.startswith("http"):
        return False
    host = urlparse(url).netloc.lower()
    return any(h in host for h in WEBFLOW_HOSTS)


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = Path(path).name or "image"
    if not Path(name).suffix:
        name += ".bin"
    return name


def mirror_url(url: str, dest_dir: Path) -> str | None:
    return download_image(url, dest_dir)


def download_image(url: str, dest_dir: Path) -> str | None:
    url = clean_text(url)
    if not url or not url.startswith("http"):
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _filename_from_url(url)
    dest = dest_dir / filename
    if dest.exists() and dest.stat().st_size > 0:
        return str(dest.relative_to(ROOT)).replace("\\", "/")
    try:
        resp = SESSION.get(url, timeout=60)
        resp.raise_for_status()
        content = resp.content
        if not content:
            return None
        if len(content) > 16:
            digest = hashlib.md5(content).hexdigest()[:8]
            dest = dest_dir / f"{dest.stem}-{digest}{dest.suffix or '.bin'}"
        dest.write_bytes(content)
        return str(dest.relative_to(ROOT)).replace("\\", "/")
    except Exception as exc:
        print(f"  warning: failed to download {url}: {exc}")
        return None


def localize_html_images(html: str, dest_dir: Path, images_map: dict[str, str]) -> str:
    if not html:
        return html

    def replace_img(match: re.Match) -> str:
        prefix, url, suffix = match.group(1), match.group(2), match.group(3)
        if not is_webflow_asset_url(url):
            return match.group(0)
        if url in images_map:
            return f"{prefix}{images_map[url]}{suffix}"
        local = mirror_url(url, dest_dir)
        if local:
            images_map[url] = local
            return f"{prefix}{local}{suffix}"
        return match.group(0)

    return IMG_SRC_RE.sub(replace_img, html)


def localize_record_images(record: dict, collection: str) -> dict:
    slug = record["slug"]
    dest_dir = IMAGES_CMS / collection / slug
    fields = record.get("fields") or {}
    images_map: dict[str, str] = {}

    for key, value in list(fields.items()):
        if not isinstance(value, str) or not value:
            continue
        if value.startswith("http") and is_webflow_asset_url(value):
            local = mirror_url(value, dest_dir)
            if local:
                record["images"][key] = local
                fields[key] = local
            continue
        if "<img" in value.lower():
            localized = localize_html_images(value, dest_dir, images_map)
            if localized != value:
                fields[key] = localized
                for remote, local in images_map.items():
                    if key not in record["images"]:
                        record["images"][key] = local
                    break
                for remote, local in images_map.items():
                    record["images"].setdefault(f"{key}:{remote}", local)

    return record


def cleanup_orphan_images(data: dict[str, list[dict]]) -> None:
    if not IMAGES_CMS.is_dir():
        return
    valid: set[str] = set()
    for collection, key in IMAGE_COLLECTIONS.items():
        for item in data.get(key, []):
            valid.add(f"{collection}/{item['slug']}")
    removed = 0
    for collection_dir in IMAGES_CMS.iterdir():
        if not collection_dir.is_dir():
            continue
        for slug_dir in collection_dir.iterdir():
            if not slug_dir.is_dir():
                continue
            rel = f"{collection_dir.name}/{slug_dir.name}"
            if rel not in valid:
                shutil.rmtree(slug_dir)
                removed += 1
    if removed:
        print(f"  removed {removed} orphan image directories")


def _scan_file(path: Path) -> list[tuple[str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    hits = []
    for pattern in AUDIT_PATTERNS:
        if pattern in text:
            for match in URL_IN_TEXT_RE.findall(text):
                if pattern in match:
                    hits.append((str(path.relative_to(ROOT)), match))
    return hits


def audit_remote_assets() -> bool:
    """Return True if no remote Webflow/CloudFront asset URLs remain."""
    hits: list[tuple[str, str]] = []
    scan_roots = [
        DATA_DIR,
        ROOT / "css",
        ROOT / "js",
        ROOT / "scripts" / "templates",
    ]
    for root in scan_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".html", ".json", ".css", ".js"}:
                continue
            if path.name == "stylesheet.html":
                continue
            hits.extend(_scan_file(path))

    for path in ROOT.glob("*.html"):
        hits.extend(_scan_file(path))
    for sub in ("earn", "bounties", "missions", "instagrants", "projects", "skills", "dao-members", "services", "docs"):
        subdir = ROOT / sub
        if subdir.is_dir():
            for path in subdir.rglob("*.html"):
                hits.extend(_scan_file(path))

    unique = sorted(set(hits))
    if unique:
        print("  audit: remote asset URLs still present:")
        for filepath, url in unique[:20]:
            print(f"    {filepath}: {url[:100]}")
        if len(unique) > 20:
            print(f"    ... and {len(unique) - 20} more")
        return False
    print("  audit: no remote Webflow/CloudFront asset URLs found")
    return True
