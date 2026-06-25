"""The fruit registry — one entry per HS code, the single retarget point.

The board machine is fully HS-parameterised; a fruit is just a config row here.
`build_all()` loops this registry, builds one page per fruit (docs/<slug>.html)
plus the atlas hub (docs/index.html). Blueberry's values come from deep.config
(the original single-fruit block); new fruits are added as Fruit(...) rows.

Per-fruit data is namespaced: vintage series are `{prefix}_{slug}_{suffix}`
(e.g. hmrc_cherry_imports) and market caches `{name}_{slug}.csv` — except
blueberry, which keeps the original un-suffixed paths so nothing migrates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from deep import config as _cfg


@dataclass(frozen=True)
class Fruit:
    slug: str                       # url + data namespace, e.g. "blueberry"
    name: str                       # "Blueberry" — masthead "Britain's {name} Board"
    emoji: str                      # eyebrow glyph, "" to omit
    hs6: str                        # UN Comtrade HS-6, e.g. "081040"
    cn8: str                        # HMRC UK CN8, e.g. "08104050"
    commodity_id: int               # HMRC numeric CommodityId (int of cn8)
    faostat_item: str               # FAOSTAT QCL production item, e.g. "Blueberries"
    supply_origins: dict            # name -> (M49, 3-letter code, colour)
    inseason: list                  # the major suppliers (subset of supply_origins)
    production_overrides: dict = field(default_factory=dict)  # {country: (t, yr, src)}
    gap_note: str = ""              # world-map caveat when overrides exist
    odepa_prefix: str = ""          # Chile ODEPA HS prefix (deep nowcast; blueberry only)
    defra_production: bool = False  # do we hold UK production for this fruit? (self-sufficiency)

    # Per-fruit data paths — blueberry keeps the original un-suffixed names.
    def cache(self, name: str):
        suffix = "" if self.slug == "blueberry" else f"_{self.slug}"
        return _cfg.DATA_DIR / "market" / f"{name}{suffix}.csv"

    def series(self, prefix: str, suffix: str) -> str:
        return f"{prefix}_{self.slug}_{suffix}"

    @property
    def out(self):
        return _cfg.REPO_ROOT / "docs" / f"{self.slug}.html"


BLUEBERRY = Fruit(
    slug="blueberry", name=_cfg.FRUIT_NAME, emoji=_cfg.FRUIT_EMOJI,
    hs6=_cfg.HS6, cn8=_cfg.COMMODITY_CN8, commodity_id=_cfg.COMMODITY_ID,
    faostat_item=_cfg.FAOSTAT_ITEM, supply_origins=_cfg.SUPPLY_ORIGINS,
    inseason=_cfg.INSEASON_ORIGINS, production_overrides=_cfg.PRODUCTION_OVERRIDES,
    gap_note=_cfg.PRODUCTION_GAP_NOTE, odepa_prefix=_cfg.ODEPA_HS_PREFIX,
    defra_production=True,
)

CHERRY = Fruit(
    slug="cherry", name="Cherry", emoji="🍒",
    # Sweet cherries: HS2012+ split 0809 into 080921 (sour) / 080929 (sweet) —
    # the old 080920 is obsolete. UK CN8 08092900 = fresh sweet cherries.
    hs6="080929", cn8="08092900", commodity_id=8092900, faostat_item="Cherries",
    # UK cherry suppliers (Europe in summer, Chile/US counter-/early-season).
    supply_origins={
        "Spain":         (724, "ESP", "#c9a227"),
        "Turkey":        (792, "TUR", "#c0392b"),
        "Chile":         (152, "CHL", "#6b3fa0"),
        "Portugal":      (620, "PRT", "#3a8f6b"),
        "Greece":        (300, "GRC", "#4c5fd5"),
        "Italy":         (380, "ITA", "#2a9d8f"),
        "Morocco":       (504, "MAR", "#e8833a"),
        "United States": (842, "USA", "#5b8a72"),
        "Netherlands":   (528, "NLD", "#7a8699"),
        "Argentina":     (32,  "ARG", "#3f7fae"),
    },
    inseason=["Chile", "Spain", "Turkey", "Greece", "Portugal", "Italy"],
    production_overrides={}, gap_note="",   # Turkey is #1 cherry grower and IS in FAOSTAT
)

FRUITS = {f.slug: f for f in (BLUEBERRY, CHERRY)}
