"""Jordan water/drought BASELINE — every figure carries {value, unit, kind, source_url}.

kind: 'measured'  = stated directly by the cited source (re-fetchable for API ones)
      'derived'   = computed from measured inputs (badge 'محسوب/derived'; never imply the
                    source stated the derived value)
      'estimate'  = expert/uncalibrated assumption with a plausible range

This is the deterministic seed for cascade_sim.py — the drought verdict reads from these +
the cascade, NOT from the complaint-sentiment graph. Numeric facts are not copyrightable;
we store the value + a source URL, never source prose.

Sources verified live during research (World Bank API returns the per-capita series to the
decimal). See REFERENCES for the full ledger.
"""
from __future__ import annotations

from typing import Any, Dict, List

WB = "https://api.worldbank.org/v2/country/JOR/indicator"

BASELINE: Dict[str, Dict[str, Any]] = {
    # --- water availability / stress ---
    "renewable_internal_per_capita_m3": {
        "value": 60.59, "unit": "m3/person/yr", "kind": "measured", "year": 2022,
        "source_url": f"{WB}/ER.H2O.INTR.PC?format=json",
        "note": "Internal renewable freshwater per capita (World Bank ER.H2O.INTR.PC). ~13% of the 500 m3 absolute-scarcity line."},
    "absolute_scarcity_line_m3": {
        "value": 500, "unit": "m3/person/yr", "kind": "measured",
        "source_url": "https://www.unwater.org/water-facts/water-scarcity",
        "note": "Falkenmark absolute-scarcity threshold."},
    "withdrawals_pct_of_renewable": {
        "value": 139, "unit": "%", "kind": "measured",
        "source_url": "https://www.fao.org/aquastat/en/countries-and-basins/country-profiles/country/JOR",
        "note": "Withdrawals exceed renewable supply (mining of fossil groundwater)."},
    "nrw_pct": {
        "value": 48, "unit": "%", "kind": "measured", "range": [45, 52],
        "source_url": "https://www.wes-med.eu/wp-content/uploads/2024/05/NRW-Policy-paper-for-Jordan-2024.05.pdf",
        "note": "Non-revenue water (physical + commercial losses)."},
    # --- demand split (MWI Facts & Figures 2022) ---
    "use_by_sector_pct": {
        "value": {"agriculture": 51, "municipal": 46, "industrial": 3}, "unit": "%", "kind": "measured",
        "source_url": "https://www.mwi.gov.jo/ebv4.0/root_storage/ar/eb_list_page/jordan_water_sector_-_facts_and_figures_2022.pdf",
        "note": "Agriculture uses ~51% of water for ~4-7% of GDP."},
    "supply_by_source_pct": {
        "value": {"groundwater": 58, "surface": 26, "treated_wastewater": 16}, "unit": "%", "kind": "measured",
        "source_url": "https://www.mwi.gov.jo/ebv4.0/root_storage/ar/eb_list_page/jordan_water_sector_-_facts_and_figures_2022.pdf"},
    "groundwater_overabstraction_ratio": {
        "value": 2.2, "unit": "x safe yield", "kind": "measured",
        "basins": {"amman_zarqa": 1.76, "azraq": 2.15},
        "source_url": "https://link.springer.com/article/10.1007/s10040-021-02404-1",
        "note": "National abstraction ~2.2x renewable safe yield."},
    # --- the drought shock (2024/25-2025/26) ---
    "dam_capacity_mcm": {
        "value": 280.76, "unit": "MCM", "kind": "measured",
        "source_url": "https://www.zawya.com/en/economy/levant/jordan-rainfall-reaches-4-of-seasonal-average-ministry-of-water-dldsf072",
        "note": "Total live capacity of the 14 major dams (the storage denominator)."},
    "dam_storage_mcm": {
        "value": {"2023": 118.7, "2024": 87.6, "2025_nov": 43}, "unit": "MCM", "kind": "measured",
        "source_url": "https://www.zawya.com/en/economy/levant/jordan-rainfall-reaches-4-of-seasonal-average-ministry-of-water-dldsf072",
        "note": "Collapse to ~15% of capacity by Nov 2025."},
    "rainfall_pct_of_seasonal_avg": {
        "value": 4, "unit": "%", "kind": "measured", "as_of": "2025-11",
        "source_url": "https://www.zawya.com/en/economy/levant/jordan-rainfall-reaches-4-of-seasonal-average-ministry-of-water-dldsf072",
        "note": "Only ~4% of seasonal-average rainfall by mid-Nov 2025 (early season)."},
    "seasonal_rainfall_deficit_pct": {
        "value": -42, "unit": "%", "kind": "estimate", "range": [-35, -50],
        "source_url": "https://www.climatecentre.org/wp-content/uploads/RCCC-Country-profiles-Jordan-2024_final.pdf",
        "note": "Representative 'no-rain year' full-season deficit band."},
    "recovery_non_monotonic_pct": {
        "value": [4, 130], "unit": "% of avg", "kind": "measured",
        "source_url": "https://www.zawya.com/en/economy/levant/jordan-rainfall-reaches-4-of-seasonal-average-ministry-of-water-dldsf072",
        "note": "The SAME 2025/26 season rebounded ~4% -> ~130% — a built-in falsification test against 'irreversible collapse'."},
    # --- food / agriculture (the corrected narrative) ---
    "grain_import_dependency_pct": {
        "value": 95, "unit": "%", "kind": "measured",
        "source_url": "https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Grain+and+Feed+Annual_Amman_Jordan_JO2025-0007",
        "note": ">95% of grain imported -> a 1-yr drought does NOT cause a domestic bread famine; risk routes via feed/livestock/vegetables/FX."},
    "grain_reserve_months": {
        "value": 10, "unit": "months", "kind": "measured",
        "source_url": "https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Grain+and+Feed+Annual_Amman_Jordan_JO2025-0007"},
    "crop_loss_pct": {
        "value": {"wheat": -14, "barley": -26, "olives": -20},
        "ranges": {"wheat": [-7, -21], "barley": [-18, -35]},
        "unit": "% yield", "kind": "estimate",
        "source_url": "https://www.climatecentre.org/wp-content/uploads/RCCC-Country-profiles-Jordan-2024_final.pdf"},
    "ag_share_gdp_pct": {
        "value": 5.5, "unit": "%", "kind": "estimate", "range": [4, 7],
        "source_url": f"{WB}/NV.AGR.TOTL.ZS?format=json"},
    # --- interventions ---
    "treated_wastewater_reuse_mcm": {
        "value": 167, "unit": "MCM/yr", "kind": "measured",
        "source_url": "https://www.mwi.gov.jo/EBV4.0/Root_Storage/AR/EB_Ticker/National_Water_Strategy_2023-2040_Summary-English_-ver2.pdf"},
    "desalination_online_year": {
        "value": 2029, "unit": "year", "kind": "measured",
        "source_url": "https://www.greenclimate.fund/project/fp288",
        "note": "Aqaba-Amman ~300 MCM/yr; GCF FP288 approved 30 Oct 2025; operational ~2029-30 -> ZERO near-term drought relief (engine must flag non-mitigating)."},
    # --- climate projection ---
    "precip_decline_2071_2100_pct": {
        "value": -22.1, "unit": "%", "kind": "measured",
        "source_url": "https://www.ipcc.ch/report/ar6/wg2/chapter/ccp4/",
        "note": "Upper Jordan River CORDEX; runoff falls faster than precip (-17.5%)."},
}

