# PRODUCT — representing the atlas to humans

What we actually have, and the absolute best way to show it. Grounded in the committed
data assets (`data/atlas/*`, `data/market/*`) and the registry (`registry.csv`, 162 rows).
Pairs with `FRONTIER.md` (what's measured) and `PHASES.md` (how it was built).

---

## 1. What we have — two assets, not one

The single most important product insight: **we have two fundamentally different things**,
and conflating them is the trap.

### A. The atlas-map (the *meta* layer) — our differentiator
The 162-row registry: a machine-readable map of **what information exists** per
commodity × country × role × data-point, flagged **free | paid | none** and **wired or not**.

> access × wired today: **25 free+wired · 73 free-unwired · 20 paid-only · 24 structural-gap · 17 process/probe**

Nobody else publishes this. Trade dashboards show *data*; none show *"here is exactly what
you can know about blueberry trade for free, what costs money (and who sells it), and what
is uncollectable at any price."* That honesty map is the moat — it's the answer to a
question every analyst silently asks and never sees answered.

### B. The data (the *object* layer) — six measurement axes, ~global
| Axis | Source (wired) | Shape | Coverage |
|---|---|---|---|
| **Trade flow + price** | UN Comtrade | ranking 659 · bilateral 5,375 · monthly 15,333 | every exporter×importer, 2012→now, both flows |
| **EU trade detail** | Eurostat COMEXT | 1,219 lanes | 9 EU members, EUR/kg |
| **Production / area / yield** | FAOSTAT | 1,087 country-years | every producing country, 1961→now |
| **Growing condition** | NASA POWER | 1,008 region-months | 14 growing regions, temp/frost/rain |
| **Forward (forecast)** | USDA-FAS GAIN | 5 figures | Peru + Mexico, season-ahead MT |
| **Entity (named orchards)** | SENASICA | 71 orchards | Mexico China-export roster |

### C. The deep reference (the *proof of depth*)
The UK↔Chile/Peru lane: HMRC, Chile DUS (named exporter/producer/cultivar weekly),
Catastro, SAG roster, Trolley/ONS/DEFRA prices, the validated ~2-week nowcast. One lane
taken to the floor — proof that the breadth atlas sits on real depth.

**So: a meta-map + 6 global data axes + 1 deep exemplar — across any fruit (Phase 4 proved
the HS code is a parameter; avocado already runs).**

---

## 2. Audiences & jobs-to-be-done

| Who | The question they arrive with | What answers it |
|---|---|---|
| **Sourcing / trade analyst** | "Who supplies my market *when*, at what $/kg? Who's gaining share?" | seasonal relay · lane+price explorer · ranking trend |
| **Market entrant / investor** | "Where is production growing? Forward outlook? Climate risk?" | FAOSTAT trend · USDA forecast · NASA frost lens |
| **Data scout / researcher** | "What can I know about country X for free? What costs money?" | **the atlas-map** (the unique answer) |
| **Seasonal buyer / journalist** | "Who's shipping *right now / next month*?" | the relay, made glanceable |

Different jobs → progressive disclosure, not one mega-dashboard.

---

## 3. The hero visual — the seasonal relay

The whole counter-season story lives in one matrix (monthly export-volume share, recent
years; the actual committed numbers):

```
month   Chile  Spain  USA  Canada  Peru  NL(re-exp)
Jan      52     2     5     0      21     20     <- Southern-summer giants
Feb      47     9     7     0      16     21
Mar      13    31    13     0      11     31
Apr       1    68    11     0       4     16     <- Spain owns the Northern spring
May       0    69    14     0       1     16
Jun       0    53    26     2       2     17
Jul       0     6    38    39       7     11     <- North America's summer
Aug       0     1    40    31      19     10
Sep       0     2    13     9      57     19     <- Peru, the counter-season colossus
Oct       0     1     3    37      46     12
Nov       1     1     8     8      61     21
Dec      31     3     9     0      32     25
```

Render this as a **stacked-area "relay" across the year** (or a month×origin heatmap) and a
reader understands global blueberry supply in five seconds. **This is the lede.** It also
generalises per-fruit and per-importer ("who supplies *Britain* each month").

A second, quieter story sits beside it — **production ≠ exports**: top *producers* (USA,
Peru, Canada, Chile, Mexico — incl. wild/domestic) are not top *exporters* (Peru, **Netherlands
[grows ~nothing]**, Spain, Chile, Morocco). The gap *is* the insight: who grows to eat vs.
grows to ship vs. ships without growing (the re-export hubs).

---

## 4. The best representation — five principles

1. **Two products, one site.** The *coverage map* (what's knowable) and the *data* (the
   picture) answer different questions. Show both, clearly separated, cross-linked.
2. **Lead with the relay.** One hero visual that delivers the whole story; everything else
   is the reader pulling a thread.
3. **Country profiles are the backbone.** Navigation is by country (and by fruit). Each
   profile pairs the *data* (production, lanes, seasonality, frost, forecast) with its
   *coverage card* (free/paid/none) — object and meta side by side.
4. **Provenance-first / radical honesty.** Every number stamped with source · free|paid ·
   verified-date · provisional flag. The honesty is the brand and the moat; a figure with
   no provenance is a bug, not a feature.
5. **Progressive disclosure.** Narrative overview (anyone) → interactive explorers (analyst)
   → the registry + raw CSV/JSON (builder). One artifact, three depths.

---

## 5. Information architecture — the concrete views

1. **The Year (landing / overview).** The relay hero · production-vs-export divergence ·
   the global ranking · a world choropleth (export value). The narrative front door.
2. **Country profiles (the spine).** Per country: production/area/yield trend (FAOSTAT) ·
   its top trade lanes + $/kg (Comtrade bilateral, both sides) · its supply/demand
   seasonality · frost/temp profile (NASA POWER) · forecast (USDA) · named orchards (if any)
   · **a coverage card** from the registry (free-wired / free-unwired / paid / none).
3. **Lane & price explorer.** exporter → importer, $/kg, the export-vs-import mirror gap,
   the FOB→CIF freight wedge. The analyst's tool.
4. **The Atlas (signature).** The registry rendered as an interactive **country × data-point
   matrix**, colour-coded free/paid/none/wired, filterable — the "what can I know" map, with
   the *free ceiling vs paid layer (named brokers) vs structural gaps* framing. This is the
   thing no competitor has; give it a first-class page.
5. **Depth exemplar.** The existing UK/Chile/Peru editorial, reframed as "one lane to the
   floor" — proof the breadth is backed by real depth (named producers, varieties, the
   2-week nowcast).
