"""Moteur ICT / Smart Money — fidèle au cours Warren (ESLSCA) :
swings, MSB/MSS, orderblocks (méthodes A/B/C), breakers, FVG, sweeps/SFP,
ranges + EQ + premium/discount + OTE 0.705, Monday range, sessions/kill zones, POC.
Aucune fonction ne regarde le futur : tout est calculé sur les bougies fournies."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import resample

OTE_LOW, OTE_MID, OTE_HIGH = 0.62, 0.705, 0.79

# Kill zones ICT, heure de New York
KILLZONES = [
    ("Asie", 20, 0, 24, 0),
    ("London KZ", 2, 0, 5, 0),
    ("NY AM KZ", 7, 0, 10, 0),
    ("Silver Bullet AM", 10, 0, 11, 0),
    ("NY Lunch", 12, 0, 13, 30),
    ("NY PM KZ", 13, 30, 16, 0),
]
# Sessions du cours (GMT) converties approximativement en heure NY pour l'affichage
SESSIONS_BOXES = [
    ("Asie", 20, 0, 24, 0, "rgba(120,120,120,0.07)"),
    ("Londres", 2, 0, 5, 0, "rgba(31,78,154,0.07)"),
    ("New York AM", 9, 30, 11, 30, "rgba(184,92,0,0.07)"),
]


def killzone(ts: pd.Timestamp) -> str:
    m = ts.hour * 60 + ts.minute
    for name, h1, m1, h2, m2 in KILLZONES:
        if h1 * 60 + m1 <= m < h2 * 60 + m2:
            return name
    return "Hors kill zone"


def trading_date(idx: pd.DatetimeIndex) -> pd.Index:
    """Les futures CME ouvrent à 18h NY : la journée de trading commence la veille à 18h."""
    return (idx + pd.Timedelta(hours=6)).date


# ------------------------------------------------------------------ swings
def find_swings(df: pd.DataFrame, n: int = 2):
    h, l = df["high"].values, df["low"].values
    N = len(df)
    sh = np.zeros(N, bool)
    sl = np.zeros(N, bool)
    for i in range(n, N - n):
        win_h = h[i - n:i + n + 1]
        win_l = l[i - n:i + n + 1]
        if h[i] == win_h.max() and (win_h == h[i]).sum() == 1:
            sh[i] = True
        if l[i] == win_l.min() and (win_l == l[i]).sum() == 1:
            sl[i] = True
    return sh, sl


# ---------------------------------------------------------- structure (MSB)
def market_structure(df: pd.DataFrame, n: int = 2):
    """Cassure validée à la CLÔTURE (comme dans le cours). BOS = continuation, MSS = changement."""
    sh, sl = find_swings(df, n)
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    events, trend = [], np.zeros(len(df), int)
    last_sh = last_sl = None  # (index, prix)
    used_sh = used_sl = -1
    cur = 0
    for i in range(len(df)):
        j = i - n  # un swing en j n'est connu qu'en i = j + n
        if j >= 0:
            if sh[j]:
                last_sh = (j, h[j])
            if sl[j]:
                last_sl = (j, l[j])
        if last_sh and last_sh[0] != used_sh and c[i] > last_sh[1]:
            kind = "MSS" if cur == -1 else "BOS"
            events.append(dict(i=i, dir=1, kind=kind, level=last_sh[1], swing_i=last_sh[0]))
            used_sh, cur = last_sh[0], 1
        elif last_sl and last_sl[0] != used_sl and c[i] < last_sl[1]:
            kind = "MSS" if cur == 1 else "BOS"
            events.append(dict(i=i, dir=-1, kind=kind, level=last_sl[1], swing_i=last_sl[0]))
            used_sl, cur = last_sl[0], -1
        trend[i] = cur
    return events, trend, sh, sl


# ------------------------------------------------------------- orderblocks
def order_blocks(df: pd.DataFrame, events: list, lookback: int = 30):
    """OB = dernière bougie opposée avant le mouvement qui a cassé la structure.
    Suivi : mitigé (retouché) / cassé -> devient BREAKER de polarité inverse."""
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    N = len(df)
    obs = []
    for ev in events:
        i, d, s = ev["i"], ev["dir"], ev["swing_i"]
        start = max(0, min(s, i) - 3)
        if d == 1:
            ext = start + int(np.argmin(l[start:i + 1]))
            cand = [j for j in range(ext, max(start, ext - lookback) - 1, -1) if c[j] < o[j]]
        else:
            ext = start + int(np.argmax(h[start:i + 1]))
            cand = [j for j in range(ext, max(start, ext - lookback) - 1, -1) if c[j] > o[j]]
        if not cand:
            continue
        j = cand[0]
        ob = dict(dir=d, i=j, formed_i=i, top=float(h[j]), bottom=float(l[j]), kind=ev["kind"],
                  ext_i=ext, ext_price=float(l[ext] if d == 1 else h[ext]), status="actif",
                  touches=0, first_touch_i=None, broken_i=None, breaker=False,
                  breaker_status=None, breaker_touch_i=None, breaker_invalid_i=None)
        for k in range(i + 1, N):
            if not ob["breaker"]:
                touched = l[k] <= ob["top"] if d == 1 else h[k] >= ob["bottom"]
                if touched:
                    ob["touches"] += 1
                    ob["first_touch_i"] = ob["first_touch_i"] if ob["first_touch_i"] is not None else k
                    ob["status"] = "mitigé"
                broken = c[k] < ob["bottom"] if d == 1 else c[k] > ob["top"]
                if broken:
                    ob.update(breaker=True, broken_i=k, status="cassé → breaker", breaker_status="actif")
            else:
                # breaker baissier (OB haussier cassé) : retest par le bas, invalidé si clôture au-dessus
                if d == 1:
                    if h[k] >= ob["bottom"] and ob["breaker_touch_i"] is None:
                        ob["breaker_touch_i"], ob["breaker_status"] = k, "retesté"
                    if c[k] > ob["top"]:
                        ob["breaker_invalid_i"], ob["breaker_status"] = k, "invalidé"
                        break
                else:
                    if l[k] <= ob["top"] and ob["breaker_touch_i"] is None:
                        ob["breaker_touch_i"], ob["breaker_status"] = k, "retesté"
                    if c[k] < ob["bottom"]:
                        ob["breaker_invalid_i"], ob["breaker_status"] = k, "invalidé"
                        break
        obs.append(ob)
    return obs


# ---------------------------------------------------------------- FVG
def fair_value_gaps(df: pd.DataFrame, min_size: float = 2.0):
    h, l = df["high"].values, df["low"].values
    N = len(df)
    out = []
    for i in range(2, N):
        if l[i] > h[i - 2] and l[i] - h[i - 2] >= min_size:
            out.append(dict(dir=1, i=i - 1, top=float(l[i]), bottom=float(h[i - 2]), filled_i=None, status="ouvert"))
        elif h[i] < l[i - 2] and l[i - 2] - h[i] >= min_size:
            out.append(dict(dir=-1, i=i - 1, top=float(l[i - 2]), bottom=float(h[i]), filled_i=None, status="ouvert"))
    for g in out:
        for k in range(g["i"] + 2, N):
            if g["dir"] == 1 and l[k] <= g["top"]:
                g["status"] = "comblé" if l[k] <= g["bottom"] else "partiel"
                if g["status"] == "comblé":
                    g["filled_i"] = k
                    break
            if g["dir"] == -1 and h[k] >= g["bottom"]:
                g["status"] = "comblé" if h[k] >= g["top"] else "partiel"
                if g["status"] == "comblé":
                    g["filled_i"] = k
                    break
    return out


# ------------------------------------------------------- liquidity sweeps
def liquidity_sweeps(df: pd.DataFrame, sh, sl, n: int = 2, max_age: int = 300):
    """SFP : la mèche prend un swing mais la bougie clôture de retour dans le range.
    dir=+1 : sell-side (bas) balayé -> signal haussier ; dir=-1 : buy-side (haut) balayé -> baissier."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    pools_h, pools_l, out = [], [], []
    for i in range(len(df)):
        j = i - n
        if j >= 0:
            if sh[j]:
                pools_h.append(j)
            if sl[j]:
                pools_l.append(j)
        for j in list(pools_h):
            if i - j > max_age:
                pools_h.remove(j)
            elif h[i] > h[j]:
                if c[i] < h[j]:
                    out.append(dict(i=i, dir=-1, level=float(h[j]), swing_i=j))
                pools_h.remove(j)
        for j in list(pools_l):
            if i - j > max_age:
                pools_l.remove(j)
            elif l[i] < l[j]:
                if c[i] > l[j]:
                    out.append(dict(i=i, dir=1, level=float(l[j]), swing_i=j))
                pools_l.remove(j)
    return out


