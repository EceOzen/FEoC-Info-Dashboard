#!/usr/bin/env python3
"""
Volcanic stratospheric aerosol optical depth (SAOD) from native CMIP
aerosol fields.

Owner: Dominik Stiller (panels/volcanic/* — see CODEOWNERS)

What this script does
----------------------
The native CMIP volcanic aerosol dataset is a 3D field on
(latitude, altitude, time) — NOT a ready-made global SAOD time series.
This script reduces that field down to two panel types:

  1. "saod_global_mean" (chart_type=line, with confidence_regime):
     a single global-mean SAOD time series, integrating over altitude and
     area-weighting over latitude. Confidence differs by era: pre-1979 is
     derived from a reduced-complexity model (EVA-H) run on ice-core-based
     SO2 emissions; 1979-onward is satellite-derived (GloSSAC). That's a
     real change in data provenance, not a stylistic choice, so it's
     recorded via confidence_regime rather than glossed over.

  2. "saod_zonal_height" (chart_type=zonal_height_heatmap):
     the (latitude, altitude) cross-section at a single eruption's peak,
     which is what the reduced global-mean panel above necessarily throws
     away (a tropical eruption and a high-latitude eruption with the same
     global-mean SAOD can have very different radiative effects).

Major eruptions annotated: Krakatau (1883), Katmai (1912), Agung (1963),
El Chichon (1982), Pinatubo (1991) — the standard reference set used in
the CMIP7 volcanic forcing evaluation papers.

How to run
----------
    python methods/volcanic/saod_zonal_reduction.py \\
        --data-ref /path/or/url/to/aerosol_properties.nc \\
        --drs "input4MIPs.CMIP7.CMIP.UOEXETER.UOEXETER-CMIP-1-1-3.atmos.mon.saod.gn" \\
        --out-dir site/panels \\
        --author your.github.handle

Writes TWO panels to site/panels/volcanic/. Open a PR with the new JSON
files — do not hand-edit JSON files created by someone else's run.
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

# Standard reference eruption set used across CMIP7 volcanic forcing papers.
ERUPTIONS = [
    {"year": 1883, "label": "Krakatau", "amp": 0.11, "sigma": 2.0},
    {"year": 1912, "label": "Katmai", "amp": 0.06, "sigma": 1.8},
    {"year": 1963, "label": "Agung", "amp": 0.075, "sigma": 2.0},
    {"year": 1982, "label": "El Chichón", "amp": 0.09, "sigma": 1.6},
    {"year": 1991, "label": "Pinatubo", "amp": 0.15, "sigma": 2.2, "flagged": True},
]

# Real CMIP7-vs-CMIP6 reference figures (Jorimann et al. 2026, GMD), used
# only to keep the stub's synthetic output in the right ballpark:
# 1850-2014 mean global SAOD: CMIP6 = 0.0107, CMIP7 = 0.0138 (+29%).
_SAOD_BACKGROUND = 0.003

# The satellite era begins in 1979 (GloSSAC); everything before that in the
# CMIP7 dataset is derived from the EVA-H reduced-complexity model driven by
# ice-core-based SO2 emission inventories.
SATELLITE_ERA_START = 1979


def _load_aerosol_field(data_ref: str):
    """
    STUB: replace with the real data access.

    Real implementation should open the native (latitude, altitude, time)
    field (e.g. the H2SO4_mass or extinction-coefficient variable) with
    feoc_panels.io.open_lazy(), then:
      - for the global-mean panel: area-weight over latitude and integrate
        over altitude to get SAOD(time)
      - for the zonal-height panel: select a single time slice (an
        eruption's peak month) and return the (latitude, altitude) grid
        as-is, no reduction

    Left as a stub with synthetic output (matching real eruption timing
    and roughly the right SAOD magnitude) so this script is runnable
    end-to-end before the real data plumbing is wired in.
    """
    years = list(range(1850, 2025, 2))
    saod = []
    for y in years:
        v = _SAOD_BACKGROUND
        for e in ERUPTIONS:
            d = (y - e["year"]) / e["sigma"]
            v += e["amp"] * math.exp(-d * d)
        saod.append(round(v, 5))

    # Synthetic (latitude, altitude) grid for the Pinatubo peak, just to
    # exercise the zonal_height_heatmap chart_type end to end.
    lats = list(range(-90, 91, 10))
    alts = list(range(15, 31, 1))  # km, stratosphere
    grid = []
    for alt in alts:
        row = []
        for lat in lats:
            # Peaks near the equator and ~20-25km, tapering with latitude
            # and altitude distance — illustrative only.
            lat_factor = math.exp(-((lat / 35.0) ** 2))
            alt_factor = math.exp(-(((alt - 22) / 5.0) ** 2))
            row.append(round(0.15 * lat_factor * alt_factor, 5))
        grid.append(row)

    return years, saod, lats, alts, grid


def build_global_mean_panel(
    data_ref: str,
    drs_string: str | None,
    author: str,
) -> PanelArtifact:
    years, saod, *_ = _load_aerosol_field(data_ref)

    drs = None
    mip_era = None
    production_ready = None
    citation_key = "volcanic_cmip6"
    if drs_string:
        drs = parse_drs(drs_string)
        mip_era = drs.mip_era
        production_ready = mip_era in PRODUCTION_READY_ERAS
        if mip_era in ("CMIP7", "CMIP7Plus"):
            citation_key = "volcanic_cmip7"

    annotations = [
        {"x": e["year"], "label": e["label"], "style": "eruption"}
        for e in ERUPTIONS
    ]

    confidence_regime = [
        {
            "from": years[0],
            "to": SATELLITE_ERA_START - 1,
            "label": "Model-derived (EVA-H, ice-core SO2 emissions)",
        },
        {
            "from": SATELLITE_ERA_START,
            "to": years[-1],
            "label": "Satellite-derived (GloSSAC)",
        },
    ]

    return PanelArtifact(
        panel_id="saod_global_mean",
        title="Volcanic stratospheric aerosol optical depth (global mean)",
        subtitle="Major eruptions annotated; provenance differs before/after 1979",
        forcing_type="volcanic",
        chart_type="line",
        analysis_level="forcing_input",
        x_axis=AxisSpec(label="Year", unit="CE"),
        y_axis=AxisSpec(label="SAOD", unit="dimensionless", domain=[0, 0.2]),
        color_role="volcanic",
        annotations=annotations,
        confidence_regime=confidence_regime,
        data={"x": years, "y": saod},
        meta=Meta(
            method="saod_global_mean_reduction",
            method_version="0.1.0",
            author=author,
            drs=str(drs) if drs else None,
            mip_era=mip_era,
            production_ready=production_ready,
            citation=CITATIONS.get(citation_key),
        ),
        status="draft",
    )


def build_zonal_height_panel(
    data_ref: str,
    drs_string: str | None,
    author: str,
    eruption_label: str = "Pinatubo",
) -> PanelArtifact:
    _, _, lats, alts, grid = _load_aerosol_field(data_ref)

    drs = None
    mip_era = None
    production_ready = None
    if drs_string:
        drs = parse_drs(drs_string)
        mip_era = drs.mip_era
        production_ready = mip_era in PRODUCTION_READY_ERAS

    return PanelArtifact(
        panel_id=f"saod_zonal_height_{eruption_label.lower()}",
        title=f"Aerosol extinction, latitude–altitude cross-section ({eruption_label} peak)",
        subtitle="What the global-mean SAOD series necessarily discards",
        forcing_type="volcanic",
        chart_type="zonal_height_heatmap",
        analysis_level="forcing_input",
        x_axis=AxisSpec(label="Latitude", unit="degrees"),
        y_axis=AxisSpec(label="Altitude", unit="km"),
        color_role="volcanic",
        data={"lat": lats, "alt": alts, "grid": grid},
        meta=Meta(
            method="saod_zonal_height_slice",
            method_version="0.1.0",
            author=author,
            drs=str(drs) if drs else None,
            mip_era=mip_era,
            production_ready=production_ready,
            params={"eruption": eruption_label},
            citation=CITATIONS.get("volcanic_cmip7"),
        ),
        status="draft",
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-ref", required=True, help="Path/glob/URL to the input4MIPs aerosol field.")
    ap.add_argument("--drs", default=None, help="Full input4MIPs DRS string for provenance (recommended).")
    ap.add_argument("--out-dir", default="site/panels")
    ap.add_argument("--author", required=True)
    ap.add_argument(
        "--panels",
        choices=["global_mean", "zonal_height", "both"],
        default="both",
    )
    args = ap.parse_args()

    if args.panels in ("global_mean", "both"):
        panel = build_global_mean_panel(args.data_ref, args.drs, args.author)
        print(f"wrote {write_panel(panel, out_dir=args.out_dir)}")

    if args.panels in ("zonal_height", "both"):
        panel = build_zonal_height_panel(args.data_ref, args.drs, args.author)
        print(f"wrote {write_panel(panel, out_dir=args.out_dir)}")


if __name__ == "__main__":
    main()
