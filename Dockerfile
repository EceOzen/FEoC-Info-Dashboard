# FEoC method scripts: run panel scripts and the validator without setting up Python yourself.
#
# Build:
#   docker build -t feoc-panels .
#
# Run a method script (panel JSON lands in ./site/panels on your machine):
#   docker run --rm -v "$PWD/site/panels:/app/site/panels" -v /path/to/cmip/data:/data:ro feoc-panels \
#     python methods/ghg/erf_myhre_etminan.py --species co2 --data-ref /data/<file>.nc \
#     --out-dir site/panels --author <you> --drs "<full input4MIPs DRS string>"
#
# Validate panels before opening a PR:
#   docker run --rm -v "$PWD/site:/app/site" feoc-panels python scripts/validate_panel.py
#
# Note: Docker is often not allowed on HPC systems. There, use
# `pip install -e .` in a conda/venv environment instead (or Apptainer).

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Data-access libraries needed by the method scripts once real CMIP files are wired in.
RUN pip install xarray netcdf4 dask

COPY . /app
RUN pip install -e .

CMD ["python", "scripts/validate_panel.py"]
