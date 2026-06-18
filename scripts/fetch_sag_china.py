"""Fetch the SAG list of Chilean blueberry predios authorised to export to China.

SAG publishes the roster as a Power BI "publish to web" report (the SAG PDF embeds
only the link; the same data is the Excel they reference). Power BI's public
querydata API is reachable from clean egress but blocked from the Claude sandbox
(analysis.windows.net -> 503), so -- like the datos.gob.cl weekly feed -- THIS
SCRIPT IS THE ACCESS METHOD and runs on a GitHub-hosted runner.

Schema-agnostic by design: rather than hardcode table/column names, it reads the
report's model + the table visual's own prototypeQuery and replays that query, then
flattens the DSR result. So it survives the seasonal re-publish.

  inspect : resolve cluster, dump model + each visual's query (pin nothing by hand)
  collect : replay the richest table query, write data/market/sag_china_orchards.csv

First run inspect (workflow_dispatch) and read the log -- exactly how the Chile
parser was pinned on run #3 -- then switch to collect.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import time
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "market" / "sag_china_orchards.csv"

# resourceKey token from the SAG "Listado arandanos a China" PDF (publish-to-web).
TOKEN = ("eyJrIjoiZTVlNDBiM2QtNTA5NC00MTYyLThmZDgtNGEyMjMxZmI3NDg0IiwidCI6Ijc3"
         "ZWNkYTc1LTU4NjQtNDIyYS1hNTM1LTZlYTY3MTU0MDI5YyIsImMiOjR9")
VIEW = "https://app.powerbi.com/view?r=" + TOKEN
# Candidate clusters for c:4; the embed config below normally pins the real one.
_CLUSTERS = [
    "https://wabi-paas-1-scus-redirect.analysis.windows.net",
    "https://wabi-south-central-us-redirect.analysis.windows.net",
    "https://wabi-us-east2-redirect.analysis.windows.net",
    "https://wabi-west-us-redirect.analysis.windows.net",
]


def _key() -> str:
    t = TOKEN + "=" * (-len(TOKEN) % 4)
    return json.loads(base64.b64decode(t))["k"]


def _get(url: str, key: str, data: bytes | None = None) -> bytes:
    hdr = {"X-PowerBI-ResourceKey": key, "User-Agent": "Mozilla/5.0",
           "Content-Type": "application/json;charset=UTF-8",
           "Accept": "application/json, text/plain, */*",
           "ActivityId": str(uuid.uuid4()), "RequestId": str(uuid.uuid4())}
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, data=data, headers=hdr,
                                         method="POST" if data else "GET")
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:                          # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{url} failed: {last}")


def _resolve_cluster(key: str) -> str:
    """Read the embed page for the real cluster URI; fall back to the candidates."""
    try:
        html = urllib.request.urlopen(
            urllib.request.Request(VIEW, headers={"User-Agent": "Mozilla/5.0"}),
            timeout=60).read().decode("utf-8", "ignore")
        m = re.search(r"https://wabi-[\w-]+\.analysis\.windows\.net", html)
        if m:
            return m.group(0)
    except Exception:                                   # noqa: BLE001
        pass
    for c in _CLUSTERS:
        try:
            _get(f"{c}/public/reports/{key}/modelsAndExploration"
                 "?preferReadOnlySession=true", key)
            return c
        except Exception:                               # noqa: BLE001
            continue
    raise RuntimeError("could not resolve Power BI cluster")


def _model(cluster: str, key: str) -> dict:
    raw = _get(f"{cluster}/public/reports/{key}/modelsAndExploration"
               "?preferReadOnlySession=true", key)
    return json.loads(raw)


def _table_visuals(model: dict) -> list[dict]:
    """Every visual carrying a prototypeQuery, richest (most Selects) first."""
    found = []
    for exp in model.get("exploration", {}).get("report", {}).get("sections", []):
        for vc in exp.get("visualContainers", []):
            try:
                cfg = json.loads(vc.get("config", "{}"))
                q = (cfg.get("singleVisual", {}).get("prototypeQuery")
                     or cfg.get("prototypeQuery"))
                if q and q.get("Select"):
                    found.append({"visualId": cfg.get("name"), "query": q,
                                  "n_select": len(q["Select"])})
            except Exception:                           # noqa: BLE001
                continue
    return sorted(found, key=lambda v: -v["n_select"])


def _select_names(query: dict) -> list[str]:
    out = []
    for s in query.get("Select", []):
        out.append(s.get("Name") or next(
            (v.get("Property") for v in s.values() if isinstance(v, dict)
             and "Property" in v), "col"))
    return [str(n).split(".")[-1] for n in out]


def _flatten_dsr(dsr: dict, ncol: int) -> list[list]:
    """Expand a Power BI DSR (DM0 rows + ValueDicts + R/Ø repeat/null bitmask)."""
    ds = dsr["DS"][0]
    dicts = ds.get("ValueDicts", {})
    desc = ds["PH"][0]["DM0"]
    rows, prev = [], [None] * ncol
    keymap = None
    for item in desc:
        c = item.get("C", [])
        rmask = item.get("R", 0)         # bit set => repeat previous value
        nmask = item.get("Ø", 0)         # bit set => null
        row, ci = [], 0
        for j in range(ncol):
            if nmask & (1 << j):
                row.append(None); continue
            if rmask & (1 << j):
                row.append(prev[j]); continue
            val = c[ci]; ci += 1
            if isinstance(val, str) and keymap and keymap[j] in dicts:
                pass
            row.append(val)
        # resolve dictionary-encoded columns
        for j in range(ncol):
            dk = f"D{j}"
            if dk in dicts and isinstance(row[j], int):
                try:
                    row[j] = dicts[dk][row[j]]
                except Exception:                       # noqa: BLE001
                    pass
        prev = row
        rows.append(row)
    return rows


def _querydata(cluster: str, key: str, model: dict, vis: dict) -> list[list]:
    q = vis["query"]
    body = json.dumps({
        "version": "1.0.0",
        "queries": [{
            "Query": {"Commands": [{"SemanticQueryDataShapeCommand": {
                "Query": q,
                "Binding": {"Primary": {"Groupings": [
                    {"Projections": list(range(len(q["Select"])))}]},
                    "DataReduction": {"DataVolume": 4,
                                      "Primary": {"Window": {"Count": 30000}}},
                    "Version": 1}}}]},
            "QueryId": "",
            "ApplicationContext": {"DatasetId": model.get("models", [{}])[0].get("dbName", ""),
                                   "Sources": [{"ReportId": model.get("exploration", {})
                                                .get("report", {}).get("objectId", ""),
                                                "VisualId": vis["visualId"]}]}}],
        "cancelQueries": [], "modelId": model.get("models", [{}])[0].get("id", 0),
    }).encode()
    raw = json.loads(_get(f"{cluster}/public/reports/querydata?synchronous=true",
                          key, data=body))
    dsr = raw["results"][0]["result"]["data"]["dsr"]
    return _flatten_dsr(dsr, len(q["Select"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["inspect", "collect"], default="inspect")
    args = ap.parse_args()

    key = _key()
    cluster = _resolve_cluster(key)
    print(f"cluster: {cluster}")
    model = _model(cluster, key)
    visuals = _table_visuals(model)
    print(f"models: {[m.get('dbName') for m in model.get('models', [])]}")
    print(f"table visuals found: {len(visuals)}")
    for v in visuals[:5]:
        print(f"  visual {v['visualId']}  cols={v['n_select']}: {_select_names(v['query'])}")

    if args.mode == "inspect":
        print("INSPECT only -- rerun with --mode collect once the richest visual "
              "above looks like the predio roster.")
        return

    if not visuals:
        raise RuntimeError("no table visual with a prototypeQuery found")
    vis = visuals[0]
    cols = _select_names(vis["query"])
    rows = _querydata(cluster, key, model, vis)
    import csv
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(cols); w.writerows(rows)
    print(f"wrote {len(rows)} predios -> {OUT}")


if __name__ == "__main__":
    main()
