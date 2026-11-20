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

### Already have the finished figure?

If you already made the figure itself, `methods/generic/from_asset.py` puts
it on the dashboard as it is. It copies the file to
`site/assets/<forcing_type>/<panel_id>.<ext>` and writes the panel JSON next
to the others. The format is taken from the file extension.

| Format | Make it with | How the dashboard shows it |
|---|---|---|
| `.svg` `.png` `.webp` `.jpg` | `fig.savefig(...)` | Image that scales to the card (SVG stays sharp) |
| `.gif` | `PillowWriter` | Looping image |
| `.json` (Plotly) | `fig.write_json(...)` | Interactive chart (zoom, hover), drawn with plotly.js |
| `.html` | Bokeh `save()`, Folium `m.save()` | Sandboxed frame; scripts run, but can't touch the dashboard |
| `.mp4` `.webm` | `FFMpegWriter` | Muted, looping video with controls; optional `--poster` |
| `.pdf` | paper figure | Preview image (CI renders page 1) that opens the full PDF |
| `.csv` `.tsv` | any | The dashboard draws it itself: `--csv-x/--csv-y`, plus `--csv-lo/--csv-hi` for a band |
| `.ipynb` | Jupyter, **saved with outputs** | The figure outputs, with a "show the code" fold |

```bash
python methods/generic/from_asset.py --input saod_map.svg \
    --forcing-type volcanic --panel-id saod_pinatubo_map \
    --title "Stratospheric aerosol after Pinatubo" \
    --alt-text "Map of stratospheric aerosol optical depth in 1992, highest in the tropics" \
    --section volcanic --prominence headline \
    --key-message "Pinatubo's aerosol veil covered the whole tropics within months." \
    --analysis-level forcing_input \
    --method-note "Plotted from GloSSAC v2.2, notebook X commit abc123" \
    --source "github.com/you/repo" --author your-handle
```

`--alt-text` is required for every format: it is what screen readers read
and what shows if the file can't load. CI checks the file exists, sits under
`site/assets/`, matches its format and stays under a size cap (5 MB images,
10 MB Plotly/HTML/PDF/CSV/notebooks, 25 MB video).

To see one example of every format on your own machine:

```bash
python examples/make_asset_examples.py        # synthetic, status=draft
python scripts/build_manifest.py --include-drafts && python scripts/build_assets.py
cd site && python3 -m http.server 8000
python examples/make_asset_examples.py --clean   # remove them again
```

To show the examples on the live dashboard (say, for a demo), run it with
`--publish`, then commit and push the new files under `site/panels/` and
`site/assets/`. Take them down with `--clean` and push the deletion.

## Where a panel sits on the page

The dashboard is organised as a story, not a gallery. Every panel can say
where it belongs:

- **`section`**: which part of the story it belongs to. Sections and their
  short intro texts are listed, in order, in `site/sections.json`. To add a
  section, add it there in the same PR.
- **`prominence`**:
  - `headline`: the lead figure of the section, full width. Ideally one per section.
  - `primary`: a normal card. This is the default.
  - `supporting`: extra detail, folded away until the reader opens it.
- **`parent`** (supporting panels only): the panel it adds detail to. It is
  then folded inside that panel's card. Supporting panels without a parent
  fold together at the end of their section.
- **`order`**: position inside the section, lower first (default 100).
- **`key_message`**: one plain-language sentence shown above the chart.
  Write it for someone who doesn't know what ERF is.

All of these are optional, so older panels keep working. A panel without a
`section` shows at the end under "More panels". CI checks that sections and
parents exist and that a parent isn't itself a supporting panel.

## Repo layout

| Path | What it is |
|---|---|
| `schema/panel.schema.json` | The PanelArtifact contract — the single source of truth for what a panel JSON must contain. |
| `feoc_panels/` | Shared Python library: `PanelArtifact` dataclass, `write_panel()`, `validate()`, DRS parsing, citations. Import from here — don't re-implement. |
| `methods/ghg/` | GHG method scripts. (see `.github/CODEOWNERS`). |
| `methods/volcanic/` | Volcanic method scripts. |
| `methods/generic/from_series.py` | For a series already computed outside this repo — wraps it into a valid panel without writing a method script. See "Already have a computed series?" above. |
| `methods/generic/from_asset.py` | For a finished figure (image, Plotly, HTML, video, PDF, CSV, notebook). See "Already have the finished figure?" above. |
| `examples/make_asset_examples.py` | Generates one synthetic draft panel per asset format, for local preview and as copy-paste templates. |
| `scripts/build_assets.py` | Runs at deploy; renders PDF previews. |
| `site/sections.json` | The story sections, in display order, with their intro texts. |
| `site/assets/<ghg\|volcanic>/` | Files for `chart_type: "asset"` panels. |
| `scripts/validate_panel.py` | Runs in CI on every PR touching `site/panels/**`, `site/assets/**` or `site/sections.json`. |
| `scripts/build_manifest.py` | Runs in CI on merge to `main`; regenerates `site/manifest.json`. |
| `site/index.html` | The dashboard itself — a single static HTML file, no build step, no framework (plotly.js is loaded from its CDN only when a Plotly panel is on the page). |
| `site/panels/<ghg\|volcanic>/` | Where panel JSON files live. |
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
- `methods/generic/from_asset.py` and the twelve asset formats — each rendered and checked in a browser (desktop and phone width) with the synthetic examples.
- Sections / prominence / parent layout, including the folded supporting panels.

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
