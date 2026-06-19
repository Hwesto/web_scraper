"""Grower netback by destination -- where Chilean fruit nets the most per kg.

    netback (FOB-equivalent) = observed CIF price - ocean freight

CIF, volume and growth are observed (Comtrade). The *only* assumption is ocean
reefer freight per kg; it is a documented, tunable constant, never presented as
measured. Tariff and transit time are known constants carried as market-friction
context, not subtracted from netback (CIF already reflects the realised sale, and
import duty is paid by the buyer, not the grower).

So the table answers: per kg, which market pays the Chilean exporter most -- and
then the volume/transit/tariff columns explain why you still can't send it all there.
"""
from __future__ import annotations

import pandas as pd

from nowcast.market import comtrade

# --- The one assumption: ocean reefer freight, USD/kg, ex San Antonio/Valparaiso. ---
# Derived transparently as (40ft reefer rate per container) / (blueberry payload),
# rather than guessed, so it can be checked and updated:
#   * Reefer boxes run 2.5-4x a dry box; deep-sea reefer Asia<->N.America sits at
#     ~$8-12k/container (2024-25). Chile-origin reefer estimates by lane:
#       US/Canada (~14d) ~$6.0k   Europe (~26d) ~$7.5k   Asia (~33d) ~$9.5k
#   * Fresh blueberries are volume-limited, not weight-limited: ~20 pallets fill a
#     40ft reefer at ~11 t net, far below the ~26 t payload cap.
#   => US 6.0k/11t=$0.55  Europe 7.5k/11t=$0.68  Asia 9.5k/11t=$0.86 per kg.
# Sources: reefer-vs-dry premium & deep-sea reefer bands (Freightos/industry 2024-25);
# 40ft reefer payload & blueberry pallet packing (container spec sheets). Tune as real
# forwarder quotes arrive -- these move the ranking, hence isolated and surfaced.
_REEFER_PAYLOAD_T = 11.0                  # net tonnes of blueberries per 40ft reefer
_FREIGHT_REGION = {
    "Americas": 0.55, "Europe": 0.68, "Asia": 0.86, "MiddleEast": 0.91,
    "SouthAmerica": 0.25,                 # short regional haul, partly overland
}
_TRANSIT_REGION = {                       # door-to-port sea days, ex central Chile
    "Americas": 14, "Europe": 26, "Asia": 33, "MiddleEast": 30, "SouthAmerica": 7,
}
_TRANSIT_PERU = {                         # ex Callao/Paita -- closer to N. America/Asia
    "Americas": 11, "Europe": 22, "Asia": 30, "MiddleEast": 26, "SouthAmerica": 7,
}
_REGION = {
    "United States": "Americas", "Canada": "Americas", "Mexico": "Americas",
    "Netherlands": "Europe", "Germany": "Europe", "United Kingdom": "Europe",
    "Spain": "Europe", "Belgium": "Europe", "Italy": "Europe", "France": "Europe",
    "Ireland": "Europe", "Sweden": "Europe", "Poland": "Europe",
    "Israel": "MiddleEast",
    "China": "Asia", "South Korea": "Asia", "Japan": "Asia", "Taiwan": "Asia",
    "Hong Kong": "Asia", "Singapore": "Asia", "Malaysia": "Asia",
    "Philippines": "Asia", "Other Asia, nes": "Asia",
    "United Arab Emirates": "MiddleEast", "Qatar": "MiddleEast",
    "Saudi Arabia": "MiddleEast",
    "Argentina": "SouthAmerica", "Brazil": "SouthAmerica",
    "Colombia": "SouthAmerica", "Ecuador": "SouthAmerica", "Chile": "SouthAmerica",
    "Costa Rica": "Americas", "Russia": "Europe",
    "India": "Asia", "Thailand": "Asia",
}

# Chile's FTAs zero the duty into its major markets (US/EU/UK/China/Korea/Japan).
# The live exception: from late 2025 Chilean blueberries were NOT exempted from the
# US +10% reciprocal tariff -- a buyer-side cost that erodes the big-volume US lane.
US_RECIPROCAL_TARIFF = 0.10
_TARIFF = {"United States": US_RECIPROCAL_TARIFF}

# Per-origin config. Freight is the shared deep-sea-reefer approximation (Peru ex-Callao
# is a touch closer to the US/Asia, partly captured by shorter transit; tune later).
_ORIGINS = {
    "Chile": {"cache": comtrade.CACHE, "transit": _TRANSIT_REGION, "tariff": _TARIFF},
    "Peru":  {"cache": comtrade.PERU_CACHE, "transit": _TRANSIT_PERU, "tariff": {}},
}


def _region(dest: str) -> str:
    return _REGION.get(dest, "Europe")            # conservative mid default


def netback_table(year: int | None = None, min_kg: float = 200_000.0,
                  origin: str = "Chile") -> pd.DataFrame:
    """Per-destination netback for one origin/year, ranked best-first.

    Columns: destination, cif_usd_kg, freight_usd_kg, netback_usd_kg, net_kg,
    vol_share_%, transit_days, tariff_%, yoy_growth_%.
    """
    cfg = _ORIGINS[origin]
    df = comtrade.load(cfg["cache"])
    if df.empty:
        return df
    year = year or comtrade.latest_year(df)
    cur = df[df["year"] == year].copy()
    cur = cur[cur["net_kg"] >= min_kg]            # drop noise-tail tiny markets
    prev = df[df["year"] == year - 1].set_index("destination")["net_kg"]

    cur["region"] = cur["destination"].map(_region)
    cur["freight_usd_kg"] = cur["region"].map(_FREIGHT_REGION)
    cur["transit_days"] = cur["region"].map(cfg["transit"])
    cur["netback_usd_kg"] = cur["cif_usd_kg"] - cur["freight_usd_kg"]
    cur["tariff_%"] = cur["destination"].map(cfg["tariff"]).fillna(0.0) * 100
    cur["vol_share_%"] = cur["net_kg"] / cur["net_kg"].sum() * 100
    cur["yoy_growth_%"] = cur.apply(
        lambda r: (r["net_kg"] / prev[r["destination"]] - 1) * 100
        if r["destination"] in prev.index and prev[r["destination"]] > 0 else float("nan"),
        axis=1)

    cols = ["destination", "cif_usd_kg", "freight_usd_kg", "netback_usd_kg",
            "net_kg", "vol_share_%", "transit_days", "tariff_%", "yoy_growth_%"]
    return cur[cols].sort_values("netback_usd_kg", ascending=False).reset_index(drop=True)


def best_markets(year: int | None = None, top: int = 5) -> pd.DataFrame:
    return netback_table(year).head(top)


if __name__ == "__main__":                         # python -m nowcast.market.netback
    t = netback_table()
    pd.set_option("display.width", 120)
    print(t.round(2).to_string(index=False))
