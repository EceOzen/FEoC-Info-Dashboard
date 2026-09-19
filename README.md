# FEoC Forcing Evaluation Dashboard — skeleton

Status: **early skeleton**, not yet wired to real CMIP data. This repo is
the "script → PR → dashboard" pipeline discussed in the FEoC design doc,
implemented enough to run end to end with synthetic data.

## How it fits together

```
methods/ghg/*.py, methods/volcanic/*.py   <- you run these locally
methods/generic/from_series.py            <- or this, if your series is already computed
              |
              v  writes
site/panels/<forcing_type>/<panel_id>.json    <- one file per panel, the PanelArtifact contract
              |
              v  PR + merge
scripts/validate_panel.py  (CI, on every PR)   <- schema + structural checks, blocks bad merges
scripts/build_manifest.py  (CI, on merge to main) <- indexes published panels into site/manifest.json
              |
              v  GitHub Pages deploy
site/index.html   <- fetches manifest.json + each panel JSON, renders by chart_type
```

## Quick start

```bash
pip install -e .          # installs feoc_panels (the shared contract library)

# Generate a couple of real panels (currently synthetic data — see the
# _load_concentration / _load_aerosol_field stubs in each script):
python methods/ghg/erf_myhre_etminan.py \
    --species co2 --data-ref dummy.nc --author your-handle

python methods/volcanic/saod_zonal_reduction.py \
    --data-ref dummy.nc --author your-handle

# Check everything validates:
python scripts/validate_panel.py

# Preview locally (panels are written with status="draft" by default,
# so build the manifest with --include-drafts to see them):
python scripts/build_manifest.py --include-drafts
cd site && python3 -m http.server 8000
# open http://localhost:8000
```

To actually publish a panel to the live dashboard, edit its JSON's
`"status"` field from `"draft"` to `"published"` before opening the PR —
`build_manifest.py`'s production run (no `--include-drafts`) only indexes
published panels.

### Already have a computed series?

If your analysis happened outside this repo (a notebook, FaIR, Excel, your
own code) and you just want the result on the dashboard, you don't need to
write a method script. `methods/generic/from_series.py` takes a ready x/y
series (CSV, TSV, or a 1-D NetCDF variable) and writes a schema-valid panel
directly, using the same `write_panel()` every method script uses:

```bash
python methods/generic/from_series.py \
    --input my_fair_erf.csv --x-col year --y-col erf_co2 \
    --forcing-type ghg --panel-id co2_erf_fair --title "CO2 ERF (FaIR)" \
    --x-label Year --x-unit CE --y-label ERF --y-unit "W m-2" \
    --analysis-level model_response --comparison-group co2_erf_estimates \
    --method-note "FaIR v2.1 default config, historical run" \
    --source "Own FaIR run, config in repo X" --author your-handle

python scripts/validate_panel.py
# then open a PR as usual
```

Supports `line`, `scatter` and `sparkline` chart types (one x series, one y
series). `band`, `bar_breakdown` and `zonal_height_heatmap` need a different
data shape and aren't handled by this script — write a method script for
those instead.

`--method-note` and `--source` are required, not optional: since the
computation happened outside this repo, they're the only record of how the
panel was produced. Write something a reviewer could actually check
("FaIR v2.1, default config, historical run, notebook X in repo Y commit
abc123"), not "computed elsewhere".

## Repo layout

| Path | What it is |
|---|---|
| `schema/panel.schema.json` | The PanelArtifact contract — the single source of truth for what a panel JSON must contain. |
| `feoc_panels/` | Shared Python library: `PanelArtifact` dataclass, `write_panel()`, `validate()`, DRS parsing, citations. Import from here — don't re-implement. |
| `methods/ghg/` | GHG method scripts. (see `.github/CODEOWNERS`). |
| `methods/volcanic/` | Volcanic method scripts. |
| `methods/generic/from_series.py` | For a series already computed outside this repo — wraps it into a valid panel without writing a method script. See "Already have a computed series?" above. |
| `scripts/validate_panel.py` | Runs in CI on every PR touching `site/panels/**`. |
| `scripts/build_manifest.py` | Runs in CI on merge to `main`; regenerates `site/manifest.json`. |
| `site/index.html` | The dashboard itself — a single static HTML file, no build step, no framework. |
| `site/panels/<ghg\|volcanic>/` | Where panel JSON files live. Currently empty except for `.gitkeep`. |
| `.github/workflows/` | `validate-panels.yml` (PR check) and `deploy-pages.yml` (deploy on merge). |
| `.github/CODEOWNERS` | Required-reviewer mapping — **replace the placeholder GitHub handles before this goes live.** |

## What's a stub vs. what's real

**Real and tested:**
- The full PanelArtifact contract (schema + Python dataclass), validated end to end.
- The GHG ERF formulas (Myhre 1998, Etminan 2016) — actual published formulas, not placeholders.
- CI validation logic (schema violations, panel_id collisions, chart_type-specific data-shape checks, size cap).
- The dashboard's six chart-type renderers (line, band, bar_breakdown, zonal_height_heatmap, scatter, sparkline) — all rendered and visually checked against synthetic data.
- The draft → published → manifest → dashboard flow.
- `methods/generic/from_series.py` — takes a ready series (CSV/TSV/NetCDF) and writes a valid panel; useful for anything computed outside this repo (e.g. FaIR runs).

**Stubs to fill in next (see docstrings in each file for exactly what's needed):**
- `feoc_panels/io.py::open_lazy()` — the actual xarray/dask data access.
- `methods/ghg/erf_myhre_etminan.py::_load_concentration()` — currently returns synthetic data shaped like real CO2/CH4/N2O growth; needs the real input4MIPs file read (note: CMIP7 concentration files are split into three time-range files per the input4MIPs CV docs).
- `methods/volcanic/saod_zonal_reduction.py::_load_aerosol_field()` — currently returns synthetic data; needs the real (latitude, altitude, time) field read and reduction.
- `.github/CODEOWNERS` — placeholder GitHub handles need to become real usernames.
- Dashboard interactivity is uneven: hover tooltips only exist on the `line` chart renderer in `site/index.html`. `band`, `bar_breakdown`, `scatter`, `zonal_height_heatmap` and `sparkline` are static SVG with no mouseover — worth extending once real volcanic panels (mostly `zonal_height_heatmap`) start landing.

See the design doc for the full architecture discussion, the CMIP research
findings behind specific contract fields (baseline periods, ensemble
variants, calendar handling, the CMIP6Plus "not for production" flag,
etc.), and the open decisions still on the table.
