"""
from_series.py: turn an ALREADY-COMPUTED series into a dashboard panel.

Use this when your analysis is done elsewhere (a notebook, FaIR, Excel, your
own code) and you just want it on the dashboard as a chart. You give it the
finished x/y series plus a few descriptive fields; it writes a schema-valid
PanelArtifact JSON to <out-dir>/<forcing_type>/<panel_id>.json using the same
write_panel() every other method script uses. From there the flow is the
usual one: validate, open a PR, CI publishes.

Supported chart types here: line, scatter, sparkline (all take one x series
and one y series). Band, bar_breakdown and zonal_height_heatmap need
different data shapes and are not handled by this generic script yet.

Input can be:
  * CSV/TSV  -> --x-col / --y-col are column names
  * NetCDF   -> --x-col / --y-col are 1-D variable/coordinate names
                (needs xarray + netcdf4 installed)

Example:
    python methods/generic/from_series.py \\
        --input my_fair_erf.csv --x-col year --y-col erf_co2 \\
        --forcing-type ghg --panel-id co2_erf_fair --title "CO2 ERF (FaIR)" \\
        --x-label Year --x-unit CE --y-label ERF --y-unit "W m-2" \\
        --analysis-level model_response --comparison-group co2_erf_estimates \\
        --method-note "FaIR v2.1 default config, historical run" \\
        --source "Own FaIR run, config in repo X" --author ece

Because the calculation happens outside this repo, the panel cannot carry the
code that produced it. That is why --method-note and --source are required:
they are what makes the panel traceable later.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path

from feoc_panels import write_panel, parse_drs, PRODUCTION_READY_ERAS
from feoc_panels.contract import PanelArtifact, AxisSpec, Meta

try:
    import jsonschema
except ImportError:  # write_panel() itself requires it, so this is just for
    # a nicer error message if it's somehow missing when this script imports.
    jsonschema = None

SUPPORTED_CHART_TYPES = ["line", "scatter", "sparkline"]

# Mirrors schema/panel.schema.json's pattern for panel_id/comparison_group
# (^[a-z0-9][a-z0-9_-]*$) plus its length bounds, checked here so a bad value
# is reported in plain language instead of surfacing as a raw
# jsonschema.ValidationError out of write_panel().
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _to_number(raw, col: str, row: int) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Row {row}, column {col!r}: {raw!r} is not a number")
    if math.isnan(v) or math.isinf(v):
        raise ValueError(
            f"Row {row}, column {col!r}: NaN/inf cannot be stored in the panel JSON. "
            "Drop or fill those rows first."
        )
    return v


def _tidy(values: list[float]) -> list:
    """Keep whole numbers as ints (years etc.) so the JSON stays readable."""
    if all(float(v).is_integer() for v in values):
        return [int(v) for v in values]
    return values


def _check_slug(value: str, field_name: str, *, min_len: int = 1, max_len: int = 80) -> None:
    if not (min_len <= len(value) <= max_len):
        raise ValueError(
            f"--{field_name} {value!r} must be {min_len}-{max_len} characters long."
        )
    if not SLUG_RE.match(value):
        raise ValueError(
            f"--{field_name} {value!r} must start with a lowercase letter or digit "
            "and contain only lowercase letters, digits, '_' and '-' "
            "(this is what the dashboard schema requires)."
        )


def read_csv(path: Path, x_col: str, y_col: str) -> tuple[list[float], list[float]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        missing = [c for c in (x_col, y_col) if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f"Column(s) {missing} not found. Available columns: {reader.fieldnames}"
            )
        xs, ys = [], []
        for i, row in enumerate(reader, start=2):  # header is row 1
            xs.append(_to_number(row[x_col], x_col, i))
            ys.append(_to_number(row[y_col], y_col, i))
    return xs, ys


def read_netcdf(path: Path, x_col: str, y_col: str) -> tuple[list[float], list[float]]:
    try:
        import xarray as xr
    except ImportError:
        raise RuntimeError(
            "Reading NetCDF needs xarray and netcdf4 (pip install xarray netcdf4)."
        )
    with xr.open_dataset(path) as ds:
        for name in (x_col, y_col):
            if name not in ds.variables:
                raise ValueError(
                    f"{name!r} not found in {path.name}. Available: {list(ds.variables)}"
                )
        x = ds[x_col].values
        y = ds[y_col].values
        if x.ndim != 1 or y.ndim != 1:
            raise ValueError(
                f"Both variables must be 1-D (got {x.ndim}-D and {y.ndim}-D). "
                "Reduce to a series first (e.g. global mean), then re-run."
            )
        xs = [_to_number(v, x_col, i) for i, v in enumerate(x.tolist(), start=0)]
        ys = [_to_number(v, y_col, i) for i, v in enumerate(y.tolist(), start=0)]
    return xs, ys


def load_series(path: Path, x_col: str, y_col: str) -> tuple[list[float], list[float]]:
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv"):
        xs, ys = read_csv(path, x_col, y_col)
    elif suffix in (".nc", ".nc4", ".netcdf"):
        xs, ys = read_netcdf(path, x_col, y_col)
    else:
        raise ValueError(f"Unsupported input type {suffix!r}. Use .csv, .tsv or .nc")

    if len(xs) != len(ys):
        raise ValueError(f"x and y lengths differ ({len(xs)} vs {len(ys)})")
    if len(xs) < 2:
        raise ValueError("Need at least 2 points to draw a series")
    return xs, ys


def build_panel(args: argparse.Namespace) -> PanelArtifact:
    # Pre-check everything the JSON Schema will also check, so a bad value is
    # reported in plain language here rather than as a jsonschema traceback
    # out of write_panel(). (write_panel() still validates for real — this is
    # just for a better error message on the common mistakes.)
    _check_slug(args.panel_id, "panel-id", min_len=3, max_len=80)
    if not (3 <= len(args.title) <= 120):
        raise ValueError(f"--title must be 3-120 characters long, got {len(args.title)}.")
    if args.subtitle is not None and len(args.subtitle) > 200:
        raise ValueError(f"--subtitle must be at most 200 characters, got {len(args.subtitle)}.")
    if args.comparison_group is not None:
        _check_slug(args.comparison_group, "comparison-group")
    if (args.baseline_start is None) != (args.baseline_end is None):
        raise ValueError("Give both --baseline-start and --baseline-end, or neither.")

    xs, ys = load_series(Path(args.input), args.x_col, args.y_col)
    # Sort by x so the chart never draws a zig-zag from unordered input.
    pairs = sorted(zip(xs, ys), key=lambda p: p[0])
    xs = _tidy([p[0] for p in pairs])
    ys = [p[1] for p in pairs]

    drs = mip_era = production_ready = None
    if args.drs:
        drs = parse_drs(args.drs)
        mip_era = drs.mip_era
        production_ready = mip_era in PRODUCTION_READY_ERAS

    baseline = (
        [args.baseline_start, args.baseline_end]
        if args.baseline_start is not None
        else None
    )

    return PanelArtifact(
        panel_id=args.panel_id,
        title=args.title,
        subtitle=args.subtitle,
        forcing_type=args.forcing_type,
        chart_type=args.chart_type,
        analysis_level=args.analysis_level,
        comparison_group=args.comparison_group,
        x_axis=AxisSpec(label=args.x_label, unit=args.x_unit),
        y_axis=AxisSpec(label=args.y_label, unit=args.y_unit),
        color_role=args.forcing_type,
        data={"x": xs, "y": ys},
        meta=Meta(
            method="precomputed",
            method_version=args.method_version,
            author=args.author,
            drs=str(drs) if drs else None,
            mip_era=mip_era,
            production_ready=production_ready,
            baseline_period=baseline,
            params={
                "method_note": args.method_note,
                "source": args.source,
                "input_file": Path(args.input).name,
            },
            citation=args.citation,
        ),
        status=args.status,
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--input", required=True, help="CSV/TSV or NetCDF file with the ready series.")
    ap.add_argument("--x-col", required=True, help="Column / variable name for x.")
    ap.add_argument("--y-col", required=True, help="Column / variable name for y.")

    ap.add_argument("--forcing-type", required=True, choices=["ghg", "volcanic"])
    ap.add_argument("--panel-id", required=True, help="Unique id, lowercase_with_underscores, 3-80 chars.")
    ap.add_argument("--title", required=True, help="3-120 characters.")
    ap.add_argument("--subtitle", default=None, help="At most 200 characters.")
    ap.add_argument("--chart-type", default="line", choices=SUPPORTED_CHART_TYPES)

    ap.add_argument("--x-label", required=True)
    ap.add_argument("--x-unit", required=True)
    ap.add_argument("--y-label", required=True)
    ap.add_argument("--y-unit", required=True)

    ap.add_argument(
        "--analysis-level",
        required=True,
        choices=["forcing_input", "model_response"],
        help="forcing_input = the dataset itself; model_response = a model's output.",
    )
    ap.add_argument(
        "--comparison-group",
        default=None,
        help="Panels sharing this value are meant to be compared, e.g. co2_erf_estimates.",
    )

    # Provenance: required because the computation lives outside this repo.
    ap.add_argument("--method-note", required=True, help="One or two sentences: how was this series produced?")
    ap.add_argument("--source", required=True, help="Where it comes from: repo, run id, notebook, paper.")
    ap.add_argument("--author", required=True)
    ap.add_argument("--citation", default=None, help="Reference string, if there is a paper/dataset to cite.")
    ap.add_argument("--method-version", default="0.1.0")
    ap.add_argument("--drs", default=None, help="input4MIPs DRS string, if the series derives from one dataset.")
    ap.add_argument("--baseline-start", type=int, default=None)
    ap.add_argument("--baseline-end", type=int, default=None)

    ap.add_argument("--status", default="draft", choices=["draft", "published"])
    ap.add_argument("--out-dir", default="site/panels")
    args = ap.parse_args()

    try:
        panel = build_panel(args)
        out = write_panel(panel, out_dir=args.out_dir)
    except (ValueError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        # Safety net: catches any schema violation the pre-checks above don't
        # already cover (jsonschema.ValidationError isn't a ValueError, so it
        # would otherwise surface as a raw traceback here).
        if jsonschema is not None and isinstance(e, jsonschema.ValidationError):
            loc = "/".join(str(p) for p in e.path) or "(top level)"
            print(f"error: schema violation at {loc}: {e.message}", file=sys.stderr)
            return 1
        raise

    print(f"wrote {out}")
    print("next: python scripts/validate_panel.py, then open a PR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
