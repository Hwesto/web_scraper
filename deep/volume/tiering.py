"""Confidence tiers and methods (spec section 5).

Every emitted volume point carries one tier so a `nowcast` or `aggregate` point
is never shown as if it were an observed `shipment`.
"""
from __future__ import annotations

# Confidence tiers, best-known first.
SHIPMENT = "shipment"                       # reconstructed from origin consignments
MIRROR = "mirror"                           # paid reconstructed consignee data
AGGREGATE_BENCHMARKED = "aggregate_benchmarked"   # HMRC level + indicator shape
NOWCAST = "nowcast"                         # modelled, pre-HMRC, with band

# Methods (how the number was produced).
M_SHIPMENT_RECON = "shipment_recon"
M_ASSOC_BENCHMARKED = "assoc_benchmarked"
M_MIRROR = "mirror"
M_NOWCAST = "nowcast"

TIER_RANK = {SHIPMENT: 0, MIRROR: 1, AGGREGATE_BENCHMARKED: 2, NOWCAST: 3}
