"""
The PanelArtifact contract: a dataclass mirroring schema/panel.schema.json,
plus write_panel() (the only way a method script should produce a panel
JSON) and validate() (used both by write_panel() and by
scripts/validate_panel.py in CI).

Design note: this dataclass is intentionally permissive about *values* (it
does not, e.g., re-implement every enum check from the JSON Schema) — the
JSON Schema file is the single source of truth for what's valid, and
validate() defers to it. This class exists so method-script authors get
autocomplete and a typo-resistant constructor instead of hand-building a
dict, not to duplicate the schema.
"""

from __future__ import annotations

import json
import datetime as _dt
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

try:
    import jsonschema
except ImportError:  # pragma: no cover - jsonschema is a required dependency,
    # but we fail with a clear message rather than an ImportError deep in a
    # method script's traceback.
    jsonschema = None

SCHEMA_VERSION = "1.0.0"
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "panel.schema.json"


@dataclass
class AxisSpec:
    label: str
    unit: str
    scale: str = "linear"
    domain: Optional[list[float]] = None

    def to_dict(self) -> dict:
        d = {"label": self.label, "unit": self.unit, "scale": self.scale}
        if self.domain is not None:
            d["domain"] = self.domain
        return d


@dataclass
class Meta:
    method: str
    method_version: str
    author: str
    generated_at: str = field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc).isoformat())
    drs: Optional[str] = None
    mip_era: Optional[str] = None
    production_ready: Optional[bool] = None
    baseline_period: Optional[list[int]] = None
    variant: Optional[str] = None
    params: Optional[dict] = None
    citation: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class PanelArtifact:
    """
    Construct one of these in your method script, then call write_panel().
    See methods/ghg/erf_myhre_etminan.py for a worked example.
    """

    panel_id: str
    title: str
    forcing_type: str  # "ghg" | "volcanic"
    chart_type: str  # "line" | "band" | "bar_breakdown" | "zonal_height_heatmap" | "scatter" | "sparkline"
    analysis_level: str  # "forcing_input" | "model_response"
    x_axis: AxisSpec
    y_axis: AxisSpec
    data: dict
    meta: Meta
    status: str = "draft"  # "draft" | "published" | "deprecated" | "retracted"
    schema_version: str = SCHEMA_VERSION
    subtitle: Optional[str] = None
    comparison_group: Optional[str] = None
    supersedes: Optional[str] = None
    color_role: Optional[str] = None
    annotations: Optional[list[dict]] = None
    uncertainty: Optional[dict] = None
    confidence_regime: Optional[list[dict]] = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "schema_version": self.schema_version,
            "panel_id": self.panel_id,
            "title": self.title,
            "forcing_type": self.forcing_type,
            "chart_type": self.chart_type,
            "analysis_level": self.analysis_level,
            "x_axis": self.x_axis.to_dict(),
            "y_axis": self.y_axis.to_dict(),
            "data": self.data,
            "meta": self.meta.to_dict(),
            "status": self.status,
        }
        optional = {
            "subtitle": self.subtitle,
            "comparison_group": self.comparison_group,
            "supersedes": self.supersedes,
            "color_role": self.color_role,
            "annotations": self.annotations,
            "uncertainty": self.uncertainty,
            "confidence_regime": self.confidence_regime,
        }
        for k, v in optional.items():
            if v is not None:
                d[k] = v
        return d


def validate(panel_dict: dict, schema_path: Path = _SCHEMA_PATH) -> None:
    """
    Raises jsonschema.ValidationError (or a clear RuntimeError if the
    jsonschema package isn't installed) if panel_dict doesn't satisfy the
    contract. Used by both write_panel() and CI's validate_panel.py so a
    bad panel is caught locally before it's ever pushed.
    """
    if jsonschema is None:
        raise RuntimeError(
            "The 'jsonschema' package is required (pip install jsonschema)."
        )
    with open(schema_path) as f:
        schema = json.load(f)
    jsonschema.validate(instance=panel_dict, schema=schema)


def write_panel(
    panel: PanelArtifact,
    out_dir: Path | str,
    *,
    validate_first: bool = True,
) -> Path:
    """
    Writes panel to <out_dir>/<panel.forcing_type>/<panel.panel_id>.json.

    This is the ONLY function method scripts should use to produce a panel
    file — it guarantees the same validation and the same file layout
    (site/panels/<forcing_type>/<panel_id>.json) that scripts/build_manifest.py
    later scans.
    """
    d = panel.to_dict()
    if validate_first:
        validate(d)

    out_dir = Path(out_dir) / panel.forcing_type
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{panel.panel_id}.json"
    with open(out_path, "w") as f:
        json.dump(d, f, indent=2, sort_keys=False)
        f.write("\n")
    return out_path
