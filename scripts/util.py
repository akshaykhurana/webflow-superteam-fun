"""Shared utilities for the CMS build pipeline."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
IMAGES_CMS = ROOT / "images" / "cms"


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("true", "yes", "1")


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def slugify_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def twitter_handle(url: str | None) -> str:
    if not url:
        return ""
    url = url.strip().rstrip("/")
    if "@" in url and "twitter.com" not in url and "x.com" not in url:
        return url.lstrip("@")
    parts = urlparse(url).path.strip("/").split("/")
    return parts[-1] if parts else ""


def skill_tag_line(skills: list[str]) -> str:
    if not skills:
        return ""
    return " | ".join(s.upper() for s in skills)


def adjust_root_paths(html: str, depth: int = 0) -> str:
    if depth <= 0:
        return html
    prefix = "../" * depth
    return re.sub(
        r'(href|src)="(?!https?://|#|mailto:|tel:|javascript:)([^"]+)"',
        rf'\1="{prefix}\2"',
        html,
    )


def remove_dyn_empty_class(tag) -> None:
    classes = [c for c in (tag.get("class") or []) if c != "w-dyn-bind-empty"]
    if classes:
        tag["class"] = classes
    elif "class" in tag.attrs:
        del tag["class"]


def apply_bindings(soup, bindings: list[dict]) -> None:
    from bs4 import BeautifulSoup

    elements = soup.select(".w-dyn-bind-empty")
    for el, binding in zip(elements, bindings):
        kind = binding.get("type", "text")
        value = binding.get("value", "")
        if kind == "html":
            el.clear()
            frag = BeautifulSoup(value or "", "html.parser")
            for child in list(frag.children):
                el.append(child)
        elif kind == "img":
            if value:
                el["src"] = value
            if binding.get("alt"):
                el["alt"] = binding["alt"]
        else:
            el.string = value
        remove_dyn_empty_class(el)


def set_page_title(soup, title: str) -> None:
    if soup.title:
        soup.title.string = title
    else:
        tag = soup.new_tag("title")
        tag.string = title
        soup.head.append(tag)


def status_class(status: str) -> str:
    s = (status or "").strip().lower()
    if s == "open":
        return "open"
    if s in ("judging", "inactive"):
        return "judging"
    return "closed"


def format_deadline(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if value.lower().startswith("ends"):
        return value
    return value.split(" GMT")[0] if "GMT" in value else value