def equal_levels(df, sh, sl, tol: float = 3.0, max_gap: int = 200):
    """Equal highs / equal lows : poches de liquidité évidentes (stops)."""
    h, l = df["high"].values, df["low"].values
    res = []
    idx_h, idx_l = np.where(sh)[0], np.where(sl)[0]
    for arr, price, kind in [(idx_h, h, "EQH"), (idx_l, l, "EQL")]:
        for a in range(len(arr) - 1):
            for b in range(a + 1, len(arr)):
                if arr[b] - arr[a] > max_gap:
                    break
                if abs(price[arr[a]] - price[arr[b]]) <= tol:
                    res.append(dict(kind=kind, i1=int(arr[a]), i2=int(arr[b]),
                                    level=float((price[arr[a]] + price[arr[b]]) / 2)))
    return res[-8:]


# ------------------------------------------------- range / EQ / OTE
def dealing_range(df: pd.DataFrame, sh=None, sl=None, n: int = 2):
    """Range de travail = derniers swings MAJEURS (fractale large) -> EQ (0.5), premium/discount, OTE."""
    N = len(df)
    big = max(5, 3 * n)
    sh, sl = find_swings(df, big)
    n = big
    hi_idx = [i for i in np.where(sh)[0] if i + n < N]
    lo_idx = [i for i in np.where(sl)[0] if i + n < N]
    if not hi_idx or not lo_idx:
        return None
    hi_i, lo_i = hi_idx[-1], lo_idx[-1]
    hi, lo = float(df["high"].iloc[hi_i]), float(df["low"].iloc[lo_i])
    if hi <= lo:
        return None
    leg_up = lo_i < hi_i  # jambe haussière : on cherche des achats en discount
    rng = hi - lo
    if leg_up:
        ote = (hi - OTE_HIGH * rng, hi - OTE_LOW * rng, hi - OTE_MID * rng)
    else:
        ote = (lo + OTE_LOW * rng, lo + OTE_HIGH * rng, lo + OTE_MID * rng)
    price = float(df["close"].iloc[-1])
    pos = (price - lo) / rng
    if pos > 1:
        zone = "AU-DESSUS du range (expansion)"
    elif pos < 0:
        zone = "SOUS le range (expansion)"
    else:
        zone = "PREMIUM" if pos > 0.55 else ("DISCOUNT" if pos < 0.45 else "EQ (équilibre)")
    return dict(hi=hi, lo=lo, hi_i=int(hi_i), lo_i=int(lo_i), eq=lo + rng / 2, leg_up=leg_up,
                ote_bottom=min(ote[0], ote[1]), ote_top=max(ote[0], ote[1]), ote_705=ote[2],
                position=pos, zone=zone)


