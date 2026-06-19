"""Reachability probe for atlas sources — the standing rule, operationalised.

Phase 2 catalogues national overlay sources per country but *does not wire* them;
the discipline is "verify a source is reachable/parseable before building on it".
This module classifies a URL from *this* environment into one honest status, so a
registry row's `verified_date` means something and its `access` reflects reality:

    reachable    — HTTP 200, real content
    key_gated    — HTTP 200 but the body is an "API key required" notice
                   (e.g. US Census returns 200 + a Missing Key page)
    auth         — 401/403 (login / credential wall)
    not_found    — 404 (dead/moved endpoint)
    rate_limited — 429
    tls_blocked  — TLS/cert failure (the sandbox MITM/selective-egress case)
    unreachable  — DNS / connection error
    error        — anything else

Note (HANDOFF gotcha): sandbox egress is selective — a `tls_blocked`/`unreachable`
here often works from the GitHub runner's clean egress. So a probe FAIL is a flag
to re-probe on the runner, not proof the source is dead.
"""
from __future__ import annotations

import datetime as _dt
import ssl
import urllib.error
import urllib.request

# Body fingerprints that mean "200 OK, but you still need a (free) key/login".
_KEY_HINTS = ("missing key", "valid key", "api key", "api_key", "sign up for a key",
              "subscription key", "requires authentication", "please log in",
              "access denied", "register for an api")


def classify(url: str, timeout: int = 30) -> tuple[str, str]:
    """Return (status, detail) for a single URL. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(2048).decode("utf-8", "replace")
            low = body.lower()
            if any(h in low for h in _KEY_HINTS):
                return "key_gated", "HTTP 200 but body asks for an API key/login"
            return "reachable", f"HTTP {r.status}, {len(body)}b sniffed"
    except urllib.error.HTTPError as e:
        code = e.code
        if code in (401, 403):
            return "auth", f"HTTP {code}"
        if code == 404:
            return "not_found", "HTTP 404"
        if code == 429:
            return "rate_limited", "HTTP 429"
        return "error", f"HTTP {code}"
    except (ssl.SSLError, urllib.error.URLError) as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, ssl.SSLError) or "SSL" in str(reason) or "certificate" in str(reason).lower():
            return "tls_blocked", str(reason)[:120]
        return "unreachable", str(reason)[:120]
    except Exception as e:                              # noqa: BLE001
        return "error", f"{type(e).__name__}: {str(e)[:100]}"


# Probe status -> the atlas `access` it implies (None = leave the catalogued value).
# A reachable/key-gated free source stays `free`; an auth wall usually means the
# free path is gone (paid/registration). Network-shaped failures imply nothing
# about access (likely sandbox egress) so they leave `access` untouched.
_ACCESS_HINT = {"reachable": "free", "key_gated": "free", "auth": None,
                "not_found": None, "rate_limited": "free", "tls_blocked": None,
                "unreachable": None, "error": None}


def probe(url: str, timeout: int = 30) -> dict:
    """Probe one URL; return a record with status, detail, access hint, date."""
    status, detail = classify(url, timeout)
    return {"url": url, "status": status, "detail": detail,
            "access_hint": _ACCESS_HINT.get(status),
            "verified_date": _dt.date.today().isoformat()}


if __name__ == "__main__":                             # python -m atlas.probe URL [URL ...]
    import sys
    for u in sys.argv[1:]:
        rec = probe(u)
        print(f"{rec['status']:12s} {rec['detail'][:60]:60s} {u}")
