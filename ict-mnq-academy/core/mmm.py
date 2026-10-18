"""Moteur « MMM-style » (inspiré de la méthodologie Max Maserati, réimplémenté de zéro) :
- bougies : BC+ / BC− (Body Close), AFs+ / AFs− (affinité / sweep), CI (inside), NBC
- GMC (gap-confirmed momentum) c1 → c2 BC → c3 laisse un vide, ligne d'urgence, type de c3
- escalier de tendance (moteur swing « s ») : CDL/CDS (flip), LD/SD (continuation), T# / P# / R#, Z = T3+
- boîtes de contraction (moteur « x ») + balance control (1/3 – 2/3) + vPOC
- bandes de pullback (P–MP après une bougie PLUS, BAL–MD après une bougie MINUS)
- niveaux swing protégés, eBlock / iBlock
- MMPD (Premium/Discount 0-100, longueurs 27 et 9, lignes c et o, XP ≥ 80, XD ≤ 20)
- feux de session (tables du PDF « Max Maserati Model – 17 758 configurations »), Tempête parfaite, cycle du momentum.
Tout est calculé sans regarder le futur (une info au temps i n'utilise que les bougies ≤ i)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import resample
from .ict import find_swings, trading_date

ASIA = (18 * 60, 2 * 60)          # 18:00 → 02:00 NY
NY_AM = (9 * 60 + 30, 13 * 60 + 30)  # 09:30 → 13:30 NY
DEAD = (0, 2 * 60)                # 00:00 → 02:00 NY (zone morte avant Londres)


# ------------------------------------------------------------------ outils
def atr(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values


def minute_of_day(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray(idx.hour * 60 + idx.minute)


def in_window(m, win) -> np.ndarray:
    a, b = win
    m = np.asarray(m)
    return (m >= a) & (m < b) if a < b else (m >= a) | (m < b)


def session_name(ts: pd.Timestamp) -> str:
    m = ts.hour * 60 + ts.minute
    if in_window([m], NY_AM)[0]:
        return "NY AM"
    if in_window([m], DEAD)[0]:
        return "Asie tardive (00-02, zone morte)"
    if in_window([m], ASIA)[0]:
        return "Asie"
    if 2 * 60 <= m < 8 * 60:
        return "Londres"
    if 8 * 60 <= m < 9 * 60 + 30:
        return "Pré-ouverture NY"
    if 13 * 60 + 30 <= m < 16 * 60:
        return "NY PM"
    return "Clôture / maintenance"


# ------------------------------------------------------------------ bougies
def candle_types(df: pd.DataFrame) -> np.ndarray:
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    ph = np.concatenate([[np.nan], h[:-1]])
    pl = np.concatenate([[np.nan], l[:-1]])
    mid = (h + l) / 2
    t = np.full(len(df), "NBC", dtype=object)
    ci = (h <= ph) & (l >= pl)
    t[ci] = "CI"
    afp = (l < pl) & (c > pl) & (c <= ph) & (c > mid)
    afm = (h > ph) & (c < ph) & (c >= pl) & (c < mid)
    t[afp] = "AFs+"
    t[afm] = "AFs−"
    t[c > ph] = "BC+"
    t[c < pl] = "BC−"
    t[0] = "NBC"
    return t


PLUS_TYPES = {"BC+", "AFs+"}
MINUS_TYPES = {"BC−", "AFs−"}
CANDLE_LABEL = {"BC+": "BuBC", "BC−": "BeBC", "AFs+": "BuAF", "AFs−": "BeAF"}


def pullback_band(df: pd.DataFrame, i: int, ctype: str):
    """Après une bougie PLUS : bande P–MP (87,5 %–75 % de la bougie) ; après une MINUS : BAL–MD (50–25 %).
    Pour une bougie baissière on mesure depuis le haut (miroir)."""
    h, l = float(df["high"].iloc[i]), float(df["low"].iloc[i])
    r = h - l
    if r <= 0:
        return None
    if ctype == "BC+":
        return dict(kind="P–MP", top=l + 0.875 * r, bottom=l + 0.75 * r, dir=1)
    if ctype == "BC−":
        return dict(kind="P–MP", top=h - 0.75 * r, bottom=h - 0.875 * r, dir=-1)
    if ctype in ("AFs+",):
        return dict(kind="BAL–MD", top=l + 0.5 * r, bottom=l + 0.25 * r, dir=1)
    if ctype in ("AFs−",):
        return dict(kind="BAL–MD", top=h - 0.25 * r, bottom=h - 0.5 * r, dir=-1)
    return None


# ------------------------------------------------------------------- GMC
def gmc(df: pd.DataFrame, types: np.ndarray, max_keep: int = 400):
    """GMC haussier en i (= c3) : c2 = BC+ et bas(c3) > haut(c1) → vide (void) entre c1 et c3.
    Ligne GMC = ouverture de c2. Ligne d'urgence = haut de c1 (le bord que le gap doit dégager)."""
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    out = []
    N = len(df)
    for i in range(2, N):
        for d in (1, -1):
            if d == 1 and not (types[i - 1] == "BC+" and l[i] > h[i - 2]):
                continue
            if d == -1 and not (types[i - 1] == "BC−" and h[i] < l[i - 2]):
                continue
            if d == 1:
                if h[i] > h[i - 1] and c[i] <= h[i - 1]:
                    c3 = "AFs contre"
                elif c[i] > h[i - 1]:
                    c3 = "BC+ avec"
                else:
                    c3 = "neutre"
            else:
                if l[i] < l[i - 1] and c[i] >= l[i - 1]:
                    c3 = "AFs contre"
                elif c[i] < l[i - 1]:
                    c3 = "BC− avec"
                else:
                    c3 = "neutre"
            g = dict(i=i, dir=d, open_line=float(o[i - 1]), urgency=float(h[i - 2] if d == 1 else l[i - 2]),
                     void_top=float(l[i] if d == 1 else l[i - 2]), void_bottom=float(h[i - 2] if d == 1 else h[i]),
                     c3=c3, deleted_i=None, urgency_x_i=None)
            for k in range(i + 1, min(N, i + max_keep)):
                if g["urgency_x_i"] is None and ((d == 1 and l[k] <= g["urgency"]) or (d == -1 and h[k] >= g["urgency"])):
                    g["urgency_x_i"] = k
                if (d == 1 and c[k] < g["open_line"]) or (d == -1 and c[k] > g["open_line"]):
                    g["deleted_i"] = k
                    break
            out.append(g)
    return out