REFERENCES: List[Dict[str, str]] = [
    {"name": "World Bank — Renewable internal freshwater per capita, Jordan (ER.H2O.INTR.PC)",
     "url": f"{WB}/ER.H2O.INTR.PC?format=json"},
    {"name": "MWI — Jordan Water Sector Facts and Figures 2022",
     "url": "https://www.mwi.gov.jo/ebv4.0/root_storage/ar/eb_list_page/jordan_water_sector_-_facts_and_figures_2022.pdf"},
    {"name": "MWI — National Water Strategy 2023-2040",
     "url": "https://www.mwi.gov.jo/EBV4.0/Root_Storage/AR/EB_Ticker/National_Water_Strategy_2023-2040_Summary-English_-ver2.pdf"},
    {"name": "Springer Hydrogeology Journal — Long-term groundwater over-abstraction in Jordan (DOI)",
     "url": "https://link.springer.com/article/10.1007/s10040-021-02404-1"},
    {"name": "IWMI MENAdrought — Jordan National Drought Action Plan (eCDI, 4-class ladder, R1-R21)",
     "url": "https://menadrought.iwmi.org/wp-content/uploads/sites/44/2023/02/combined_jordan_dap.pdf"},
    {"name": "USDA FAS — Jordan Grain and Feed Annual 2025 (>95% grain imported, ~10-mo reserves)",
     "url": "https://apps.fas.usda.gov/newgainapi/api/Report/DownloadReportByFileName?fileName=Grain+and+Feed+Annual_Amman_Jordan_JO2025-0007"},
    {"name": "UNICEF — Tapped Out: The Costs of Water Stress in Jordan",
     "url": "https://www.unicef.org/jordan/media/11356/file/water%20stress%20in%20Jordan%20report.pdf"},
    {"name": "Green Climate Fund FP288 — Aqaba-Amman Desalination & Conveyance",
     "url": "https://www.greenclimate.fund/project/fp288"},
    {"name": "Red Cross Climate Centre — Jordan Country Profile 2024",
     "url": "https://www.climatecentre.org/wp-content/uploads/RCCC-Country-profiles-Jordan-2024_final.pdf"},
    {"name": "IPCC AR6 WGII — Cross-Chapter Paper 4 (Mediterranean)",
     "url": "https://www.ipcc.ch/report/ar6/wg2/chapter/ccp4/"},
    {"name": "Zawya/MWI — Jordan rainfall 4% of seasonal average; dam storage 43 MCM (Nov 2025)",
     "url": "https://www.zawya.com/en/economy/levant/jordan-rainfall-reaches-4-of-seasonal-average-ministry-of-water-dldsf072"},
    {"name": "WES-MED — Non-Revenue Water Policy for Jordan 2024",
     "url": "https://www.wes-med.eu/wp-content/uploads/2024/05/NRW-Policy-paper-for-Jordan-2024.05.pdf"},
    {"name": "FAO AQUASTAT — Jordan country profile",
     "url": "https://www.fao.org/aquastat/en/countries-and-basins/country-profiles/country/JOR"},
]


def value(key: str, default: Any = None) -> Any:
    return BASELINE.get(key, {}).get("value", default)


def to_public() -> Dict[str, Any]:
    """Profile payload for the frontend (values + provenance + references)."""
    return {"baseline": BASELINE, "references": REFERENCES}