# ----------------------------------------------------------- key levels
def key_levels(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    td = pd.Series(trading_date(df.index), index=df.index)
    last_td = td.iloc[-1]
    days = sorted(td.unique())
    lv = {}
    today = df[td == last_td]
    if len(days) >= 2:
        prev = df[td == days[-2]]
        lv["PDH"], lv["PDL"] = float(prev["high"].max()), float(prev["low"].min())
    t = df.index
    mid = df[(t.date == t[-1].date()) & (t.hour == 0)]
    if not mid.empty:
        lv["Midnight Open"] = float(mid["open"].iloc[0])
    ny = df[(t.date == t[-1].date()) & (t.hour == 9) & (t.minute >= 30)]
    if not ny.empty:
        lv["NY Open 9:30"] = float(ny["open"].iloc[0])
    # Semaine de trading : commence dimanche 18h NY
    wk = pd.Series([(pd.Timestamp(d) - pd.Timedelta(days=pd.Timestamp(d).dayofweek)).date() for d in td], index=df.index)
    this_wk = wk.iloc[-1]
    wdf = df[wk == this_wk]
    if not wdf.empty:
        lv["Weekly Open"] = float(wdf["open"].iloc[0])
        mon = wdf[[pd.Timestamp(d).dayofweek == 0 for d in td[wk == this_wk]]]
        if not mon.empty:
            lv["Monday High"], lv["Monday Low"] = float(mon["high"].max()), float(mon["low"].min())
    weeks = sorted(wk.unique())
    if len(weeks) >= 2:
        pw = df[wk == weeks[-2]]
        lv["PWH"], lv["PWL"] = float(pw["high"].max()), float(pw["low"].min())
    asia = today[(today.index.hour >= 20) | (today.index.hour < 0)]
    if asia.empty:
        asia = today[today.index.hour >= 18]
    if not asia.empty:
        lv["Asia High"], lv["Asia Low"] = float(asia["high"].max()), float(asia["low"].min())
    lon = today[(today.index.hour >= 2) & (today.index.hour < 5)]
    if not lon.empty:
        lv["London High"], lv["London Low"] = float(lon["high"].max()), float(lon["low"].min())
    return lv


def volume_profile(df: pd.DataFrame, bins: int = 40) -> dict | None:
    """POC / VAH / VAL (zone de valeur ~70 %) — proxy TPO/Market Profile du cours."""
    if df.empty or df["high"].max() == df["low"].min():
        return None
    edges = np.linspace(df["low"].min(), df["high"].max(), bins + 1)
    mids = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(bins)
    w = df["volume"].values if df["volume"].sum() > 0 else np.ones(len(df))
    for lo, hi, v in zip(df["low"].values, df["high"].values, w):
        a, b = np.searchsorted(edges, lo, "right") - 1, np.searchsorted(edges, hi, "right") - 1
        a, b = max(a, 0), min(b, bins - 1)
        vol[a:b + 1] += v / (b - a + 1)
    poc = int(vol.argmax())
    tot, acc, lo_k, hi_k = vol.sum(), vol[poc], poc, poc
    while acc < 0.70 * tot and (lo_k > 0 or hi_k < bins - 1):
        up = vol[hi_k + 1] if hi_k < bins - 1 else -1
        dn = vol[lo_k - 1] if lo_k > 0 else -1
        if up >= dn:
            hi_k += 1
            acc += up
        else:
            lo_k -= 1
            acc += dn
    return dict(poc=float(mids[poc]), vah=float(edges[hi_k + 1]), val=float(edges[lo_k]),
                mids=mids, vol=vol)


# --------------------------------------------------------- full analysis
@dataclass
class Analysis:
    df: pd.DataFrame
    swing_n: int
    events: list = field(default_factory=list)
    trend: np.ndarray = None
    sh: np.ndarray = None
    sl: np.ndarray = None
    obs: list = field(default_factory=list)
    fvgs: list = field(default_factory=list)
    sweeps: list = field(default_factory=list)
    eq_levels: list = field(default_factory=list)
    rng: dict | None = None
    levels: dict = field(default_factory=dict)
    profile: dict | None = None
    htf: dict = field(default_factory=dict)
    setups: list = field(default_factory=list)
    bias: str = "Neutre"
    bias_score: int = 0


def htf_trend(df: pd.DataFrame, rule: str, n: int = 2) -> int:
    r = resample(df, rule)
    if len(r) < 10:
        return 0
    _, tr, _, _ = market_structure(r, n)
    return int(tr[-1])


def detect_setups(a: Analysis, max_sweep_gap: int = 40):
    """Modèle 'Méthode C / Breaker Strategy' du cours :
    sweep de liquidité -> MSS dans le sens opposé -> retour dans l'OB/breaker (idéalement OTE)."""
    df = a.df
    N = len(df)
    if N < 30:
        return []
    price = float(df["close"].iloc[-1])
    out = []
    for ob in a.obs[-12:]:
        if ob["formed_i"] < N - 150:
            continue
        d = ob["dir"]
        zone_dir, top, bot, label = d, ob["top"], ob["bottom"], f"OB {'haussier' if d == 1 else 'baissier'}"
        if ob["breaker"]:
            if ob["breaker_status"] == "invalidé":
                continue
            zone_dir, label = -d, f"Breaker {'baissier' if d == 1 else 'haussier'}"
        elif ob["status"] == "cassé → breaker":
            continue
        sweep_before = [s for s in a.sweeps if s["dir"] == zone_dir and
                        ob["formed_i"] - max_sweep_gap <= s["i"] <= ob["formed_i"]]
        if ob["breaker"]:
            sweep_before = [s for s in a.sweeps if s["dir"] == zone_dir and
                            ob["broken_i"] - max_sweep_gap <= s["i"] <= ob["broken_i"]] or sweep_before
        in_zone = bot - 2 <= price <= top + 2
        dist = 0.0 if in_zone else min(abs(price - top), abs(price - bot))
        hgt = max(top - bot, 1.0)
        near = [x["level"] for x in sweep_before
                if (x["level"] <= bot if zone_dir == 1 else x["level"] >= top)
                and abs(x["level"] - (bot if zone_dir == 1 else top)) <= 3 * hgt + 15]
        h_, l_ = df["high"].values, df["low"].values
        if zone_dir == 1:
            entry, sl = top, bot - 2.0
            if near:
                sl = min(sl, min(near) - 2.0)
            highs = [h_[k] for k in np.where(a.sh)[0] if h_[k] > entry + 2 * (entry - sl)]
            tgt = min(highs, key=lambda x: x - entry) if highs else entry + 3 * (entry - sl)
        else:
            entry, sl = bot, top + 2.0
            if near:
                sl = max(sl, max(near) + 2.0)
            lows = [l_[k] for k in np.where(a.sl)[0] if l_[k] < entry - 2 * (sl - entry)]
            tgt = max(lows, key=lambda x: x - entry) if lows else entry - 3 * (sl - entry)
        risk = abs(entry - sl)
        rr = abs(tgt - entry) / risk if risk > 0 else 0
        ote_ok = bool(a.rng and not (top < a.rng["ote_bottom"] or bot > a.rng["ote_top"]))
        score = 30 + (25 if sweep_before else 0) + (15 if ob["kind"] == "MSS" else 0) + \
            (10 if ote_ok else 0) + (10 if rr >= 2 else 0) + (10 if zone_dir == a.bias_score else 0)
        out.append(dict(direction="LONG" if zone_dir == 1 else "SHORT", zone=label, top=top, bottom=bot,
                        entry=round(entry, 2), stop=round(sl, 2), target=round(tgt, 2), rr=round(rr, 2),
                        sweep=bool(sweep_before), mss=ob["kind"] == "MSS", ote=ote_ok, in_zone=in_zone,
                        distance=round(dist, 2), score=min(score, 100), formed=df.index[ob["formed_i"]]))
    out.sort(key=lambda s: (-s["in_zone"], -s["score"], s["distance"]))
    return out[:5]


def analyze(df: pd.DataFrame, swing_n: int = 2, fvg_min: float = 4.0) -> Analysis:
    a = Analysis(df=df, swing_n=swing_n)
    if len(df) < 15:
        return a
    a.events, a.trend, a.sh, a.sl = market_structure(df, swing_n)
    a.obs = order_blocks(df, a.events)
    a.fvgs = fair_value_gaps(df, fvg_min)
    a.sweeps = liquidity_sweeps(df, a.sh, a.sl, swing_n)
    a.eq_levels = equal_levels(df, a.sh, a.sl)
    a.rng = dealing_range(df, n=swing_n)
    a.levels = key_levels(df)
    td = pd.Series(trading_date(df.index), index=df.index)
    days = sorted(td.unique())
    if len(days) >= 2:
        a.profile = volume_profile(df[td == days[-2]])
    step = (df.index[-1] - df.index[-2]) if len(df) > 2 else pd.Timedelta("15min")
    if step < pd.Timedelta("1h"):
        a.htf["H1"] = htf_trend(df, "1h")
    if step < pd.Timedelta("4h"):
        a.htf["H4"] = htf_trend(df, "4h")
    a.htf["TF"] = int(a.trend[-1])
    score = a.htf.get("H4", 0) * 2 + a.htf.get("H1", 0) + a.htf["TF"]
    if a.rng:
        score += 1 if 0 <= a.rng["position"] < 0.45 else (-1 if 0.55 < a.rng["position"] <= 1 else 0)
    a.bias_score = 1 if score >= 2 else (-1 if score <= -2 else 0)
    a.bias = {1: "Haussier", -1: "Baissier", 0: "Neutre / range"}[a.bias_score]
    a.setups = detect_setups(a)
    return a


def describe_trend(v: int) -> str:
    return {1: "haussière", -1: "baissière", 0: "indéfinie"}[int(v)]
