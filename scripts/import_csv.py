"""Import Webflow CSV exports into normalized JSON."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from images import localize_record_images
from util import DATA_DIR, clean_text, skill_tag_line, slugify_name, truthy, twitter_handle

COLLECTION_FILES = {
    "dao-members": "dao-members.csv",
    "master-skills": "master-skills.csv",
    "missions": "missions.csv",
    "instagrants": "instagrants.csv",
    "projects": "projects.csv",
    "bounties": "bounties.csv",
}

DEDUPE_COLLECTIONS = (
    "master-skills",
    "missions",
    "instagrants",
    "projects",
    "bounties",
)

SKIP_CSV_COLUMNS = {
    "Collection ID", "Locale ID", "Item ID", "Archived", "Draft",
    "Created On", "Updated On", "Published On",
    "Name", "Slug", "Skill Name",
}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def pick_canonical(group: list[dict]) -> dict:
    """Keep one duplicate: prefer slugify(name), else shortest slug, else first row."""
    base = slugify_name(group[0]["name"])
    for item in group:
        if item["slug"] == base:
            return item
    return min(group, key=lambda r: (len(r["slug"]), group.index(r)))


def build_alias_map(items: list[dict], label: str) -> tuple[list[dict], dict[str, str]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[item["name"].strip().lower()].append(item)

    kept: list[dict] = []
    aliases: dict[str, str] = {}
    removed = 0
    for group in groups.values():
        chosen = pick_canonical(group)
        kept.append(chosen)
        for item in group:
            if item["slug"] != chosen["slug"]:
                aliases[item["slug"]] = chosen["slug"]
                removed += 1
    if removed:
        print(f"  deduped {label}: {len(items)} -> {len(kept)} ({removed} duplicates removed)")
    return kept, aliases


def remap_skill_refs(items: list[dict], aliases: dict[str, str]) -> None:
    if not aliases:
        return
    for item in items:
        slugs = item.get("refs", {}).get("skills", [])
        if not slugs:
            continue
        canonical = []
        for slug in slugs:
            slug = aliases.get(slug, slug)
            if slug not in canonical:
                canonical.append(slug)
        item["refs"]["skills"] = canonical


def apply_aliases(data: dict[str, list[dict]], all_aliases: dict[str, dict[str, str]]) -> None:
    """Remap skill refs and refresh skill tags after dedup."""
    skill_aliases = all_aliases.get("master-skills", {})
    remap_skill_refs(data["bounties"], skill_aliases)
    remap_skill_refs(data["missions"], skill_aliases)

    skill_by_slug = {s["slug"]: s for s in data["master-skills"]}
    for item in data["bounties"] + data["missions"]:
        slugs = item["refs"].get("skills", [])
        if slugs:
            labels = skill_labels(slugs, skill_by_slug)
            item["fields"]["skillTag"] = skill_tag_line(labels)


def base_record(row: dict, name_key: str = "Name") -> dict | None:
    if truthy(row.get("Archived")) or truthy(row.get("Draft")):
        return None
    name = clean_text(row.get(name_key) or row.get("Skill Name"))
    slug = clean_text(row.get("Slug"))
    if not slug:
        return None
    return {
        "id": clean_text(row.get("Item ID")),
        "slug": slug,
        "name": name,
        "collectionId": clean_text(row.get("Collection ID")),
        "fields": {},
        "refs": {},
        "images": {},
    }


def parse_skills_field(
    value: str,
    skill_by_slug: dict,
    skill_by_name: dict,
    skill_aliases: dict | None = None,
) -> list[str]:
    if not value:
        return []
    aliases = skill_aliases or {}
    parts = [p.strip() for p in value.replace(";", ",").split(",") if p.strip()]
    slugs = []
    for part in parts:
        resolved = None
        if part in aliases:
            resolved = aliases[part]
        elif part in skill_by_slug:
            resolved = part
        elif part.lower() in skill_by_name:
            resolved = skill_by_name[part.lower()]
        else:
            guess = slugify_name(part)
            if guess in skill_by_slug:
                resolved = guess
            elif guess in aliases:
                resolved = aliases[guess]
        if resolved:
            resolved = aliases.get(resolved, resolved)
            if resolved not in slugs:
                slugs.append(resolved)
    return slugs


def skill_labels(slugs: list[str], skill_by_slug: dict, fallback: str = "") -> list[str]:
    labels = []
    for slug in slugs:
        item = skill_by_slug.get(slug)
        labels.append(item["name"] if item else slug.replace("-", " ").title())
    if not labels and fallback:
        labels = [fallback]
    return labels


def import_all(download_images: bool = True) -> tuple[dict[str, list[dict]], dict[str, dict[str, str]]]:
    data: dict[str, list[dict]] = {}
    all_aliases: dict[str, dict[str, str]] = {}

    rows = read_csv(DATA_DIR / COLLECTION_FILES["dao-members"])
    data["dao-members"] = []
    for row in rows:
        rec = base_record(row)
        if not rec:
            continue
        rec["fields"]["twitterLink"] = clean_text(row.get("Twitter Link"))
        data["dao-members"].append(rec)

    dao_by_twitter = {}
    dao_by_name = {}
    for m in data["dao-members"]:
        handle = twitter_handle(m["fields"].get("twitterLink"))
        if handle:
            dao_by_twitter[handle.lower()] = m["slug"]
        dao_by_name[m["name"].lower()] = m["slug"]

    rows = read_csv(DATA_DIR / COLLECTION_FILES["master-skills"])
    data["master-skills"] = []
    for row in rows:
        rec = base_record(row, name_key="Skill Name")
        if rec:
            data["master-skills"].append(rec)
    data["master-skills"], all_aliases["master-skills"] = build_alias_map(
        data["master-skills"], "master-skills"
    )
    skill_aliases = all_aliases["master-skills"]

    skill_by_slug = {s["slug"]: s for s in data["master-skills"]}
    skill_by_name = {s["name"].lower(): s["slug"] for s in data["master-skills"]}

    rows = read_csv(DATA_DIR / COLLECTION_FILES["missions"])
    data["missions"] = []
    for row in rows:
        rec = base_record(row)
        if not rec:
            continue
        skill_slugs = parse_skills_field(
            row.get("Skills", ""), skill_by_slug, skill_by_name, skill_aliases
        )
        labels = skill_labels(skill_slugs, skill_by_slug, clean_text(row.get("Skills 2")))
        rec["refs"]["skills"] = skill_slugs
        rec["fields"]["skillTag"] = skill_tag_line(labels)
        rec["fields"]["status"] = clean_text(row.get("Status"))
        rec["fields"]["type"] = clean_text(row.get("Type of Mission"))
        rec["fields"]["availableTo"] = clean_text(row.get("Available To"))
        rec["fields"]["missionBudget"] = clean_text(row.get("Mission Budget"))
        rec["fields"]["estimatedTime"] = clean_text(row.get("Estimated Time"))
        rec["fields"]["missionOverview"] = clean_text(row.get("Mission Overview"))
        rec["fields"]["scopeOfWork"] = clean_text(row.get("Scope of Work"))
        rec["fields"]["idealProfile"] = clean_text(row.get("Ideal Profile"))
        rec["fields"]["notes"] = clean_text(row.get("Notes"))
        rec["fields"]["screeningQuestions"] = clean_text(row.get("Mission Screening Questions"))
        rec["fields"]["missionLogistics"] = clean_text(row.get("Mission Logistics"))
        data["missions"].append(rec)
    data["missions"], all_aliases["missions"] = build_alias_map(data["missions"], "missions")

    rows = read_csv(DATA_DIR / COLLECTION_FILES["instagrants"])
    data["instagrants"] = []
    for row in rows:
        rec = base_record(row)
        if not rec:
            continue
        rec["fields"]["status"] = clean_text(row.get("Status")) or "Open"
        rec["fields"]["grantSize"] = clean_text(row.get("Grant Size"))
        rec["fields"]["currency"] = clean_text(row.get("Currency"))
        rec["fields"]["grantOverview"] = clean_text(row.get("Grant Overview"))
        rec["fields"]["areasOfFocus"] = clean_text(row.get("Areas of Focus"))
        rec["fields"]["howItWorks"] = clean_text(row.get("How it Works"))
        rec["fields"]["resources"] = clean_text(row.get("Resources"))
        rec["fields"]["faqs"] = clean_text(row.get("FAQs"))
        data["instagrants"].append(rec)
    data["instagrants"], all_aliases["instagrants"] = build_alias_map(
        data["instagrants"], "instagrants"
    )

    rows = read_csv(DATA_DIR / COLLECTION_FILES["projects"])
    data["projects"] = []
    for row in rows:
        rec = base_record(row)
        if not rec:
            continue
        lead = clean_text(row.get("Project Lead"))
        twitter = clean_text(row.get("Twitter of Project Lead"))
        handle = twitter_handle(twitter)
        led_by = dao_by_twitter.get(handle.lower()) if handle else None
        if not led_by and lead:
            led_by = dao_by_name.get(lead.lower())
        rec["refs"]["ledBy"] = led_by
        rec["fields"]["tagline"] = clean_text(row.get("Tagline"))
        rec["fields"]["projectLink"] = clean_text(row.get("Project Link"))
        rec["fields"]["projectLead"] = lead
        rec["fields"]["twitterOfProjectLead"] = twitter
        rec["fields"]["featured"] = truthy(row.get("Featured Projects"))
        rec["fields"]["thumbnail"] = clean_text(row.get("Thumbnail"))
        rec["fields"]["description"] = clean_text(row.get("Project Description"))
        rec["fields"]["mainContent"] = clean_text(row.get("Main Content"))
        if download_images:
            rec = localize_record_images(rec, "projects")
        data["projects"].append(rec)
    data["projects"], all_aliases["projects"] = build_alias_map(data["projects"], "projects")

    rows = read_csv(DATA_DIR / COLLECTION_FILES["bounties"])
    data["bounties"] = []
    for row in rows:
        rec = base_record(row)
        if not rec:
            continue
        skill_slugs = parse_skills_field(
            row.get("Skills", ""), skill_by_slug, skill_by_name, skill_aliases
        )
        labels = skill_labels(skill_slugs, skill_by_slug, clean_text(row.get("Skills 2")))
        rec["refs"]["skills"] = skill_slugs
        rec["fields"]["skillTag"] = skill_tag_line(labels)
        rec["fields"]["status"] = clean_text(row.get("Status"))
        rec["fields"]["type"] = clean_text(row.get("Type of Bounty"))
        rec["fields"]["prize"] = clean_text(row.get("Total Prize Pool"))
        rec["fields"]["currency"] = clean_text(row.get("Currency"))
        rec["fields"]["deadline"] = clean_text(row.get("Deadline"))
        rec["fields"]["description"] = clean_text(row.get("Description"))
        rec["fields"]["mission"] = clean_text(row.get("Mission"))
        rec["fields"]["rewards"] = clean_text(row.get("Rewards"))
        rec["fields"]["evaluationCriteria"] = clean_text(row.get("Evaluation Criteria"))
        rec["fields"]["resources"] = clean_text(row.get("Resources"))
        rec["fields"]["terms"] = clean_text(row.get("Terms and Conditions"))
        rec["fields"]["notes"] = clean_text(row.get("Notes"))
        rec["fields"]["bugBounty"] = clean_text(row.get("Bug Bounty"))
        data["bounties"].append(rec)
    data["bounties"], all_aliases["bounties"] = build_alias_map(data["bounties"], "bounties")

    apply_aliases(data, all_aliases)
    return data, all_aliases


def write_slug_aliases(all_aliases: dict[str, dict[str, str]]) -> None:
    out = DATA_DIR / "slug-aliases.json"
    out.write_text(json.dumps(all_aliases, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in all_aliases.values())
    print(f"  wrote slug-aliases.json ({total} slug remaps)")


def write_json_files(data: dict[str, list[dict]]) -> None:
    for key, items in data.items():
        out = DATA_DIR / f"{key}.json"
        out.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  wrote {out.name} ({len(items)} items)")


def load_json_files() -> dict[str, list[dict]]:
    data = {}
    for key in COLLECTION_FILES:
        path = DATA_DIR / f"{key}.json"
        if path.exists():
            data[key] = json.loads(path.read_text(encoding="utf-8"))
    return data
