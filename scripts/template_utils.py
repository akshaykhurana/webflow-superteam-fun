"""Helpers for Webflow HTML templates."""
from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPTS_DIR / "templates"
LISTING_TEMPLATES_DIR = TEMPLATES_DIR / "listings"
DETAIL_TEMPLATES_DIR = TEMPLATES_DIR / "detail"
ARCHIVE_TEMPLATES_DIR = TEMPLATES_DIR / "archive"

LISTING_PAGES = (
    "showcase.html",
    "about.html",
    "earn.html",
    "index.html",
    "earn/bounties.html",
    "earn/missions.html",
    "earn/instagrants.html",
)

DETAIL_TEMPLATES = (
    "detail_bounties.html",
    "detail_missions.html",
    "detail_instagrants.html",
)

ARCHIVED_DETAIL_TEMPLATES = (
    "detail_projects.html",
    "detail_skills.html",
    "detail_dao-members.html",
    "detail_jobs.html",
)


def reset_dyn_lists_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for dyn_list in soup.select(".w-dyn-list"):
        items_container = dyn_list.select_one(".w-dyn-items")
        if items_container:
            items_container.clear()
        if not dyn_list.select_one(".w-dyn-empty"):
            empty = soup.new_tag("div")
            empty["class"] = "w-dyn-empty"
            empty.string = "No items found."
            dyn_list.append(empty)
    return str(soup)


def strip_newsletter_forms(soup: BeautifulSoup) -> None:
    for form in soup.select(".form-master.w-form"):
        link = soup.new_tag("a")
        link["href"] = "https://twitter.com/SuperteamDAO"
        link["class"] = "text-bodyregular text-emphasis"
        link.string = "Follow @SuperteamDAO on Twitter for updates"
        form.replace_with(link)


def remove_winning_entries(soup: BeautifulSoup) -> None:
    for heading in soup.find_all("h2", class_="heading-section"):
        if heading.get_text(strip=True) != "Winning Entries":
            continue
        section = heading.find_parent("div", class_="block-subsection")
        if section:
            section.decompose()


def apply_status_visibility(soup: BeautifulSoup, status: str) -> None:
    from util import status_class

    active = status_class(status)
    for badge in soup.select(".icon-statusbadge"):
        classes = badge.get("class") or []
        if active not in classes:
            badge.decompose()
    for aside in soup.select(".block-aside"):
        heading = aside.find("h4", class_=lambda c: c and "closed" in c)
        if not heading:
            continue
        text = heading.get_text(strip=True).upper()
        if "CLOSED" in text and active == "open":
            aside.decompose()


def prepare_listing_html(html: str, rel_path: str) -> str:
    soup = BeautifulSoup(reset_dyn_lists_html(html), "html.parser")
    strip_newsletter_forms(soup)
    if rel_path == "index.html":
        remove_winning_entries(soup)
    return str(soup)


def ensure_listing_templates(root: Path) -> None:
    for rel in LISTING_PAGES:
        dest = LISTING_TEMPLATES_DIR / rel
        if dest.exists():
            continue
        src = root / rel
        if not src.exists():
            raise FileNotFoundError(f"Missing listing page to seed template: {src}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(prepare_listing_html(src.read_text(encoding="utf-8"), rel), encoding="utf-8")


def ensure_detail_templates(root: Path) -> None:
    DETAIL_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for name in DETAIL_TEMPLATES:
        dest = DETAIL_TEMPLATES_DIR / name
        src = root / name
        if not dest.exists():
            if not src.exists():
                raise FileNotFoundError(f"Missing detail template source: {src}")
            soup = BeautifulSoup(src.read_text(encoding="utf-8"), "html.parser")
            strip_newsletter_forms(soup)
            dest.write_text(str(soup), encoding="utf-8")
        if src.exists():
            src.unlink()
    for name in ARCHIVED_DETAIL_TEMPLATES:
        dest = ARCHIVE_TEMPLATES_DIR / name
        if dest.exists():
            continue
        src = root / name
        if src.exists():
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            src.unlink()
