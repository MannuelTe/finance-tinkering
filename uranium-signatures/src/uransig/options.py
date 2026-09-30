"""Options footprints before the news, from Massive (formerly Polygon.io).

Informed traders like options: little capital, lots of leverage, and a short-dated
out-of-the-money contract pays off only if the news comes. So the screen asks: in the
ten sessions before day 0, was there unusual volume in *directional* options, meaning

* calls struck above spot before bullish news, puts struck below spot before bearish news,
* expiring within HORIZON calendar days (an insider has no reason to pay for time),
* with the strike no more than MAX_OTM away from spot (lottery tickets are noise)?

Daily directional volume is summed over all such contracts, logged, and compared with
the same measure over the baseline, days -60 to -11:

    z_opt = (mean log(1 + V) over -10..-1  -  mean over -60..-11) / sd over -60..-11

Contracts are listed from three snapshots (days -60, -35 and -10) so short-dated
contracts are in the baseline as well as the window. Every HTTP response is cached
under data/cache/massive/, so a second run costs no API calls.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "massive"
BASE = "https://api.massive.com"
HORIZON = 60          # calendar days to expiry, at the time of trading
MAX_OTM = 0.30        # strike at most 30% beyond spot
BASELINE = (-60, -11)
WINDOW = (-10, -1)
SNAPSHOTS = (-60, -35, -10)
Z_MIN = 2.0


def load_env(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader: KEY=value lines, no overriding of variables already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Client:
    """Tiny REST client: bearer auth, disk cache, pagination and a calls-per-minute limit."""

    key: str = ""
    calls_per_min: float = 5
    cache: Path = CACHE
    fetch: object = None       # injectable transport for tests: fetch(url, headers) -> dict
    calls: int = field(default=0, init=False)
    _last: float = field(default=0.0, init=False)

    @classmethod
    def from_env(cls) -> Client:
        load_env()
        key = os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY", "")
        if not key:
            raise SystemExit("No API key: copy .env.example to .env and set MASSIVE_API_KEY.")
        return cls(key=key, calls_per_min=float(os.environ.get("MASSIVE_CALLS_PER_MIN", "5")))

    def _path(self, url: str) -> Path:
        return self.cache / (hashlib.sha1(url.encode()).hexdigest() + ".json")

    def _http(self, url: str) -> dict:
        if self.fetch is not None:
            return self.fetch(url, {"Authorization": f"Bearer {self.key}"})
        for attempt in range(5):
            if self.calls_per_min > 0:
                wait = 60 / self.calls_per_min - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
            self._last = time.monotonic()
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.key}"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 4:
                    time.sleep(15 * (attempt + 1))
                    continue
                raise
        raise RuntimeError("unreachable")

    def get(self, path: str, **params) -> dict:
        """GET with caching. `path` may be a full next_url from a previous page."""
        url = path if path.startswith("http") else BASE + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        p = self._path(url)
        if p.exists():
            return json.loads(p.read_text())
        data = self._http(url)
        self.calls += 1
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
        return data

    def pages(self, path: str, **params) -> list[dict]:
        out, data = [], self.get(path, **params)
        out += data.get("results", [])
        while data.get("next_url"):
            data = self.get(data["next_url"])
            out += data.get("results", [])
        return out

    def contracts(self, underlying, as_of, kind, exp_to, strike_lo, strike_hi) -> list[dict]:
        """Contracts of one type listed on `as_of` and expiring by `exp_to` (both states:
        long-expired contracts need expired=true, still-live ones expired=false)."""
        rows = []
        for expired in ("true", "false"):
            rows += self.pages("/v3/reference/options/contracts", underlying_ticker=underlying,
                               contract_type=kind, as_of=as_of, expired=expired,
                               **{"expiration_date.gte": as_of, "expiration_date.lte": exp_to,
                                  "strike_price.gte": round(strike_lo, 2),
                                  "strike_price.lte": round(strike_hi, 2)}, limit=1000)
        return list({r["ticker"]: r for r in rows}.values())

    def daily(self, ticker: str, start: str, end: str) -> pd.Series:
        """Daily volume of one contract (missing days = no trades)."""
        res = self.pages(f"/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
                         adjusted="true", sort="asc", limit=50000)
        if not res:
            return pd.Series(dtype=float)
        idx = pd.to_datetime([r["t"] for r in res], unit="ms").normalize()
        return pd.Series([r["v"] for r in res], index=idx, dtype=float)


def plan(index: pd.DatetimeIndex, pos: int, spot: pd.Series, kind: str):
    """Contract-listing requests for one event: (as_of, expiry cap, strike range) per snapshot."""
    out = []
    for s in SNAPSHOTS:
        d = index[pos + s]
        px = spot.loc[:d].dropna().iloc[-1]
        lo, hi = (px, px * (1 + MAX_OTM)) if kind == "call" else (px * (1 - MAX_OTM), px)
        # wider strike range than needed: moneyness is re-checked day by day below
        lo, hi = lo * 0.85, hi * 1.15
        out.append((d.date().isoformat(), (d + pd.Timedelta(days=HORIZON)).date().isoformat(),
                    lo, hi))
    return out


def directional_volume(contracts: list[dict], vols: dict[str, pd.Series], spot: pd.Series,
                       days: pd.DatetimeIndex, kind: str) -> pd.Series:
    """Per day: volume in contracts that were short-dated and moderately out of the money
    *on that day*, in the news direction."""
    total = pd.Series(0.0, index=days)
    for c in contracts:
        v = vols.get(c["ticker"])
        if v is None or v.empty:
            continue
        v = v.reindex(days).fillna(0.0)
        exp = pd.Timestamp(c["expiration_date"])
        k = float(c["strike_price"])
        s = spot.reindex(days).ffill()
        dte = (exp - days).days
        m = k / s - 1 if kind == "call" else 1 - k / s
        ok = (dte >= 0) & (dte <= HORIZON) & (m >= 0) & (m <= MAX_OTM)
        total += v.where(ok, 0.0)
    return total


def z_score(vol: pd.Series, day0_pos: int) -> dict:
    """Window vs baseline on log(1 + volume); positions relative to day 0 in `vol`."""
    lv = np.log1p(vol.to_numpy())
    b = lv[day0_pos + BASELINE[0]: day0_pos + BASELINE[1] + 1]
    w = lv[day0_pos + WINDOW[0]: day0_pos + WINDOW[1] + 1]
    sd = b.std(ddof=1)
    base_mean = float(np.expm1(b).mean())
    return {"z": float((w.mean() - b.mean()) / sd) if sd > 0 else np.nan,
            "window_avg": float(np.expm1(w).mean()), "baseline_avg": base_mean,
            "ratio": float(np.expm1(w).mean() / base_mean) if base_mean > 0 else np.nan,
            "peak_day_z": float((w.max() - b.mean()) / sd) if sd > 0 else np.nan}


def screen_event(client: Client, underlying: str, day0: pd.Timestamp, direction: str,
                 index: pd.DatetimeIndex, spot: pd.Series, dry_run=False) -> dict:
    """Directional-options footprint of one event on one underlying."""
    pos = index.get_loc(day0)
    kind = "call" if direction == "bull" else "put"
    contracts = []
    for as_of, exp_to, lo, hi in plan(index, pos, spot, kind):
        contracts += client.contracts(underlying, as_of, kind, exp_to, lo, hi)
    contracts = list({c["ticker"]: c for c in contracts}.values())
    out = {"underlying": underlying, "contracts": len(contracts)}
    if dry_run:
        return out
    start = index[pos + BASELINE[0]].date().isoformat()
    end = index[pos + 1].date().isoformat()
    vols = {c["ticker"]: client.daily(c["ticker"], start, end) for c in contracts}
    days = index[pos + BASELINE[0]: pos + 2]
    dv = directional_volume(contracts, vols, spot, days, kind)
    return {**out, **z_score(dv, -BASELINE[0]), "flag": None, "series": dv}