# -------------------------------------------------------- escalier (moteur s)
def _stair_engine(df: pd.DataFrame, n: int = 2):
    """Escalier de tendance par swings.
    Haussier : T1 = origine après un flip (CDL). P# = sommet avant pullback, R# = creux du pullback.
    Clôture > P# → LD# (continuation) et R# devient T(#+1). Clôture < T (origine de la jambe) → CDS (flip).
    Z = continuation qui crée T3 ou plus (LD2+ / SD2+)."""
    sh, sl = find_swings(df, n)
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    N = len(df)
    events = []
    state = np.zeros(N, int)        # +k = T# haussier, -k = T# baissier
    protect = np.full(N, np.nan)    # niveau swing protégé (où placer le stop)
    d, cnt = 0, 0
    T = None   # (idx, level)
    P = None   # (idx, level)
    last_sh = last_sl = None
    for i in range(N):
        j = i - n
        if j >= 0:
            if sh[j]:
                last_sh = (j, h[j])
                if d == 1 and j > T[0] and (P is None or h[j] > P[1]):
                    P = (j, h[j])
            if sl[j]:
                last_sl = (j, l[j])
                if d == -1 and j > T[0] and (P is None or l[j] < P[1]):
                    P = (j, l[j])
        if d == 0:
            if last_sh is not None and c[i] > last_sh[1]:
                k0 = max(0, last_sh[0] - 20)
                lo_i = k0 + int(np.argmin(l[k0:i + 1]))
                events.append(dict(i=i, dir=1, kind="CDL", T=1, T_i=lo_i, T_level=float(l[lo_i]), P=None, R=None,
                                   broken=float(last_sh[1]), broken_i=last_sh[0]))
                d, cnt, T, P = 1, 1, (lo_i, l[lo_i]), None
            elif last_sl is not None and c[i] < last_sl[1]:
                k0 = max(0, last_sl[0] - 20)
                hi_i = k0 + int(np.argmax(h[k0:i + 1]))
                events.append(dict(i=i, dir=-1, kind="CDS", T=1, T_i=hi_i, T_level=float(h[hi_i]), P=None, R=None,
                                   broken=float(last_sl[1]), broken_i=last_sl[0]))
                d, cnt, T, P = -1, 1, (hi_i, h[hi_i]), None
        elif d == 1:
            if c[i] < T[1]:
                hi_i = T[0] + int(np.argmax(h[T[0]:i + 1]))
                events.append(dict(i=i, dir=-1, kind="CDS", T=1, T_i=hi_i, T_level=float(h[hi_i]), P=None, R=None,
                                   broken=float(T[1]), broken_i=T[0]))
                d, cnt, T, P = -1, 1, (hi_i, h[hi_i]), None
            elif P is not None and c[i] > P[1]:
                r_i = P[0] + int(np.argmin(l[P[0]:i + 1]))
                cnt += 1
                events.append(dict(i=i, dir=1, kind="LD", k=cnt - 1, T=cnt, T_i=r_i, T_level=float(l[r_i]),
                                   P=float(P[1]), P_i=P[0], R=float(l[r_i]), R_i=r_i))
                T, P = (r_i, l[r_i]), None
        else:
            if c[i] > T[1]:
                lo_i = T[0] + int(np.argmin(l[T[0]:i + 1]))
                events.append(dict(i=i, dir=1, kind="CDL", T=1, T_i=lo_i, T_level=float(l[lo_i]), P=None, R=None,
                                   broken=float(T[1]), broken_i=T[0]))
                d, cnt, T, P = 1, 1, (lo_i, l[lo_i]), None
            elif P is not None and c[i] < P[1]:
                r_i = P[0] + int(np.argmax(h[P[0]:i + 1]))
                cnt += 1
                events.append(dict(i=i, dir=-1, kind="SD", k=cnt - 1, T=cnt, T_i=r_i, T_level=float(h[r_i]),
                                   P=float(P[1]), P_i=P[0], R=float(h[r_i]), R_i=r_i))
                T, P = (r_i, h[r_i]), None
        state[i] = d * cnt
        protect[i] = T[1] if T is not None else np.nan
    pending_P = P
    return dict(events=events, state=state, protect=protect, pending_P=pending_P, sh=sh, sl=sl)


