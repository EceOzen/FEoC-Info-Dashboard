"""
Data-access helpers shared by method scripts.

Kept deliberately thin: this is NOT a general CMIP data-access library, just
the handful of things both the GHG and volcanic scripts need so they don't
each reinvent DRS parsing or repeat the "never load the whole file into
memory" rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# input4MIPs datasets flagged as test/transitional — per the CMIP CV docs,
# "production simulations should not be started based on any data that has
# a mip_era value equal to 'CMIP6Plus'". Any mip_era in this set means a
# panel's meta.production_ready must be set to False, and the dashboard
# will render a visible "not production data" badge.
PRODUCTION_READY_ERAS = {"CMIP6", "CMIP7"}
NON_PRODUCTION_ERAS = {"CMIP6Plus", "CMIP7Plus"}


@dataclass
class DRS:
    """
    Parsed input4MIPs Data Reference Syntax:
    activity_id.mip_era.target_mip.institution_id.source_id.realm.frequency.variable_id.grid_label
    """

    activity_id: str
    mip_era: str
    target_mip: str
    institution_id: str
    source_id: str
    realm: str
    frequency: str
    variable_id: str
    grid_label: str

    def __str__(self) -> str:
        return ".".join(
            [
                self.activity_id,
                self.mip_era,
                self.target_mip,
                self.institution_id,
                self.source_id,
                self.realm,
                self.frequency,
                self.variable_id,
                self.grid_label,
            ]
        )

    @property
    def is_production_ready(self) -> bool:
        return self.mip_era in PRODUCTION_READY_ERAS


def parse_drs(drs_string: str) -> DRS:
    """
    Parses a full input4MIPs DRS string, e.g.:
    'input4MIPs.CMIP7.CMIP.UOEXETER.UOEXETER-CMIP-1-1-3.atmos.mon.saod.gn'

    Raises ValueError if the string doesn't have exactly 9 dot-separated
    components — fail loudly here rather than silently mis-attributing a
    panel's provenance.
    """
    parts = drs_string.split(".")
    if len(parts) != 9:
        raise ValueError(
            f"Expected a 9-component input4MIPs DRS string, got {len(parts)} "
            f"components in: {drs_string!r}"
        )
    return DRS(*parts)


def open_lazy(data_ref: str, *, chunks: Optional[dict] = None):
    """
    Opens a CMIP source lazily (xarray, dask-backed) rather than reading it
    fully into memory. `data_ref` is expected to be a path, glob pattern, or
    URL/zstore reference — never a value embedded directly in a panel JSON.

    This is a thin wrapper stub: real method scripts fill in the actual
    xarray.open_dataset / open_mfdataset call appropriate to their source
    (single file, glob of split time-range files, OPeNDAP URL, zarr store).
    Left unimplemented here deliberately — the right call depends on the
    dataset layout (e.g. GHG concentration files are split into three
    time-range files per the input4MIPs CV notes), which is domain
    knowledge that belongs in the method script, not this shared helper.
    """
    raise NotImplementedError(
        "open_lazy() is a stub. Implement the actual xarray.open_dataset("
        "..., chunks=chunks) or open_mfdataset(...) call for your specific "
        "data_ref layout inside your method script, or extend this helper "
        "once a common pattern emerges across GHG and volcanic scripts."
    )
