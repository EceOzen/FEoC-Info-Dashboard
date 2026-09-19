"""
feoc_panels — shared core library for FEoC method scripts.

Method scripts (methods/ghg/*, methods/volcanic/*) import from here so that
every panel is written against the same PanelArtifact contract, instead of
each script re-inventing JSON writing, DRS parsing, or baseline handling.

Keep this package small and stable. Domain-specific computation (the actual
forcing formulas, the actual zonal reduction) belongs in the method scripts,
not here.
"""

from .contract import PanelArtifact, write_panel, validate
from .io import parse_drs, open_lazy, PRODUCTION_READY_ERAS
from .citation import CITATIONS

__all__ = [
    "PanelArtifact",
    "write_panel",
    "validate",
    "parse_drs",
    "open_lazy",
    "PRODUCTION_READY_ERAS",
    "CITATIONS",
]
