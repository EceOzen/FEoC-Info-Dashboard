#!/usr/bin/env python3
"""
Deploy-time asset preparation for chart_type="asset" panels.

Currently one job: for every PDF asset without an explicit `asset.preview`,
render page 1 to <asset path>.preview.png so the dashboard can show a
thumbnail (browsers on phones can't embed PDFs reliably). Needs `pdftoppm`
(poppler-utils); CI installs it, locally it's skipped with a note if absent.

Generated previews are build output, not source: they're gitignored and
recreated on every deploy.

Usage:
    python scripts/build_assets.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
PANELS_DIR = SITE_DIR / "panels"


def main() -> int:
    pdfs = []
    for path in sorted(PANELS_DIR.rglob("*.json")):
        panel = json.loads(path.read_text())
        asset = panel.get("asset") or {}
        if panel.get("chart_type") == "asset" and asset.get("format") == "pdf" and not asset.get("preview"):
            pdfs.append(SITE_DIR / asset["path"])

    if not pdfs:
        print("build_assets: no PDF assets need previews.")
        return 0

    if shutil.which("pdftoppm") is None:
        print("build_assets: pdftoppm not found (install poppler-utils); "
              f"skipping {len(pdfs)} PDF preview(s). The dashboard falls back to an embedded viewer.")
        return 0

    for pdf in pdfs:
        out = pdf.with_name(pdf.name + ".preview.png")
        # pdftoppm appends ".png" itself when given -singlefile
        stem = str(out)[: -len(".png")]
        subprocess.run(
            ["pdftoppm", "-png", "-singlefile", "-f", "1", "-l", "1", "-scale-to", "1400", str(pdf), stem],
            check=True,
        )
        print(f"build_assets: wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