def blocks_from_staircase(df: pd.DataFrame, st: dict):
    """eBlock = bougie d'origine derrière un flip (T1) ; iBlock = bougie R# derrière une continuation (T2+).
    Supprimés quand une clôture les traverse."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    out = []
    for e in st["events"]:
        k = e["T_i"]
        b = dict(kind="eBlock" if e["kind"] in ("CDL", "CDS") else "iBlock", dir=e["dir"], i=k, formed_i=e["i"],
                 top=float(h[k]), bottom=float(l[k]), end_i=None)
        for m in range(e["i"] + 1, len(df)):
            if (b["dir"] == 1 and c[m] < b["bottom"]) or (b["dir"] == -1 and c[m] > b["top"]):
                b["end_i"] = m
                break
        out.append(b)
    return out


# ------------------------------------------------------ boîtes (moteur x)
def contraction_boxes(df: pd.DataFrame, atr_v: np.ndarray, min_len: int = 5, k_atr: float = 1.6):
    """Boîte de contraction : au moins `min_len` bougies dont l'amplitude totale ≤ k × ATR.
    La boîte grandit tant que les clôtures restent dedans ; une clôture dehors = cassure (ZBrk)."""
    h, l, c, v = (df[k].values for k in ["high", "low", "close", "volume"])
    N = len(df)
    boxes, i = [], min_len
    while i < N:
        lo_i = i - min_len + 1
        hi, lo = h[lo_i:i + 1].max(), l[lo_i:i + 1].min()
        if hi - lo <= k_atr * atr_v[i] and all(lo <= c[m] <= hi for m in range(lo_i, i + 1)):
            j = i + 1
            while j < N and lo <= c[j] <= hi:
                hi, lo = max(hi, h[j]), min(lo, l[j])
                j += 1
            brk = None
            if j < N:
                brk = 1 if c[j] > hi else -1
            seg = slice(lo_i, j)
            boxes.append(dict(i0=lo_i, i1=j - 1, hi=float(hi), lo=float(lo), break_i=j if j < N else None,
                              break_dir=brk, vpoc=_vpoc(h[seg], l[seg], v[seg]),
                              last_close=float(c[min(j, N) - 1])))
            i = j + 1
        else:
            i += 1
    return boxes


def _vpoc(h, l, v, bins: int = 24):
    lo, hi = float(np.min(l)), float(np.max(h))
    if hi <= lo:
        return lo
    edges = np.linspace(lo, hi, bins + 1)
    vol = np.zeros(bins)
    w = v if np.sum(v) > 0 else np.ones(len(h))
    for a, b, x in zip(l, h, w):
        ia, ib = max(np.searchsorted(edges, a, "right") - 1, 0), min(np.searchsorted(edges, b, "right") - 1, bins - 1)
        vol[ia:ib + 1] += x / (ib - ia + 1)
    k = int(vol.argmax())
    return float((edges[k] + edges[k + 1]) / 2)


def balance_control(box: dict, close: float) -> dict:
    rng = box["hi"] - box["lo"]
    buy_line, sell_line = box["lo"] + rng * 2 / 3, box["lo"] + rng / 3
    pos = (close - box["lo"]) / rng if rng else 0.5
    side = "Acheteurs" if pos >= 2 / 3 else ("Vendeurs" if pos <= 1 / 3 else "Équilibre")
    return dict(buy_line=buy_line, sell_line=sell_line, pos=pos, side=side)


# ------------------------------------------------------------------ MMPD
def mmpd(df: pd.DataFrame, length: int = 27):
    """Position du prix dans son range récent (0–100). Ligne rapide « c » = clôture, ligne lente « o » = ouverture."""
    hh = df["high"].rolling(length, min_periods=2).max()
    ll = df["low"].rolling(length, min_periods=2).min()
    rng = (hh - ll).replace(0, np.nan)
    fast = ((df["close"] - ll) / rng * 100).clip(0, 100)
    slow = ((df["open"] - ll) / rng * 100).clip(0, 100)
    return fast.fillna(50).values, slow.fillna(50).values


def mmpd_state(fast: float, slow: float) -> str:
    if max(fast, slow) >= 80:
        return "XP"
    if min(fast, slow) <= 20:
        return "XD"
    return "MID"


# ------------------------------------------------------- tables du PDF
# Feux de session (heures UTC) — PDF « Max Maserati Model – 17 758 configurations » (mai 2019 – jan. 2026)
H4_LIGHTS = {  # bloc UTC (début) → {type: (win %, feu)}
    2: {"BC+": (78.1, "vert"), "BC−": (68.3, "vert"), "AFs+": (59.1, "jaune"), "AFs−": (68.3, "vert")},
    6: {"BC+": (78.0, "vert"), "BC−": (69.5, "vert"), "AFs+": (67.5, "vert"), "AFs−": (69.5, "vert")},
    10: {"BC+": (68.2, "vert"), "BC−": (70.7, "vert"), "AFs+": (68.0, "vert"), "AFs−": (70.7, "vert")},
    22: {"BC+": (64.9, "jaune"), "BC−": (55.9, "jaune"), "AFs+": (61.8, "jaune"), "AFs−": (55.9, "jaune")},
    18: {"BC+": (58.2, "jaune"), "BC−": (41.6, "rouge"), "AFs+": (48.2, "rouge"), "AFs−": (41.6, "rouge")},
    14: {"BC+": (55.1, "rouge"), "BC−": (52.2, "jaune"), "AFs+": (47.2, "rouge"), "AFs−": (52.2, "jaune")},
}
H1_BUBC = {9: 80.4, 8: 79.1, 11: 78.0, 4: 76.3, 18: 76.2, 20: 75.6, 10: 75.2, 2: 74.1, 0: 74.2, 3: 72.9,
           5: 58.5, 6: 59.7, 15: 65.3}
H1_BEBC = {11: 76.2, 3: 74.6, 2: 74.1, 20: 72.0, 0: 71.4, 10: 70.8, 4: 69.5, 9: 68.6, 8: 67.5, 1: 67.7, 15: 56.4}
GLOBAL_STATS = {  # TF: {type: (N, win, invalid, both, note)}
    "D": {"BC+": (519, 75.1, 14.6, 10.2, "A+"), "BC−": (358, 65.9, 26.0, 8.1, "A"),
          "AFs+": (241, 63.1, 22.4, 14.5, "B+"), "AFs−": (290, 59.3, 22.4, 18.3, "B")},
    "4H": {"BC+": (2871, 69.3, 16.1, 14.6, "A"), "BC−": (2129, 64.3, 23.0, 12.6, "B+"),
           "AFs+": (651, 58.7, 21.5, 19.8, "B"), "AFs−": (722, 60.8, 19.4, 19.8, "B")},
    "1H": {"BC+": (2790, 72.3, 17.0, 10.7, "A+"), "BC−": (2210, 69.3, 21.0, 9.7, "A"),
           "AFs+": (856, 62.6, 21.3, 16.1, "B+"), "AFs−": (903, 58.5, 23.1, 18.4, "B")},
    "15m": {"BC+": (2656, 71.8, 17.7, 10.4, "A+"), "BC−": (2344, 70.3, 20.3, 9.5, "A"),
            "AFs+": (950, 61.9, 22.4, 15.7, "B+"), "AFs−": (1005, 57.6, 24.7, 17.7, "B")},
}
M15_AVOID_UTC = [(15 * 60, 16 * 60, "Déjeuner NY : agitation extrême"), (0, 60, "Gap ouverture Asie"),
                 (5 * 60, 6 * 60, "Gap pré-Londres")]
ALIGN_TABLE = [(1, "69-78 %", "1 %"), (2, "75-80 %", "1 %"), (3, "80-85 %", "1 %"), (4, "85-90 %", "1,5 % max")]


def pdf_light(ts_ny: pd.Timestamp, ctype: str, tf: str) -> tuple[str, str]:
    """Feu de session selon les tables du PDF. ts_ny = début de la bougie signal (heure NY)."""
    if ctype not in ("BC+", "BC−", "AFs+", "AFs−"):
        return "—", "pas une configuration MMM"
    u = ts_ny.tz_convert("UTC")
    if tf == "4H":
        blk = (u.hour // 4) * 4 + 2 if u.hour % 4 >= 2 else (u.hour // 4) * 4 - 2
        blk = blk % 24
        w, f = H4_LIGHTS.get(blk, {}).get(ctype, (None, "n/d"))
        return f, (f"{w:.1f} % (bloc {blk:02d}-{(blk + 4) % 24:02d} UTC)" if w else "bloc non référencé")
    if tf == "1H":
        tab = H1_BUBC if ctype == "BC+" else (H1_BEBC if ctype == "BC−" else None)
        if tab is None:
            return "n/d", "AFs : pas de table horaire 1H dans le PDF"
        w = tab.get(u.hour)
        if w is None:
            return "jaune", f"heure {u.hour:02d}h UTC hors top 10"
        return ("vert" if w >= 70 else "jaune" if w >= 62 else "rouge"), f"{w:.1f} % ({u.hour:02d}h UTC)"
    if tf == "15m":
        m = u.hour * 60 + u.minute
        for a, b, why in M15_AVOID_UTC:
            if a <= m < b:
                return "rouge", why
        if ctype in ("BC+",) and 8 * 60 + 15 <= m <= 9 * 60 + 30:
            return "vert", "fenêtre matinale BuBC (~75-79 %)"
        if ctype in ("BC−",) and 11 * 60 <= m <= 13 * 60:
            return "vert", "mi-journée BeBC (~72-76 %)"
        return "jaune", "fenêtre standard"
    return "n/d", ""


# -------------------------------------------------- Tempête parfaite
def last_closed_type(df: pd.DataFrame, rule: str, now: pd.Timestamp) -> str:
    r = resample(df, rule)
    if len(r) < 3:
        return "NBC"
    step = pd.Timedelta(rule.replace("D", "1D")) if rule != "D" else pd.Timedelta("1D")
    closed = r[r.index + step <= now + pd.Timedelta(seconds=1)]
    if len(closed) < 3:
        return "NBC"
    return candle_types(closed)[-1]


def perfect_storm(df: pd.DataFrame) -> dict:
    """Alignement D / 4H / 1H / 15m des dernières bougies CLÔTURÉES (BuBC ou BeBC)."""
    if len(df) < 50:
        return dict(level=0, dir=0, detail={})
    now = df.index[-1] + (df.index[-1] - df.index[-2])
    td = df.copy()
    td.index = td.index + pd.Timedelta(hours=6)  # journée CME 18h → 17h
    detail = {"D": last_closed_type(td, "D", now + pd.Timedelta(hours=6)),
              "4H": last_closed_type(df, "4h", now), "1H": last_closed_type(df, "1h", now),
              "15m": last_closed_type(df, "15min", now)}
    up = sum(v == "BC+" for v in detail.values())
    dn = sum(v == "BC−" for v in detail.values())
    d = 1 if up > dn else (-1 if dn > up else 0)
    lvl = max(up, dn)
    prob = next((p for k, p, s in ALIGN_TABLE if k == lvl), "—")
    size = next((s for k, p, s in ALIGN_TABLE if k == lvl), "0 %")
    return dict(level=lvl, dir=d, detail=detail, prob=prob, size=size)


# ------------------------------------------------- cycle du momentum
def _phase(df: pd.DataFrame, entry_i: int, side: str, entry: float) -> dict:
    """Construction (aucun retest), Touche (retest sans clôture au-delà), Échec (clôture au-delà).
    Mur du momentum : 4 bougies de construction (haussier) / 3 (baissier)."""
    d = 1 if side == "LONG" else -1
    seg = df.iloc[entry_i + 1:]
    build = touches = 0
    phase = "Construction"
    for _, b in seg.iterrows():
        if (d == 1 and b["close"] < entry) or (d == -1 and b["close"] > entry):
            phase = "Échec"
            break
        touched = (b["low"] <= entry) if d == 1 else (b["high"] >= entry)
        if touched:
            touches += 1
            phase = "Touche"
        elif touches == 0:
            build += 1
    wall = 4 if d == 1 else 3
    cont = {0: None, 1: "50 %", 2: "30 %"}.get(touches, "< 20 %")
    if phase == "Échec":
        advice = "ÉCHEC : clôture au-delà de l'entrée → sortir (seulement 11 % récupèrent)."
    elif build >= wall and touches == 0:
        advice = f"MUR DU MOMENTUM atteint ({build} bougies) → sortir {'75 %' if d == 1 else '100 %'} de la position."
    elif phase == "Touche":
        advice = f"TOUCHE n°{touches} : continuation ≈ {cont} → resserrer le stop, préparer la sortie."
    else:
        advice = f"CONSTRUCTION ({build} bougie(s)) : tenir, laisser courir (≈ 80 % de continuation)."
    return dict(phase=phase, build=build, touches=touches, wall=wall, advice=advice)


# ============================================================ API publique
def mmpd_zone(fast: float, slow: float) -> str:
    return mmpd_state(fast, slow)


def staircase(df: pd.DataFrame, swing_n: int = 2) -> list:
    """Marches de l'escalier (une par flip ou continuation) :
    i, dir, T, label (CDLs/CDSs/LDs#/SDs#), p_i/p_level (niveau cassé), r_i/r_level (origine / niveau protégé)."""
    eng = _stair_engine(df, swing_n)
    steps = []
    for e in eng["events"]:
        if e["kind"] in ("CDL", "CDS"):
            steps.append(dict(i=e["i"], dir=e["dir"], T=1, label=e["kind"] + "s", kind="FLIP",
                              p_i=int(e.get("broken_i", e["T_i"])), p_level=float(e.get("broken", e["T_level"])),
                              r_i=int(e["T_i"]), r_level=float(e["T_level"])))
        else:
            steps.append(dict(i=e["i"], dir=e["dir"], T=int(e["T"]), label=f"{e['kind']}s{e['k']}", kind="CONT",
                              p_i=int(e["P_i"]), p_level=float(e["P"]), r_i=int(e["R_i"]), r_level=float(e["R"])))
    return steps


def gmc_events(df: pd.DataFrame, ty: np.ndarray | None = None) -> list:
    """GMC au format attendu par le backtest et les graphiques."""
    ty = candle_types(df) if ty is None else ty
    out = []
    for g in gmc(df, ty):
        out.append(dict(i=g["i"], dir=g["dir"], open_line=g["open_line"], urgency=g["urgency"],
                        void_top=max(g["void_top"], g["void_bottom"]), void_bot=min(g["void_top"], g["void_bottom"]),
                        c3=str(ty[g["i"]]), afs_against=g["c3"] == "AFs contre", deleted_i=g["deleted_i"],
                        urgency_x_i=g["urgency_x_i"]))
    return out


SESSION_RESETS = [(18 * 60, "Asie"), (2 * 60, "Londres"), (9 * 60 + 30, "NY 09h30")]


def session_boxes(df: pd.DataFrame, build_minutes: int = 60) -> list:
    """Boîtes de zone (BZ) remises à zéro à 18:00, 02:00 et 09:30 (NY) : la boîte = range de la
    première heure de session. ZBrk = 1re clôture hors de la boîte avant la remise à zéro suivante.
    Contraction = boîte étroite (≤ 1,5 ATR) ; Expansion sinon. Balance control : lignes 1/3 et 2/3,
    le camp qui contrôle = celui du tiers où se trouve la dernière clôture dans la boîte."""
    if len(df) < 10:
        return []
    o, h, l, c, v = (df[k].values for k in ["open", "high", "low", "close", "volume"])
    a = atr(df)
    mins = minute_of_day(df.index)
    step = (df.index[1] - df.index[0]).total_seconds() / 60 if len(df) > 1 else 15
    n_build = max(1, int(round(build_minutes / max(step, 1))))
    starts = []
    for k in range(1, len(df)):
        for m0, name in SESSION_RESETS:
            prev = mins[k - 1]
            if (prev < m0 <= mins[k]) or (mins[k] == m0) or (m0 == 18 * 60 and prev < m0 and mins[k] >= m0):
                if not starts or starts[-1][0] != k:
                    starts.append((k, name))
    starts = [(k, nm) for j, (k, nm) in enumerate(starts) if j == 0 or k - starts[j - 1][0] > n_build]
    out = []
    for j, (s0, name) in enumerate(starts):
        e_build = s0 + n_build - 1
        if e_build >= len(df):
            break
        nxt = starts[j + 1][0] if j + 1 < len(starts) else len(df)
        top, bot = float(h[s0:e_build + 1].max()), float(l[s0:e_build + 1].min())
        rng = top - bot
        brk_i = brk_dir = None
        for k in range(e_build + 1, nxt):
            if c[k] > top or c[k] < bot:
                brk_i, brk_dir = k, (1 if c[k] > top else -1)
                break
        last_in = brk_i - 1 if brk_i is not None else min(nxt, len(df)) - 1
        pos = (c[last_in] - bot) / rng if rng > 0 else 0.5
        seg = slice(s0, e_build + 1)
        out.append(dict(s=s0, e=e_build, end=nxt - 1, name=name, top=top, bot=bot,
                        kind="Contraction" if rng <= 1.5 * a[e_build] else "Expansion",
                        brk_i=brk_i, brk_dir=brk_dir, third_hi=bot + rng * 2 / 3, third_lo=bot + rng / 3,
                        control=1 if pos >= 2 / 3 else (-1 if pos <= 1 / 3 else 0),
                        vpoc=_vpoc(h[seg], l[seg], v[seg]), range=rng))
    return out


def daily_direction(df: pd.DataFrame) -> np.ndarray:
    """Pour chaque bougie : sens de la bougie journalière PRÉCÉDENTE (journée CME 18h → 17h NY). +1 / −1 / 0."""
    td = pd.Series(trading_date(df.index), index=df.index)
    g = df.groupby(td.values).agg(open=("open", "first"), close=("close", "last"))
    dd = np.sign(g["close"] - g["open"]).astype(int)
    prev = dd.shift(1).fillna(0).astype(int)
    return prev.reindex(td.values).values


def alignment(df: pd.DataFrame) -> dict:
    """Tempête parfaite : type de la dernière bougie CLÔTURÉE sur D / 4H / 1H / 15m."""
    ps = perfect_storm(df)
    prob = ps.get("prob", "—")
    return dict(tf=ps.get("detail", {}), count=ps.get("level", 0), dir=ps.get("dir", 0),
                prob_doc=prob if ps.get("level", 0) else "—", size=ps.get("size", "0 %"))


def momentum_phase(df: pd.DataFrame, side: str, entry: float, entry_time) -> dict:
    """Cycle du momentum d'une position ouverte (PDF partie 4)."""
    try:
        k = int(np.searchsorted(df.index, pd.Timestamp(entry_time)))
    except Exception:
        k = len(df) - 1
    r = _phase(df, min(k, len(df) - 1), side, entry)
    r["construction"] = r["build"]
    return r


# ------------------------------------------------------- analyse complète
@dataclass
class MMM:
    df: pd.DataFrame
    types: np.ndarray = None
    atr: np.ndarray = None
    gmc: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    stair: dict = field(default_factory=dict)
    blocks: list = field(default_factory=list)
    boxes: list = field(default_factory=list)
    contraction: list = field(default_factory=list)
    pb: dict | None = None
    mmpd27: tuple = None
    mmpd9: tuple = None
    align: dict = field(default_factory=dict)
    storm: dict = field(default_factory=dict)
    daily_dir: int = 0
    htf_1h: int = 0


def analyze_mmm(df: pd.DataFrame, swing_n: int = 2, box_len: int = 5, box_k: float = 1.6) -> MMM:
    m = MMM(df=df)
    if len(df) < 30:
        return m
    m.types = candle_types(df)
    m.atr = atr(df)
    m.gmc = gmc_events(df, m.types)
    m.stair = _stair_engine(df, swing_n)
    m.steps = staircase(df, swing_n)
    m.blocks = blocks_from_staircase(df, m.stair)
    m.boxes = session_boxes(df)
    m.contraction = contraction_boxes(df, m.atr, box_len, box_k)
    m.mmpd27 = mmpd(df, 27)
    m.mmpd9 = mmpd(df, 9)
    m.storm = perfect_storm(df)
    m.align = alignment(df)
    m.daily_dir = int(daily_direction(df)[-1])
    for k in range(len(df) - 1, max(-1, len(df) - 12), -1):
        band = pullback_band(df, k, m.types[k])
        if band:
            m.pb = dict(i=k, top=band["top"], bot=band["bottom"], dir=band["dir"],
                        label=f"{band['kind']} après {m.types[k]}")
            break
    h1 = resample(df, "1h")
    if len(h1) > 20:
        m.htf_1h = int(np.sign(_stair_engine(h1, 2)["state"][-2]))
    return m


def map_table(m: MMM) -> list[tuple[str, str]]:
    """Lecture live façon « MAP table »."""
    df = m.df
    if m.types is None:
        return []
    i = len(df) - 1
    st = m.stair["state"][i]
    rows = [("Structure (escalier s)", (f"Haussière T{st}" if st > 0 else f"Baissière T{-st}" if st < 0 else "indéfinie")
             + (" → zone Z (T3+)" if abs(st) >= 3 else ""))]
    live = next((b for b in reversed(m.contraction) if b["break_i"] is None or b["break_i"] >= i - 2), None)
    if live:
        bc = balance_control(live, float(df["close"].iloc[i]))
        rows.append(("Contrôle (boîte vivante)", f"{bc['side']} — clôture à {bc['pos'] * 100:.0f} % de la boîte "
                     f"{live['lo']:.2f}–{live['hi']:.2f} · vPOC {live['vpoc']:.2f}"))
    else:
        rows.append(("Contrôle (boîte vivante)", "pas de boîte de contraction en cours"))
    t = m.types[i]
    rows.append(("Dernière bougie", f"{t} ({CANDLE_LABEL.get(t, 'non-configuration')})"))
    f, s = m.mmpd27[0][i], m.mmpd27[1][i]
    rows.append(("MMPD 27", f"{mmpd_state(f, s)} — c {f:.0f} / o {s:.0f} "
                 + ("(longs autorisés)" if mmpd_state(f, s) == "XP" else "(shorts autorisés)" if mmpd_state(f, s) == "XD" else "(pas de gate)")))
    g = next((g for g in reversed(m.gmc) if g["deleted_i"] is None), None)
    rows.append(("GMC actif", (f"{'haussier' if g['dir'] == 1 else 'baissier'} · ligne {g['open_line']:.2f} · c3 {g['c3']}"
                               + (" (AFs contre)" if g["afs_against"] else "")) if g else "aucun"))
    bx = m.boxes[-1] if m.boxes else None
    if bx:
        rows.append(("Boîte de session (BZ)", f"{bx['name']} {bx['kind']} {bx['bot']:.2f}–{bx['top']:.2f} ({bx['range']:.0f} pts) · "
                     + ("cassée ▲" if bx["brk_dir"] == 1 else "cassée ▼" if bx["brk_dir"] == -1 else "pas encore cassée")))
    rows.append(("Swing protégé", f"{m.stair['protect'][i]:.2f}" if not np.isnan(m.stair['protect'][i]) else "—"))
    rows.append(("Biais 1H", {1: "haussier", -1: "baissier", 0: "neutre"}[m.htf_1h]))
    rows.append(("Session", session_name(df.index[i])))
    sm = m.storm
    if sm.get("detail"):
        rows.append(("Tempête parfaite", f"{sm['level']}/4 TF alignés ({', '.join(f'{k} {v}' for k, v in sm['detail'].items())}) → "
                     f"proba PDF {sm['prob']}, taille {sm['size']}"))
    rows.append(("ATR(14)", f"{m.atr[i]:.1f} pts"))
    return rows
