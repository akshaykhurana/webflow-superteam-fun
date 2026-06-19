#!/usr/bin/env python3
"""Build static CMS pages from Webflow CSV exports."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python3 scripts/build.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_csv import import_all, load_json_files, write_json_files, write_slug_aliases
from images import audit_remote_assets
from render_html import render_all


def cmd_import(download_images: bool = True) -> dict:
    print("Importing CSVs → JSON...")
    data, all_aliases = import_all(download_images=download_images)
    write_json_files(data)
    write_slug_aliases(all_aliases)
    return data


def cmd_render(data: dict | None = None) -> None:
    if data is None:
        print("Loading JSON...")
        data = load_json_files()
    print("Rendering HTML...")
    render_all(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Superteam static CMS site")
    parser.add_argument("command", nargs="?", default="all", choices=["all", "import", "render"])
    parser.add_argument("--skip-images", action="store_true", help="Skip downloading CMS images")
    args = parser.parse_args()

    if args.command == "import":
        cmd_import(download_images=not args.skip_images)
    elif args.command == "render":
        cmd_render()
    else:
        data = cmd_import(download_images=not args.skip_images)
        cmd_render(data)
    print("Auditing remote assets...")
    if not audit_remote_assets():
        raise SystemExit(1)
    print("Done.")


if __name__ == "__main__":
    main()
