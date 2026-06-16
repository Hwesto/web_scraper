# UK Blueberry Hidden-Flow Nowcast

Estimating the opaque EU/Morocco -> UK blueberry import flow weekly and in real
time, ahead of HMRC's ~6-week-lagged monthly print, by fusing free signals into
a mixed-frequency state-space (Kalman) model.

This README tracks **what is actually built and verified**, not the full vision.
The full design and the data-source stress test live in the project discussion.

## Status

| Milestone | What | State |
|---|---|---|
| **M1** | Real data ingest + append-only vintage store | **done, real data** |
| M2 | K=1 volume-space state-space + Kalman + EM calibration | not started |
| M3 | Walk-forward vintage backtest vs seasonal-naive / persistence / ARIMA | not started |
| M4 | Sentinel-2 NDVI forward signal (optional) | not started |
| M5 | Forward-collect alt-data (packhouse hiring; clock started in M1) | stub wired |

**M3 is the gate:** ship nothing until it provably beats seasonal-naive at a
useful lead. Alt-data (M5) never counts toward this gate — it has no history.

## Verified data sources (free)

- **HMRC OTS** (`data/hmrc.py`) — anchor + ground truth. Live OData API,
  CN8 `08104050` (cultivated blueberry + cranberry), `NetMass` kg -> tonnes.
  Real pull confirmed: 2018-01 .. 2026-04, 6 origins.
- **DEFRA wholesale price** (`data/defra_price.py`) — price/demand context.
  Machine-readable CSV, blueberry line, GBP/kg.

## Real-data findings (M1)

1. **Morocco is exploding**: ~1,750 t (2018) -> 18,066 t (2025), now 5-6x Spain
   and rising fast. The local-linear-trend (`level`+`slope`) state is there to
   absorb exactly this. Spain is stable (~2.5-4.8k t/yr) and cleanly seasonal,
   peaking May-Jun; Morocco peaks Jan-Apr -> anti-phase, extended import window.
2. **Strong, clean seasonality** => seasonal-naive is a stiff benchmark. The
   tradeable alpha is the *anomaly* around the seasonal norm, not the level.
3. **EU/non-EU collection seam**: Spain/PT/NL arrive via FlowType 1 (EU,
   Intrastat-derived); Morocco/Peru/Chile via FlowType 3 (non-EU, customs).
   Different methods -> a consistency seam, worst around the post-Brexit break.
4. **DEFRA price is anti-aligned with the target season**: it only quotes
   blueberries while UK home-grown is in season (~Jun-Nov) and is silent Dec-May
   — exactly the import window we care about. So DEFRA is an off-season/price
   context input; the intended in-season weekly driver is **retail-price
   scraping** (year-round supermarket prices), to be added in M2.
5. **Vintage caveat**: the live APIs serve only the *current* revision, so true
   historical vintages cannot be reconstructed — they accrue from the first pull
   forward. The store is built so that, going forward, the backtest reads each
   series exactly as it stood at decision time.

## Usage

```bash
pip install -r nowcast/requirements.txt
python3 -m nowcast.pipeline ingest          # pull all sources -> dated snapshots
python3 -m nowcast.pipeline show hmrc_blueberry_imports -n 12
pytest tests/ -q
```

Run `ingest` on a schedule to accrue the revision history M3 replays.

## Rejected alt-data methods

Real techniques that fail a hard constraint we set (see `config.REJECTED_SIGNALS`):
tasking satellites & sub-metre optical (paid), thermal reefer counting (free TIR
is 70-100 m, can't resolve ~12 m containers), freight load boards (account-gated,
ToS), container-number enumeration on Destin8/Portbase (**UK Computer Misuse Act
risk**), historical AIS (paid; target flow is road not deep-sea), Kantar (paid).
