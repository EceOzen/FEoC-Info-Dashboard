#!/usr/bin/env python3
"""
PR-time validation for panel JSON files under site/panels/.

Runs two layers of checks:
  1. JSON Schema validation (schema/panel.schema.json) — structure, enums,
     required fields.
  2. Checks the schema can't express: panel_id uniqueness across the whole
     repo, panel_id matching its filename, forcing_type matching its
     directory, chart_type-specific data-shape checks, and a size cap so
     nobody accidentally commits a multi-hundred-MB JSON.

Exits non-zero (failing the PR check) on any problem, printing every
problem found rather than stopping at the first one.

Usage:
    python scripts/validate_panel.py                  # validate everything under site/panels/
    python scripts/validate_panel.py path/to/one.json  # validate just this file
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from feoc_panels.contract import validate as schema_validate
import jsonschema

PANELS_DIR = REPO_ROOT / "site" / "panels"
MAX_PANEL_BYTES = 2 * 1024 * 1024  # 2 MB — panels hold plotting-ready series, not raw data


def find_panel_files(paths: list[str] | None) -> list[Path]:
    if paths:
        return [Path(p) for p in paths]
    return sorted(PANELS_DIR.rglob("*.json"))


def check_size(path: Path, errors: list[str]) -> None:
    size = path.stat().st_size
    if size > MAX_PANEL_BYTES:
        errors.append(
            f"{path}: file is {size / 1024 / 1024:.1f} MB, exceeds the "
            f"{MAX_PANEL_BYTES / 1024 / 1024:.0f} MB cap. Panels hold "
            f"plotting-ready series, not raw/native data — if your series "
            f"is legitimately this large, downsample before writing the "
            f"panel, or raise this in review before changing the cap."
        )


def check_filename_matches_id(path: Path, panel: dict, errors: list[str]) -> None:
    expected_stem = panel.get("panel_id", "")
    if path.stem != expected_stem:
        errors.append(
            f"{path}: filename stem {path.stem!r} does not match "
            f"panel_id {expected_stem!r}. write_panel() names the file "
            f"after panel_id automatically — don't rename after the fact."
        )


def check_directory_matches_forcing_type(path: Path, panel: dict, errors: list[str]) -> None:
    forcing_type = panel.get("forcing_type")
    parent_dir = path.parent.name
    if forcing_type != parent_dir:
        errors.append(
            f"{path}: forcing_type={forcing_type!r} but file lives under "
            f"site/panels/{parent_dir}/. Move it under "
            f"site/panels/{forcing_type}/ or fix forcing_type."
        )


def check_chart_type_data_shape(path: Path, panel: dict, errors: list[str]) -> None:
    """
    JSON Schema deliberately leaves `data`'s internal shape open (it varies
    by chart_type). Enforce the shapes the dashboard's renderers actually
    expect here instead.
    """
    chart_type = panel.get("chart_type")
    data = panel.get("data", {})

    if chart_type in ("line", "band", "scatter", "sparkline"):
        if "x" not in data or "y" not in data:
            errors.append(f"{path}: chart_type={chart_type!r} requires data.x and data.y arrays.")
        elif len(data.get("x", [])) != len(data.get("y", [])):
            errors.append(
                f"{path}: data.x has {len(data['x'])} points but data.y has "
                f"{len(data['y'])} — must be equal length."
            )
        if chart_type == "band":
            unc = panel.get("uncertainty")
            if not unc:
                errors.append(f"{path}: chart_type='band' but no top-level 'uncertainty' block is set.")
            elif len(unc.get("lo", [])) != len(data.get("x", [])) or len(unc.get("hi", [])) != len(data.get("x", [])):
                errors.append(f"{path}: uncertainty.lo/hi length must match data.x length.")

    elif chart_type == "bar_breakdown":
        required = {"categories", "values"}
        missing = required - data.keys()
        if missing:
            errors.append(f"{path}: chart_type='bar_breakdown' missing data keys: {sorted(missing)}.")
        elif len(data["categories"]) != len(data["values"]):
            errors.append(f"{path}: data.categories and data.values must be equal length.")

    elif chart_type == "zonal_height_heatmap":
        required = {"lat", "alt", "grid"}
        missing = required - data.keys()
        if missing:
            errors.append(f"{path}: chart_type='zonal_height_heatmap' missing data keys: {sorted(missing)}.")
        else:
            n_alt, n_lat = len(data["alt"]), len(data["lat"])
            grid = data["grid"]
            if len(grid) != n_alt or any(len(row) != n_lat for row in grid):
                errors.append(
                    f"{path}: data.grid must be shape [len(alt)][len(lat)] = "
                    f"[{n_alt}][{n_lat}], got {len(grid)} rows."
                )


def check_uniqueness_and_status(
    path: Path,
    panel: dict,
    seen_ids: dict[str, Path],
    errors: list[str],
) -> None:
    panel_id = panel.get("panel_id")
    if panel_id in seen_ids and seen_ids[panel_id] != path:
        errors.append(
            f"{path}: panel_id {panel_id!r} is already used by "
            f"{seen_ids[panel_id]} — panel_id must be unique across the "
            f"whole repo. If this intentionally replaces the other panel, "
            f"set 'supersedes' and mark the old one status='deprecated' "
            f"instead of reusing its id."
        )
    else:
        seen_ids[panel_id] = path

    supersedes = panel.get("supersedes")
    if supersedes and supersedes not in seen_ids and not any(
        json.loads(p.read_text()).get("panel_id") == supersedes
        for p in PANELS_DIR.rglob("*.json")
    ):
        errors.append(
            f"{path}: supersedes={supersedes!r} but no panel with that "
            f"panel_id exists in the repo."
        )


def main():
    paths = find_panel_files(sys.argv[1:] if len(sys.argv) > 1 else None)
    if not paths:
        print("No panel JSON files found under site/panels/. Nothing to validate.")
        return 0

    errors: list[str] = []
    seen_ids: dict[str, Path] = {}

    for path in paths:
        check_size(path, errors)
        try:
            panel = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"{path}: invalid JSON ({e})")
            continue

        try:
            schema_validate(panel)
        except jsonschema.ValidationError as e:
            errors.append(f"{path}: schema violation at {'/'.join(str(p) for p in e.path)}: {e.message}")
            continue  # further structural checks assume a schema-valid panel

        check_filename_matches_id(path, panel, errors)
        check_directory_matches_forcing_type(path, panel, errors)
        check_chart_type_data_shape(path, panel, errors)
        check_uniqueness_and_status(path, panel, seen_ids, errors)

    if errors:
        print(f"FAILED: {len(errors)} problem(s) found across {len(paths)} panel file(s):\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: {len(paths)} panel file(s) validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
