"""
Citation strings for the CMIP forcing datasets this project currently
covers. Method scripts should pull from here (meta.citation) rather than
hand-typing citations, so a correction only needs to happen in one place.

Extend this dict as new datasets/eras are added (ozone, solar, land-use...).
"""

CITATIONS = {
    # GHG concentrations
    "ghg_cmip6": (
        "Meinshausen, M., Vogel, E., Nauels, A., et al. (2017). Historical "
        "greenhouse gas concentrations for climate modelling (CMIP6). "
        "Geosci. Model Dev., 10, 2057-2116."
    ),
    "ghg_cmip7": (
        "Climate Resource (CR) GHG concentrations for CMIP7 "
        "(source_id family CR-CMIP-*). See "
        "https://github.com/climate-resource/CMIP6-vs-CMIP7-GHG-Concentrations "
        "for a direct comparison against CMIP6."
    ),
    # Volcanic stratospheric aerosol
    "volcanic_cmip6": (
        "Luo, B. (2018). Stratospheric aerosol data for use in CMIP6 "
        "models - data description. "
        "ftp://iacftp.ethz.ch/pub_read/luo/CMIP6/Readme_Data_Description.pdf"
    ),
    "volcanic_cmip7": (
        "Jörimann, A., Aubry, T.J., et al. (2026). Stratospheric aerosol "
        "forcing for CMIP7 - Part 1: optical properties for pre-industrial, "
        "historical, and scenario simulations. Geosci. Model Dev., 19, 3725."
    ),
    "volcanic_glossac": (
        "GloSSAC v2.x - Global Space-based Stratospheric Aerosol Climatology "
        "(satellite era, 1979-present)."
    ),
    "volcanic_eva_h": (
        "Toohey, M. & Sigl, M. (2017). Volcanic stratospheric sulfur "
        "injections and aerosol optical depth from 500 BCE to 1900 CE. "
        "Earth Syst. Sci. Data, 9, 809-831."
    ),
    # Forcing formulas
    "erf_myhre1998": (
        "Myhre, G., Highwood, E.J., Shine, K.P., Stordal, F. (1998). New "
        "estimates of radiative forcing due to well mixed greenhouse gases. "
        "Geophys. Res. Lett., 25(14), 2715-2718."
    ),
    "erf_etminan2016": (
        "Etminan, M., Myhre, G., Highwood, E.J., Shine, K.P. (2016). "
        "Radiative forcing of carbon dioxide, methane, and nitrous oxide: "
        "A significant revision. Geophys. Res. Lett., 43, 12614-12623."
    ),
}
