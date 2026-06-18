"""Where should Chilean fruit be sold? -- destination economics from the grower's seat.

Two layers:
  comtrade.py  -- the observed price each destination pays (UN Comtrade, free, real)
  netback.py   -- grower netback = CIF price - ocean freight, ranked across markets

The discipline: only one *assumed* number in the whole model (ocean freight per kg).
Everything else -- the price each market pays, the volume it absorbs, its growth --
is observed from Comtrade. Tariffs and transit times are known constants.
"""
