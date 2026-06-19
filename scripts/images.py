"""Download CMS images and rewrite URLs to local paths."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests

from util import IMAGES_CMS, ROOT, clean_text

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "superteam-cms-build/1.0"})

IMAGE_COLLECTIONS = {
    "projects": "projects",
}


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = Path(path).name or "image"
    if not Path(name).suffix:
        name += ".bin"
    return name


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


def localize_record_images(record: dict, collection: str) -> dict:
    slug = record["slug"]
    dest_dir = IMAGES_CMS / collection / slug
    fields = record.get("fields") or {}
    for key, value in list(fields.items()):
        if isinstance(value, str) and value.startswith("http"):
            if "thumbnail" in key.lower() or "uploads" in value or "webflow" in value:
                local = download_image(value, dest_dir)
                if local:
                    record["images"][key] = local
                    fields[key] = local
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
