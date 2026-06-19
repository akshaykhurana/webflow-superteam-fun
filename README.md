# Superteam.fun (Webflow Export + Static CMS)

Static portfolio build of the Superteam Webflow design with CMS content generated from CSV exports.

## Build

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py
```

Commands:

- `python scripts/build.py` — import CSVs → JSON, download images, render HTML
- `python scripts/build.py import` — JSON + images only
- `python scripts/build.py render` — HTML from existing JSON
- `python scripts/build.py --skip-images` — skip Webflow CDN image downloads

## Data

Place Webflow CSV exports in `data/`:

| File | Collection |
|------|------------|
| `dao-members.csv` | DAO Members |
| `master-skills.csv` | Master Skills |
| `missions.csv` | Missions |
| `instagrants.csv` | Instagrants |
| `projects.csv` | Projects |
| `bounties.csv` | Bounties |

Normalized JSON is written to `data/*.json`. Duplicate CMS items are merged at import time; see `data/slug-aliases.json` for the slug remap audit trail.

## Output structure

```
bounties/{slug}.html        # 61 detail pages
missions/{slug}.html        # 14 detail pages
instagrants/{slug}.html     # 12 detail pages
projects/{slug}.html        # 23 detail pages
skills/{slug}.html          # 8 detail pages
dao-members/{slug}.html     # 3 detail pages
images/cms/                 # downloaded project thumbnails
```

Listing pages (`showcase.html`, `earn/*.html`, `index.html`) are rendered from pristine templates in `scripts/templates/listings/`.

Detail page templates live in `scripts/templates/detail/`.

## Local preview

```bash
python3 -m http.server 8765
```

Open http://127.0.0.1:8765

## Cloudflare Pages

| Setting | Value |
|---------|-------|
| Build command | `pip install -r requirements.txt && python scripts/build.py` |
| Output directory | `.` |
| Python version | 3.11+ |

Or commit pre-built HTML and skip the build step.

## Notes

- Newsletter footers are replaced with a Twitter follow link (static site).
- Jobs collection links to external Pallet — not CMS-driven.
- Re-run build after updating CSVs. Listing pages are regenerated from templates each render.
