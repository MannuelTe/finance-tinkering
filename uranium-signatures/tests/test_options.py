import json
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

from uransig import options


def _fake_api(n_days=80, spike=0.0, seed=0):
    """A fake Massive API: two call contracts, one near the money and one deep OTM."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-01-02", periods=n_days)
    contracts = [
        {"ticker": "O:XYZ250530C00105000", "strike_price": 105, "expiration_date": "2025-05-30"},
        {"ticker": "O:XYZ250530C00200000", "strike_price": 200, "expiration_date": "2025-05-30"},
    ]
    vols = {c["ticker"]: rng.poisson(200, n_days).astype(float) for c in contracts}
    day0 = 70
    vols[contracts[0]["ticker"]][day0 - 10:day0] *= spike + 1  # informed buying, near money
    vols[contracts[1]["ticker"]][day0 - 10:day0] *= 50         # deep OTM noise: must be ignored
    calls = []

    def fetch(url, headers):
        calls.append(url)
        assert headers["Authorization"] == "Bearer k"
        u = urlparse(url)
        if u.path == "/v3/reference/options/contracts":
            q = parse_qs(u.query)
            if q.get("cursor"):
                return {"results": [contracts[1]]}
            return {"results": [contracts[0]], "next_url": options.BASE + u.path + "?cursor=2"}
        t = u.path.split("/")[4]
        return {"results": [{"t": int(d.timestamp() * 1000), "v": v}
                            for d, v in zip(days, vols[t])]}

    return fetch, days, day0, calls


def _run(tmp_path, spike):
    fetch, days, day0, calls = _fake_api(spike=spike)
    client = options.Client(key="k", calls_per_min=0, cache=tmp_path, fetch=fetch)
    spot = pd.Series(100.0, index=days)
    r = options.screen_event(client, "XYZ", days[day0], "bull", days, spot)
    return r, client, calls


@pytest.fixture(autouse=True)
def long_horizon(monkeypatch):
    monkeypatch.setattr(options, "HORIZON", 200)  # the fake contracts stay "short-dated"


def test_directional_spike_is_detected_and_deep_otm_ignored(tmp_path):
    quiet, _, _ = _run(tmp_path / "a", spike=0.0)
    loud, _, _ = _run(tmp_path / "b", spike=4.0)
    assert quiet["contracts"] == 2
    assert abs(quiet["z"]) < 2      # the 50x deep-OTM burst is outside MAX_OTM
    assert loud["z"] > 2 and loud["ratio"] > 3


def test_pagination_and_cache(tmp_path):
    r, client, calls = _run(tmp_path, spike=0.0)
    first = client.calls
    assert first == len(calls) > 0
    days = pd.bdate_range("2025-01-02", periods=80)
    r2 = options.screen_event(client, "XYZ", days[70], "bull", days, pd.Series(100.0, index=days))
    assert client.calls == first    # the identical rerun is served from the cache
    assert all(json.loads(p.read_text()) for p in tmp_path.glob("*.json"))
    assert r2["z"] == r["z"]
