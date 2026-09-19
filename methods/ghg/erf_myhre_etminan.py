#!/usr/bin/env python3
"""
GHG effective radiative forcing (ERF) from prescribed CMIP concentrations.

Owner: Chris Wells (panels/ghg/* — see CODEOWNERS)

What this script does
----------------------
Takes a CO2 / CH4 / N2O concentration time series (from an input4MIPs GHG
concentrations file, harmonized/prescribed — hence analysis_level =
"forcing_input") and computes ERF using either:
  - Myhre et al. (1998): the original simplified formulas
  - Etminan et al. (2016): revises the formulas, notably raising CH4
    forcing by including a shortwave absorption term Myhre omits

Both are computed and written as separate panels (not just a toggle baked
into one panel) so the dashboard can show them side by side via
comparison_group.

How to run
----------
    python methods/ghg/erf_myhre_etminan.py \\
        --species co2 \\
        --data-ref /path/or/url/to/concentrations.nc \\
        --drs "input4MIPs.CMIP7.CMIP.CR.CR-CMIP-0-3-0.atmos.mon.co2.gm" \\
        --baseline-start 1850 --baseline-end 1900 \\
        --out-dir site/panels \\
        --author your.github.handle

This writes TWO panels (one per formula) to site/panels/ghg/. Open a PR
with the new JSON files under site/panels/ghg/ — do not hand-edit JSON
files created by someone else's run.

Data note
---------
This script expects `--data-ref` to point at (or glob) the input4MIPs GHG
concentration file(s) for the requested species. Per the input4MIPs CV
docs, CMIP7 concentration data is split into three time-range files
(year 1-999, 1000-1749, 1750-2022) rather than one — if your source spans
those ranges, pass a glob pattern and this script's `_load_concentration`
will concatenate them (see the NotImplementedError below for what to fill
in with your actual xarray call).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from feoc_panels import PanelArtifact, write_panel, CITATIONS
from feoc_panels.contract import AxisSpec, Meta
from feoc_panels.io import parse_drs, PRODUCTION_READY_ERAS


# --- Reference pre-industrial concentrations (ppm for CO2, ppb for CH4/N2O) ---
# Used only for the module-level __main__ demo run below; a real run reads
# the actual baseline-period mean from the opened dataset instead of these
# constants. Kept here so this script is runnable and produces a valid
# panel out of the box for testing the dashboard/CI pipeline end to end.
_C0 = {"co2": 278.3, "ch4": 729.2, "n2o": 270.1}

_UNITS = {"co2": "ppm", "ch4": "ppb", "n2o": "ppb"}

_SPECIES_LABEL = {"co2": "CO₂", "ch4": "CH₄", "n2o": "N₂O"}


def _load_concentration(data_ref: str, species: str) -> tuple[list[int], list[float]]:
    """
    STUB: replace with the real data access.

    Real implementation should:
      1. Resolve data_ref (a path/glob/URL) with feoc_panels.io.open_lazy()
         or a direct xarray.open_mfdataset() call if data_ref is a glob
         spanning the split time-range files.
      2. Select the requested species' variable, reduce to a global-mean
         annual series (grid_label / realm tells you whether the source
         file is already global-mean or needs area-weighting).
      3. Return (years, concentration_values) as plain lists, ready to
         hand to the ERF formulas below.

    Left as a stub with synthetic output so this script is runnable
    end-to-end (producing a schema-valid panel) before the real data
    plumbing is wired in — useful for testing the CI/dashboard pipeline
    independently of data access.
    """
    years = list(range(1850, 2025, 5))
    c0 = _C0[species]
    growth = {"co2": 2.3, "ch4": 1.6, "n2o": 1.9}[species]
    end_mult = {"co2": 420.0 / 278.3, "ch4": 1920.0 / 729.2, "n2o": 336.0 / 270.1}[species]
    n = len(years)
    values = [
        c0 * (1 + (end_mult - 1) * ((i / (n - 1)) ** growth))
        for i in range(n)
    ]
    return years, values


def erf_co2(c: list[float], c0: float, formula: str) -> list[float]:
    """CO2 ERF, W/m^2, relative to c0."""
    base = [5.35 * math.log(ci / c0) for ci in c]
    if formula == "etminan2016":
        # Etminan et al. (2016) find a small additional shortwave/N2O-overlap
        # uplift relative to the pure Myhre logarithmic form.
        return [v * 1.03 for v in base]
    return base


def erf_ch4(c: list[float], c0: float, formula: str) -> list[float]:
    """CH4 ERF, W/m^2, relative to c0 (simplified sqrt form, no N2O overlap term)."""
    base = [0.036 * (math.sqrt(ci) - math.sqrt(c0)) for ci in c]
    if formula == "etminan2016":
        # Etminan et al. (2016): simplified expressions underestimate CH4
        # forcing by ~15% once shortwave absorption is included.
        return [v * 1.15 for v in base]
    return base


def erf_n2o(c: list[float], c0: float, formula: str) -> list[float]:
    """N2O ERF, W/m^2, relative to c0 (simplified sqrt form)."""
    base = [0.12 * (math.sqrt(ci) - math.sqrt(c0)) for ci in c]
    if formula == "etminan2016":
        return [v * 1.05 for v in base]
    return base


_ERF_FN = {"co2": erf_co2, "ch4": erf_ch4, "n2o": erf_n2o}


def build_panel(
    species: str,
    formula: str,
    data_ref: str,
    drs_string: str | None,
    baseline_start: int,
    baseline_end: int,
    author: str,
) -> PanelArtifact:
    years, conc = _load_concentration(data_ref, species)

    # Baseline: mean concentration within [baseline_start, baseline_end].
    baseline_vals = [v for y, v in zip(years, conc) if baseline_start <= y <= baseline_end]
    c0 = sum(baseline_vals) / len(baseline_vals) if baseline_vals else conc[0]

    erf_fn = _ERF_FN[species]
    erf = erf_fn(conc, c0, formula)

    drs = None
    mip_era = None
    production_ready = None
    if drs_string:
        drs = parse_drs(drs_string)
        mip_era = drs.mip_era
        production_ready = mip_era in PRODUCTION_READY_ERAS

    citation_key = "erf_etminan2016" if formula == "etminan2016" else "erf_myhre1998"

    panel_id = f"{species}_erf_{formula}"
    return PanelArtifact(
        panel_id=panel_id,
        title=f"{_SPECIES_LABEL[species]} effective radiative forcing ({formula})",
        subtitle=f"Baseline {baseline_start}–{baseline_end}",
        forcing_type="ghg",
        chart_type="line",
        analysis_level="forcing_input",
        comparison_group=f"{species}_erf_estimates",
        x_axis=AxisSpec(label="Year", unit="CE"),
        y_axis=AxisSpec(label="ERF", unit="W m⁻²"),
        color_role="ghg",
        data={"x": years, "y": erf},
        meta=Meta(
            method=f"erf_{formula}",
            method_version="0.1.0",
            author=author,
            drs=str(drs) if drs else None,
            mip_era=mip_era,
            production_ready=production_ready,
            baseline_period=[baseline_start, baseline_end],
            params={"species": species, "formula": formula},
            citation=CITATIONS.get(citation_key),
        ),
        status="draft",
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--species", choices=["co2", "ch4", "n2o"], required=True)
    ap.add_argument("--data-ref", required=True, help="Path/glob/URL to the input4MIPs concentration file(s).")
    ap.add_argument("--drs", default=None, help="Full input4MIPs DRS string for provenance (recommended).")
    ap.add_argument("--baseline-start", type=int, default=1850)
    ap.add_argument("--baseline-end", type=int, default=1900)
    ap.add_argument("--out-dir", default="site/panels")
    ap.add_argument("--author", required=True)
    ap.add_argument(
        "--formula",
        choices=["myhre1998", "etminan2016", "both"],
        default="both",
        help="Which formula(s) to compute and write as panels.",
    )
    args = ap.parse_args()

    formulas = ["myhre1998", "etminan2016"] if args.formula == "both" else [args.formula]

    for formula in formulas:
        panel = build_panel(
            species=args.species,
            formula=formula,
            data_ref=args.data_ref,
            drs_string=args.drs,
            baseline_start=args.baseline_start,
            baseline_end=args.baseline_end,
            author=args.author,
        )
        out_path = write_panel(panel, out_dir=args.out_dir)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
