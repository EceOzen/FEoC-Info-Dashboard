"""
from_asset.py: put a READY-MADE figure on the dashboard as it is.

Use this when you already have the figure itself, not just the numbers:
a matplotlib SVG/PNG, a Plotly figure saved with fig.write_json(), a Bokeh or
Folium HTML page, an animation (GIF/MP4/WebM), a paper figure as PDF, a CSV
you want the dashboard to plot, or a Jupyter notebook with its outputs.

The script:
  1. copies your file to site/assets/<forcing_type>/<panel_id>.<ext>
  2. writes the panel JSON to site/panels/<forcing_type>/<panel_id>.json
     (same write_panel() every other script uses, so it's validated)
From there the flow is the usual one: validate, open a PR, CI publishes.

The format is guessed from the file extension (.json is assumed to be a
Plotly figure). Override with --format if needed.

Examples:
    # matplotlib figure, headline of the volcanic section
    python methods/generic/from_asset.py --input saod_map.svg \\
        --forcing-type volcanic --panel-id saod_pinatubo_map \\
        --title "Stratospheric aerosol after Pinatubo" \\
        --alt-text "Map of stratospheric aerosol optical depth in 1992, highest in the tropics" \\
        --section volcanic --prominence headline \\
        --key-message "Pinatubo's aerosol veil covered the whole tropics within months." \\
        --analysis-level forcing_input --method-note "Plotted from GloSSAC v2.2" \\
        --source "notebook in github.com/x/y" --author dominik

    # CSV the dashboard draws itself, with an uncertainty band
    python methods/generic/from_asset.py --input erf.csv --csv-x year --csv-y erf \\
        --csv-lo erf_p05 --csv-hi erf_p95 ...

    # supporting detail folded under another panel
    ... --prominence supporting --parent saod_pinatubo_map

Because the figure was made outside this repo, --method-note and --source are
required: they are what makes the panel traceable later.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from feoc_panels import write_panel  # noqa: E402
from feoc_panels.contract import PanelArtifact, AssetSpec, AxisSpec, Meta  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None

EXT_TO_FORMAT = {
    ".svg": "svg", ".png": "png", ".webp": "webp", ".jpg": "jpg", ".jpeg": "jpg",
    ".gif": "gif", ".json": "plotly_json", ".html": "html", ".htm": "html",
    ".mp4": "mp4", ".webm": "webm", ".pdf": "pdf", ".csv": "csv", ".tsv": "csv",
    ".ipynb": "ipynb",
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


def _copy_into_assets(src: Path, site_dir: Path, forcing_type: str, name: str) -> str:
    dest_dir = site_dir / "assets" / forcing_type
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    return f"assets/{forcing_type}/{name}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="The figure file.")
    ap.add_argument("--format", choices=sorted(set(EXT_TO_FORMAT.values())), default=None,
                    help="Override the format guessed from the extension.")
    ap.add_argument("--alt-text", required=True, help="What the figure shows, in one or two sentences (10-500 chars).")
    ap.add_argument("--height", type=int, default=None, help="Display height in px for html/plotly/pdf frames.")
    ap.add_argument("--poster", default=None, help="Still image shown before a video plays (mp4/webm).")
    ap.add_argument("--csv-x", default=None, help="CSV only: x column.")
    ap.add_argument("--csv-y", default=None, help="CSV only: y column.")
    ap.add_argument("--csv-lo", default=None, help="CSV only: lower bound column (band).")
    ap.add_argument("--csv-hi", default=None, help="CSV only: upper bound column (band).")
    ap.add_argument("--csv-render-as", choices=["line", "scatter"], default=None)
    ap.add_argument("--x-label", default=None, help="CSV only, optional axis label.")
    ap.add_argument("--x-unit", default="")
    ap.add_argument("--y-label", default=None, help="CSV only, optional axis label.")
    ap.add_argument("--y-unit", default="")
    ap.add_argument("--cell", type=int, default=None, help="ipynb only: code cell index to show.")

    ap.add_argument("--forcing-type", required=True, choices=["ghg", "volcanic"])
    ap.add_argument("--panel-id", required=True, help="Unique id, lowercase_with_underscores, 3-80 chars.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default=None)
    ap.add_argument("--analysis-level", required=True, choices=["forcing_input", "model_response"])
    ap.add_argument("--comparison-group", default=None)

    ap.add_argument("--section", default=None, help="Section id from site/sections.json.")
    ap.add_argument("--prominence", choices=["headline", "primary", "supporting"], default=None)
    ap.add_argument("--order", type=int, default=None, help="Position inside the section, lower first.")
    ap.add_argument("--parent", default=None, help="panel_id this supporting panel belongs under.")
    ap.add_argument("--key-message", default=None, help="One plain-language takeaway sentence.")

    ap.add_argument("--method-note", required=True, help="How was this figure produced?")
    ap.add_argument("--source", required=True, help="Where it comes from: repo, notebook, paper.")
    ap.add_argument("--author", required=True)
    ap.add_argument("--citation", default=None)
    ap.add_argument("--method-version", default="0.1.0")
    ap.add_argument("--drs", default=None)
    ap.add_argument("--status", default="draft", choices=["draft", "published"])
    ap.add_argument("--site-dir", default=str(REPO_ROOT / "site"))
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        return _fail(f"input file not found: {src}")
    if not SLUG_RE.match(args.panel_id) or not (3 <= len(args.panel_id) <= 80):
        return _fail("--panel-id must be lowercase letters/digits/_/-, 3-80 chars, starting with a letter or digit.")

    fmt = args.format or EXT_TO_FORMAT.get(src.suffix.lower())
    if fmt is None:
        return _fail(f"can't guess the format of {src.name}; pass --format.")
    if args.parent and args.prominence not in (None, "supporting"):
        return _fail("--parent only makes sense with --prominence supporting.")
    prominence = args.prominence or ("supporting" if args.parent else None)

    csv_cols = None
    if fmt == "csv":
        if not (args.csv_x and args.csv_y):
            return _fail("CSV input needs --csv-x and --csv-y.")
        csv_cols = {"x": args.csv_x, "y": args.csv_y}
        if args.csv_lo or args.csv_hi:
            if not (args.csv_lo and args.csv_hi):
                return _fail("give both --csv-lo and --csv-hi, or neither.")
            csv_cols.update(lo=args.csv_lo, hi=args.csv_hi)
        if args.csv_render_as:
            csv_cols["render_as"] = args.csv_render_as
    if fmt == "plotly_json":
        try:
            if "data" not in json.loads(src.read_text()):
                return _fail(f"{src.name} doesn't look like a Plotly figure (no 'data' key). Save it with fig.write_json().")
        except json.JSONDecodeError:
            return _fail(f"{src.name} is not valid JSON.")

    site_dir = Path(args.site_dir)
    asset_rel = _copy_into_assets(src, site_dir, args.forcing_type, f"{args.panel_id}{src.suffix.lower()}")
    poster_rel = None
    if args.poster:
        p = Path(args.poster)
        poster_rel = _copy_into_assets(p, site_dir, args.forcing_type, f"{args.panel_id}.poster{p.suffix.lower()}")

    x_axis = y_axis = None
    if fmt == "csv" and args.x_label and args.y_label:
        x_axis = AxisSpec(label=args.x_label, unit=args.x_unit)
        y_axis = AxisSpec(label=args.y_label, unit=args.y_unit)

    panel = PanelArtifact(
        panel_id=args.panel_id,
        title=args.title,
        subtitle=args.subtitle,
        forcing_type=args.forcing_type,
        chart_type="asset",
        analysis_level=args.analysis_level,
        comparison_group=args.comparison_group,
        asset=AssetSpec(
            path=asset_rel, format=fmt, alt_text=args.alt_text, height=args.height,
            poster=poster_rel, csv=csv_cols, cell=args.cell,
        ),
        x_axis=x_axis,
        y_axis=y_axis,
        section=args.section,
        prominence=prominence,
        order=args.order,
        parent=args.parent,
        key_message=args.key_message,
        meta=Meta(
            method="external_figure",
            method_version=args.method_version,
            author=args.author,
            drs=args.drs,
            citation=args.citation,
            params={"method_note": args.method_note, "source": args.source, "original_file": src.name},
        ),
        status=args.status,
    )

    try:
        out = write_panel(panel, site_dir / "panels")
    except Exception as e:  # jsonschema.ValidationError, mostly
        msg = getattr(e, "message", str(e))
        where = "/".join(str(p) for p in getattr(e, "path", []))
        return _fail(f"panel didn't validate{' at ' + where if where else ''}: {msg}")

    print(f"copied  {src} -> site/{asset_rel}")
    print(f"wrote   {out}")
    print("next:   python scripts/validate_panel.py   (checks section/parent/file too), then open a PR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
