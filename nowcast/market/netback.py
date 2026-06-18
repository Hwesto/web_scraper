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
# Order-of-magnitude from 2024-25 reefer benchmarks (40ft ~10-14 t of berries):
# ~$0.45/kg short-haul Americas, ~$0.70/kg to Europe, ~$0.90/kg deep-sea to Asia.
# Tune these as real forwarder quotes come in -- they move the ranking, so they are
# isolated here and surfaced in the dashboard as an assumption.
_FREIGHT_REGION = {
    "Americas": 0.48, "Europe": 0.70, "Asia": 0.90, "MiddleEast": 0.95,
    "SouthAmerica": 0.30,
}
_TRANSIT_REGION = {                       # door-to-port sea days, ex central Chile
    "Americas": 14, "Europe": 26, "Asia": 33, "MiddleEast": 30, "SouthAmerica": 7,
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
    "Colombia": "SouthAmerica", "Ecuador": "SouthAmerica",
}

# Chile's FTAs zero the duty into its major markets (US/EU/UK/China/Korea/Japan).
# The live exception: from late 2025 Chilean blueberries were NOT exempted from the
# US +10% reciprocal tariff -- a buyer-side cost that erodes the big-volume US lane.
US_RECIPROCAL_TARIFF = 0.10
_TARIFF = {"United States": US_RECIPROCAL_TARIFF}


def _region(dest: str) -> str:
    return _REGION.get(dest, "Europe")            # conservative mid default


def netback_table(year: int | None = None, min_kg: float = 200_000.0) -> pd.DataFrame:
    """Per-destination netback for one year, ranked best-first.

    Columns: destination, cif_usd_kg, freight_usd_kg, netback_usd_kg, net_kg,
    vol_share_%, transit_days, tariff_%, yoy_growth_%.
    """
    df = comtrade.load()
    if df.empty:
        return df
    year = year or comtrade.latest_year(df)
    cur = df[df["year"] == year].copy()
    cur = cur[cur["net_kg"] >= min_kg]            # drop noise-tail tiny markets
    prev = df[df["year"] == year - 1].set_index("destination")["net_kg"]

    cur["region"] = cur["destination"].map(_region)
    cur["freight_usd_kg"] = cur["region"].map(_FREIGHT_REGION)
    cur["transit_days"] = cur["region"].map(_TRANSIT_REGION)
    cur["netback_usd_kg"] = cur["cif_usd_kg"] - cur["freight_usd_kg"]
    cur["tariff_%"] = cur["destination"].map(_TARIFF).fillna(0.0) * 100
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
