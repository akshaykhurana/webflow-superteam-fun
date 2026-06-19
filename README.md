# Superteam.fun (Webflow Export + Static CMS)

Static portfolio build of the Superteam Webflow design with CMS content generated from CSV exports. All Webflow CDN assets are mirrored locally — the site has no runtime dependency on Webflow hosting.

**Repository:** https://github.com/akshaykhurana/webflow-superteam-fun

## Pre-deletion checklist (Webflow)

Before deleting the Webflow project, ensure:

1. Fresh CSV exports for all 6 collections are in `data/`
2. Run `python scripts/build.py` with network access to download CMS thumbnails
3. Commit all files under `images/cms/`, `js/jquery-3.5.1.min.js`, and built HTML
4. Verify build ends with `audit: no remote Webflow/CloudFront asset URLs found`

After Webflow deletion, rebuilds use frozen CSVs and committed local assets only.

## Build

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py
```

Commands:

- `python scripts/build.py` — import CSVs → JSON, download images, render HTML, audit remote URLs
- `python scripts/build.py import` — JSON + images only
- `python scripts/build.py render` — HTML from existing JSON
- `python scripts/build.py --skip-images` — skip Webflow CDN image downloads (use only after assets are committed)

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
images/cms/                 # mirrored CMS thumbnails
js/jquery-3.5.1.min.js      # vendored (was CloudFront)
```

Listing pages (`showcase.html`, `earn/*.html`, `index.html`) are rendered from pristine templates in `scripts/templates/listings/`.

Detail page templates live in `scripts/templates/detail/`.

## Local preview

```bash
python3 -m http.server 8765
```

Open http://127.0.0.1:8765

## Cloudflare Pages

Connect the GitHub repo with these settings:

| Setting | Value |
|---------|-------|
| Build command | *(empty — site is pre-built in repo)* |
| Build output directory | `/` |
| Production branch | `main` |

Pushes to `main` auto-deploy. No Python build step is required on Cloudflare because HTML and assets are committed.

### Redirect warning

Do **not** add `_redirects` rules that rewrite clean paths back to `.html` files (e.g. `/about /about.html 200`). Cloudflare Pages already strips `.html` with a 308 redirect; rewriting back causes infinite redirect loops.

`_headers` is included for long-lived cache on static assets.

## Notes

- Newsletter footers are replaced with a Twitter follow link (static site).
- Jobs collection links to external Pallet — not CMS-driven.
- Re-run build after updating CSVs. Listing pages are regenerated from templates each render.
- Two projects (`solace-development-protocol`, `superteam-media`) have no thumbnail in the CMS export.