6. **Commodity selector.** Blueberry now; avocado/cherry/… one parameter away. The shell is
   fruit-agnostic so the same site serves the whole Phase-4 ambition.

---

## 6. Form factor & technology

Keep what already works and scales for free:
- **Static site, zero backend, committed data, weekly-cron-regenerated** — the current
  `docs/index.html` model. Free hosting (Pages), versioned, honest, no ops.
- **But evolve it from a single 1.4 MB PNG editorial → a layered atlas.** The narrative
  heroes (relay, divergence) stay as crisp custom matplotlib PNGs; the *explorable* parts
  (country selector, coverage matrix, lane explorer) become **client-side interactive** off
  a small committed **JSON data layer** (vanilla JS or a light lib — still no backend).
- **Decouple data from render:** add an export step that emits the atlas as one clean
  `docs/data/atlas.json` the site reads. Then the page is a thin view over versioned data,
  and the same JSON powers any future native/API consumer.

---

## 7. Considered and rejected

- **Interactive BI dashboard only (Tableau/Power BI style).** Powerful for analysts, but no
  narrative, no honesty layer, needs hosting/licences, and throws away our editorial
  strength. The relay-as-a-grid-of-filters loses the story.
- **Editorial only (today's page).** Beautiful and trustworthy, but UK-only, not explorable,
  and doesn't scale to global × multi-country × multi-fruit.
- **Raw data portal / API only.** Serves builders, ignores the 99% who want the picture and
  the coverage answer. (We still ship the JSON/CSV — as a *layer*, not the product.)
- **Winner — the layered static atlas:** narrative + exploration + raw, coverage-map as the
  signature, provenance everywhere, regenerated by the existing cron. Best of all three,
  zero-backend, on-brand.

---

## 8. Build phasing (when we say go)

1. **Data-export layer** — `scripts/build_atlas_json.py` → `docs/data/atlas.json` (rankings,
   relay, bilateral, faostat, weather, forecasts, registry), provenance-stamped.
2. **The Year** — relay hero + production-vs-export + ranking + world map.
3. **Country profiles** + coverage cards (the spine).
4. **The Atlas coverage matrix** (the signature page).
5. **Lane & price explorer.**
6. **Commodity selector** (multi-fruit) + fold the UK editorial in as the depth exemplar.

---

## 9. The product, in one line

**The Global Blueberry Atlas — what the world grows, ships, and pays through the year, and
exactly what you can know about it for free.** (Fruit is a parameter.)

The data is the substance; the relay is the hook; **the coverage map is the moat**; the
provenance is the brand.
