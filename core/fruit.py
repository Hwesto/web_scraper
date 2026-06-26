"""The fruit registry — one entry per HS code, the single retarget point.

The board machine is fully HS-parameterised; a fruit is just a config row here.
`build_all()` loops this registry, builds one page per fruit (docs/<slug>.html)
plus the atlas hub (docs/index.html). The HS-driven feeds (HMRC imports/value/
re-exports, Comtrade global trade map, FAOSTAT production, destinations) come for
free per fruit; the consumer side (Trolley retail, DEFRA wholesale/production) is
wired only where held, and the board degrades gracefully without it.

Per-fruit data is namespaced: vintage series `{prefix}_{slug}_{suffix}` and market
caches `{name}_{slug}.csv` — except blueberry, which keeps the original un-suffixed
paths so nothing migrates.
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
    faostat_item: str               # FAOSTAT QCL production item, e.g. "Blueberries"
    supply_origins: dict            # name -> (M49, 3-letter code, colour)
    inseason: list                  # the major suppliers (subset of supply_origins)
    commodity_ids: tuple | None = None  # HMRC CN8 ids to sum; None -> all CN8 under hs6
    production_overrides: dict = field(default_factory=dict)  # {country: (t, yr, src)}
    gap_note: str = ""              # world-map caveat when overrides exist
    odepa_prefix: str = ""          # Chile ODEPA HS prefix (deep nowcast; blueberry only)
    defra_rows: tuple = ()          # DEFRA Hort-stats Table-6/7 row labels to SUM for UK
                                    # production (e.g. apple = Dessert + Culinary); () = none
    container_t: int = 24           # fruit per 40-ft reefer: soft/clamshell is
                                    # volume-bound (~20 t); dense cartoned fruit is
                                    # weight-bound, nearer the ~26 t payload cap.

    @property
    def defra_production(self) -> bool:
        """Do we hold UK-grown production for this fruit (DEFRA Horticulture stats)?"""
        return bool(self.defra_rows)

    def cache(self, name: str):
        suffix = "" if self.slug == "blueberry" else f"_{self.slug}"
        return _cfg.DATA_DIR / "market" / f"{name}{suffix}.csv"

    def series(self, prefix: str, suffix: str) -> str:
        return f"{prefix}_{self.slug}_{suffix}"

    @property
    def out(self):
        return _cfg.REPO_ROOT / "docs" / f"{self.slug}.html"


# A shared palette of common fruit-exporting origins — name -> (M49, code, colour).
# New fruits draw their codes/colours from here; origins not listed fall back to a
# 3-letter slice + the accent colour. Blueberry keeps its own bespoke set.
_PAL = ["#4c5fd5", "#e8833a", "#2a9d8f", "#6b3fa0", "#c9a227", "#7a8699", "#b1543a",
        "#3a8f6b", "#c0392b", "#5b8a72", "#3f7fae", "#9b59b6", "#d68910", "#16a085"]
_ORIGINS = [
    ("Spain", 724, "ESP"), ("Morocco", 504, "MAR"), ("South Africa", 710, "ZAF"),
    ("Chile", 152, "CHL"), ("Peru", 604, "PER"), ("Netherlands", 528, "NLD"),
    ("Italy", 380, "ITA"), ("Turkey", 792, "TUR"), ("Egypt", 818, "EGY"),
    ("Costa Rica", 188, "CRI"), ("Colombia", 170, "COL"), ("Brazil", 76, "BRA"),
    ("Mexico", 484, "MEX"), ("United States", 842, "USA"), ("Argentina", 32, "ARG"),
    ("Ecuador", 218, "ECU"), ("Dominican Republic", 214, "DOM"), ("Israel", 376, "ISR"),
    ("Portugal", 620, "PRT"), ("Greece", 300, "GRC"), ("France", 251, "FRA"),
    ("Poland", 616, "POL"), ("Belgium", 56, "BEL"), ("Germany", 276, "GER"),
    ("India", 356, "IND"), ("China", 156, "CHN"), ("Kenya", 404, "KEN"),
    ("Ghana", 288, "GHA"), ("Côte d'Ivoire", 384, "CIV"), ("Cameroon", 120, "CMR"),
    ("Panama", 591, "PAN"), ("Guatemala", 320, "GTM"), ("Honduras", 340, "HND"),
    ("New Zealand", 554, "NZL"), ("Pakistan", 586, "PAK"), ("Namibia", 516, "NAM"),
    ("Tunisia", 788, "TUN"), ("Iran", 364, "IRN"), ("Saudi Arabia", 682, "KSA"),
    ("Vietnam", 704, "VNM"), ("Thailand", 764, "THA"),
]
SHARED = {n: (m, c, _PAL[i % len(_PAL)]) for i, (n, m, c) in enumerate(_ORIGINS)}


def _f(slug, name, emoji, hs6, faostat, inseason, **kw):
    """A new fruit drawing origins from the shared palette (HS-driven feeds only)."""
    return Fruit(slug=slug, name=name, emoji=emoji, hs6=hs6, faostat_item=faostat,
                 supply_origins=SHARED, inseason=inseason, **kw)


BLUEBERRY = Fruit(
    slug="blueberry", name=_cfg.FRUIT_NAME, emoji=_cfg.FRUIT_EMOJI,
    hs6=_cfg.HS6, commodity_ids=(_cfg.COMMODITY_ID,), faostat_item=_cfg.FAOSTAT_ITEM,
    supply_origins=_cfg.SUPPLY_ORIGINS, inseason=_cfg.INSEASON_ORIGINS,
    production_overrides=_cfg.PRODUCTION_OVERRIDES, gap_note=_cfg.PRODUCTION_GAP_NOTE,
    odepa_prefix=_cfg.ODEPA_HS_PREFIX, defra_rows=("Blueberry",), container_t=20,
)
CHERRY = _f("cherry", "Cherry", "🍒", "080929", "Cherries",  # sweet cherries (080920 obsolete)
            ["Chile", "Spain", "Turkey", "Greece", "Portugal", "Italy"],
            commodity_ids=(8092900,), container_t=20, defra_rows=("Cherries :",))

# Top UK fresh-fruit imports — HS6 verified, CN8 auto-discovered (all CN8 under HS6).
_TOP = [
    _f("banana", "Banana", "🍌", "080390", "Bananas",
       ["Colombia", "Costa Rica", "Dominican Republic", "Ecuador", "Cameroon", "Côte d'Ivoire"]),
    _f("grape", "Grape", "🍇", "080610", "Grapes",
       ["Spain", "South Africa", "Chile", "Egypt", "Peru", "India"], container_t=20),
    _f("apple", "Apple", "🍎", "080810", "Apples",
       ["France", "South Africa", "Chile", "New Zealand", "Italy", "Netherlands"],
       defra_rows=("Total Dessert Apples", "Total Culinary Apples")),
    _f("strawberry", "Strawberry", "🍓", "081010", "Strawberries",
       ["Spain", "Egypt", "Morocco", "Netherlands", "Belgium"], container_t=20,
       defra_rows=("Strawberries",)),
    _f("avocado", "Avocado", "🥑", "080440", "Avocados",
       ["Peru", "South Africa", "Chile", "Israel", "Spain", "Colombia"]),
    _f("raspberry", "Raspberry", "🔴", "081020", "Raspberries",
       ["Spain", "Morocco", "Portugal", "Mexico", "Netherlands"], container_t=20,
       defra_rows=("Raspberries",)),
    _f("mandarin", "Mandarin", "🍊", "080521", "Tangerines, mandarins, clementines",
       ["Spain", "South Africa", "Morocco", "Peru", "Egypt", "Turkey"]),
    _f("mango", "Mango", "🥭", "080450", "Mangoes, guavas and mangosteens",
       ["Brazil", "Peru", "Côte d'Ivoire", "Pakistan", "Israel", "Spain"]),
    _f("orange", "Orange", "🍊", "080510", "Oranges",
       ["Spain", "South Africa", "Egypt", "Morocco", "Argentina"]),
    _f("lemon", "Lemon", "🍋", "080550", "Lemons and limes",
       ["Spain", "South Africa", "Argentina", "Turkey", "Brazil"]),
    _f("pear", "Pear", "🍐", "080830", "Pears",
       ["Netherlands", "South Africa", "Belgium", "Argentina", "Chile", "Spain"],
       defra_rows=("Total Pears",)),
    _f("peach", "Peach", "🍑", "080930", "Peaches and nectarines",
       ["Spain", "Italy", "Greece", "South Africa", "Chile"]),
    _f("watermelon", "Watermelon", "🍉", "080711", "Watermelons",
       ["Spain", "Morocco", "Costa Rica", "Brazil", "Egypt"]),
    _f("melon", "Melon", "🍈", "080719", "Cantaloupes and other melons",
       ["Spain", "Brazil", "Costa Rica", "Morocco", "Honduras"]),
    _f("pineapple", "Pineapple", "🍍", "080430", "Pineapples",
       ["Costa Rica", "Ghana", "Côte d'Ivoire", "Panama"]),
    _f("kiwi", "Kiwi", "🥝", "081050", "Kiwi fruit",
       ["Italy", "New Zealand", "Greece", "Chile", "France"]),
    _f("plum", "Plum", "🟣", "080940", "Plums and sloes",
       ["Spain", "South Africa", "Chile", "Namibia"], defra_rows=("Total Plums",)),
    _f("date", "Date", "🌴", "080410", "Dates",
       ["Tunisia", "Israel", "Egypt", "Iran", "Saudi Arabia"]),
]

FRUITS = {f.slug: f for f in (BLUEBERRY, CHERRY, *_TOP)}
