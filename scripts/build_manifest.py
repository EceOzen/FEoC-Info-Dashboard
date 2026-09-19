#!/usr/bin/env python3
"""
Post-merge step: scans site/panels/**/*.json and writes site/manifest.json,
a flat index the dashboard fetches on load (a static GitHub Pages site
can't list a directory itself, so this manifest stands in for that).

Only 'published' panels are included by default — 'draft' panels are left
out of the manifest so they don't appear on the live site (draft is for
local preview only, per schema/panel.schema.json). Pass --include-drafts
for a preview build.

Usage:
    python scripts/build_manifest.py                 # production manifest, published only
    python scripts/build_manifest.py --include-drafts  # preview build
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PANELS_DIR = REPO_ROOT / "site" / "panels"
MANIFEST_PATH = REPO_ROOT / "site" / "manifest.json"


def build_manifest(include_drafts: bool = False) -> dict:
    entries = []
    for path in sorted(PANELS_DIR.rglob("*.json")):
        panel = json.loads(path.read_text())
        status = panel.get("status")

        if status == "retracted":
            continue  # never listed, even in preview
        if status == "draft" and not include_drafts:
            continue

        entries.append(
            {
                "panel_id": panel["panel_id"],
                "forcing_type": panel["forcing_type"],
                "title": panel["title"],
                "subtitle": panel.get("subtitle"),
                "chart_type": panel["chart_type"],
                "comparison_group": panel.get("comparison_group"),
                "status": status,
                "path": str(path.relative_to(REPO_ROOT / "site")),
                "production_ready": panel.get("meta", {}).get("production_ready"),
            }
        )

    return {
        "generated_by": "scripts/build_manifest.py",
        "includes_drafts": include_drafts,
        "panel_count": len(entries),
        "panels": entries,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-drafts", action="store_true")
    ap.add_argument("--out", default=str(MANIFEST_PATH))
    args = ap.parse_args()

    manifest = build_manifest(include_drafts=args.include_drafts)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out_path} ({manifest['panel_count']} panel(s), includes_drafts={args.include_drafts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
