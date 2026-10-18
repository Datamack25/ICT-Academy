"""Banc de backtests ICT + MMM — même philosophie que la page backtests de maxmaserati.com :
coût déduit à chaque trade, période « ancienne » (70 %) vs « récente » (30 %), comparaison à un
tirage ALÉATOIRE, t-score, plateau de voisins, retrait des 5 meilleurs trades, puis verdict :
TRADE / USE AS FILTER / WATCH / DON'T TRADE.

Règles de simulation (prudentes, sans regarder le futur) :
- signal sur bougie CLÔTURÉE ; entrée à la clôture (marché) ou ordre limite (expire après 20 bougies) ;
- si stop et objectif sont touchés dans la même bougie, le STOP l'emporte ;
- ½ sortie optionnelle à +0,5 R puis stop à l'entrée pour le reste (runner) ;
- sortie forcée après `max_bars` bougies à la clôture ; une seule position par setup à la fois."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .mmm import atr, candle_types, daily_direction, gmc_events, mmpd, session_boxes, staircase

NY_AM = (9 * 60 + 30, 13 * 60 + 30)
ASIA = (18 * 60, 2 * 60)  # 18:00 → 02:00 (traverse minuit)


def session_label(ts: pd.Timestamp) -> str:
    m = ts.hour * 60 + ts.minute
    if NY_AM[0] <= m < NY_AM[1]:
        return "NY AM"
    if m >= ASIA[0] or m < ASIA[1]:
        return "Asie"
    if 2 * 60 <= m < 8 * 60:
        return "Londres"
    if 8 * 60 <= m < 9 * 60 + 30:
        return "Pré-NY"
    return "NY PM / clôture"


# ---------------------------------------------------------------- signaux
def build_signals(df: pd.DataFrame, swing_n: int = 2) -> dict:
    """Retourne {nom_setup: [signal, ...]} — chaque signal : i, dir, entry_kind, limit, nat_stop, nat_tp."""
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    N = len(df)
    ty = candle_types(df)
    sig = {k: [] for k in SETUPS}
    # --- MMM : bougies du PDF (cible = extrême de la bougie signal, stop = extrême opposé, entrée ouverture suivante)
    for i in range(1, N - 1):
        if ty[i] == "BC+":
            sig["MMM BuBC (doc)"].append(dict(i=i, dir=1, entry_kind="next_open", nat_stop=l[i], nat_tp=h[i]))
            if l[i] >= l[i - 1] and (c[i] - l[i]) >= 0.5 * (h[i] - l[i]):
                sig["MMM M · BC+ long"].append(dict(i=i, dir=1, entry_kind="close", nat_stop=l[i], nat_tp=None))
        elif ty[i] == "BC−":
            sig["MMM BeBC (doc)"].append(dict(i=i, dir=-1, entry_kind="next_open", nat_stop=h[i], nat_tp=l[i]))
        elif ty[i] == "AFs+":
            sig["MMM BuAF (doc)"].append(dict(i=i, dir=1, entry_kind="next_open", nat_stop=l[i], nat_tp=h[i - 1]))
            sig["MMM AFs+ limite P 12,5 %"].append(dict(i=i, dir=1, entry_kind="limit",
                                                        limit=h[i] - 0.125 * (h[i] - l[i]), nat_stop=l[i], nat_tp=None))
        elif ty[i] == "AFs−":
            sig["MMM BeAF (doc)"].append(dict(i=i, dir=-1, entry_kind="next_open", nat_stop=h[i], nat_tp=l[i - 1]))
    # --- GMC (G long, B AFs contre)
    for g in gmc_events(df, ty):
        i = g["i"]
        if g["dir"] == 1:
            sig["MMM G · GMC long"].append(dict(i=i, dir=1, entry_kind="close", nat_stop=l[i - 1], nat_tp=None))
            if g["afs_against"]:
                sig["MMM B · GMC AFs contre"].append(dict(i=i, dir=1, entry_kind="close", nat_stop=l[i - 1], nat_tp=None))
        else:
            sig["MMM GMC short"].append(dict(i=i, dir=-1, entry_kind="close", nat_stop=h[i - 1], nat_tp=None))
    # --- escalier : Z = T3+ (LD2+ / SD2+) à la clôture
    for s in staircase(df, swing_n):
        if s["T"] >= 3 and s["i"] < N - 1:
            sig["MMM Z · T3+ break"].append(dict(i=s["i"], dir=s["dir"], entry_kind="close", nat_stop=s["r_level"], nat_tp=None))
    # --- boîtes de session : 1re cassure à 09h30 (E3 retest) et contraction limite 75 %
    for bx in session_boxes(df):
        k = bx["brk_i"]
        if k is None or k >= N - 1:
            continue
        d = bx["brk_dir"]
        if bx["name"].startswith("NY") and 50 <= bx["top"] - bx["bot"] <= 100:
            lvl = bx["top"] if d == 1 else bx["bot"]
            sig["MMM 09h30 · 1re cassure BZ (retest)"].append(dict(i=k, dir=d, entry_kind="limit", limit=lvl,
                                                                     nat_stop=bx["bot"] if d == 1 else bx["top"], nat_tp=None))
        if bx["kind"] == "Contraction" and d == 1:
            lim = l[k] + 0.75 * (h[k] - l[k])
            sig["MMM C · contraction limite 75 %"].append(dict(i=k, dir=1, entry_kind="limit", limit=lim, nat_stop=bx["bot"], nat_tp=None))
    # --- ICT : on rejoue le moteur ICT en glissant (pas de futur) toutes les `stride` bougies
    _ict_signals(df, swing_n, sig)
    return sig


def _ict_signals(df, swing_n, sig, stride: int = 4, window: int = 600):
    N = len(df)
    seen = set()
    c, h, l = df["close"].values, df["high"].values, df["low"].values
    from .ict import fair_value_gaps, liquidity_sweeps, market_structure, order_blocks
    ev, _, sh, sl = market_structure(df, swing_n)
    obs = order_blocks(df, ev)
    sws = liquidity_sweeps(df, sh, sl, swing_n)
    fvgs = fair_value_gaps(df, 4.0)
    # Méthode C : sweep -> MSS opposé -> 1er retour dans l'OB (limite au bord de l'OB)
    for ob in obs:
        if ob["kind"] != "MSS":
            continue
        d, fi = ob["dir"], ob["formed_i"]
        swept = [s for s in sws if s["dir"] == d and fi - 40 <= s["i"] <= fi]
        lim = ob["top"] if d == 1 else ob["bottom"]
        stop = (min([ob["bottom"]] + [s["level"] for s in swept]) - 2) if d == 1 else (max([ob["top"]] + [s["level"] for s in swept]) + 2)
        if fi < N - 2:
            key = ("C", fi)
            if swept and key not in seen:
                sig["ICT Méthode C · sweep + MSS + OB"].append(dict(i=fi, dir=d, entry_kind="limit", limit=lim, nat_stop=stop, nat_tp=None))
                seen.add(key)
            sig["ICT Méthode A · OB après MSB"].append(dict(i=fi, dir=d, entry_kind="limit", limit=lim,
                                                             nat_stop=ob["bottom"] - 2 if d == 1 else ob["top"] + 2, nat_tp=None))
        # Breaker : OB cassé -> retest du breaker dans le sens inverse
        if ob["breaker"] and ob["broken_i"] is not None and ob["broken_i"] < N - 2:
            bd = -d
            lim_b = ob["bottom"] if bd == -1 else ob["top"]
            stp = ob["top"] + 2 if bd == -1 else ob["bottom"] - 2
            sig["ICT Breaker · retest"].append(dict(i=ob["broken_i"], dir=bd, entry_kind="limit", limit=lim_b, nat_stop=stp, nat_tp=None))
    # ICT 2022 : MSS + FVG créé dans la jambe de cassure -> limite au bord du FVG
    for e in ev:
        if e["kind"] != "MSS":
            continue
        g = [x for x in fvgs if x["dir"] == e["dir"] and e["swing_i"] <= x["i"] <= e["i"] + 1]
        if g and e["i"] < N - 2:
            x = g[-1]
            lim = x["top"] if e["dir"] == 1 else x["bottom"]
            a = max(0, e["swing_i"] - 10)
            stp = (l[a:e["i"] + 1].min() - 2) if e["dir"] == 1 else (h[a:e["i"] + 1].max() + 2)
            sig["ICT 2022 · MSS + FVG"].append(dict(i=e["i"], dir=e["dir"], entry_kind="limit", limit=lim, nat_stop=stp, nat_tp=None))
    # SFP pur : sweep + clôture de retour -> entrée à la clôture, stop au-delà de la mèche
    for s in sws:
        i = s["i"]
        if i < N - 1:
            sig["ICT SFP · sweep seul"].append(dict(i=i, dir=s["dir"], entry_kind="close",
                                                    nat_stop=(l[i] - 1) if s["dir"] == 1 else (h[i] + 1), nat_tp=None))


SETUPS = {
    # nom: (famille, description, défauts canoniques)
    "ICT Méthode C · sweep + MSS + OB": ("ICT", "Cours Warren méthode C : liquidité prise, MSS opposé, entrée au retour dans l'OB, stop sous le sweep.",
                                         dict(stop="Structure", tp=3.0, half=True)),
    "ICT Méthode A · OB après MSB": ("ICT", "Méthode A : entrée au début de l'OB qui a provoqué la rupture, invalidation de l'autre côté.",
                                     dict(stop="Structure", tp=3.0, half=True)),
    "ICT Breaker · retest": ("ICT", "OB cassé à la clôture → breaker ; entrée au retest, stop de l'autre côté.",
                             dict(stop="Structure", tp=3.0, half=True)),
    "ICT 2022 · MSS + FVG": ("ICT", "MSS avec déplacement laissant un FVG ; entrée limite sur le FVG.", dict(stop="Structure", tp=3.0, half=True)),
    "ICT SFP · sweep seul": ("ICT", "Sweep/SFP sans confirmation : test de contrôle (le cours dit qu'il ne suffit pas).",
                             dict(stop="Structure", tp=2.0, half=False)),
    "MMM Z · T3+ break": ("MMM", "Marche T3+ (LD2+/SD2+) à la clôture, stop ATR × 1,5, ½ à +0,5 R, runner 1:6.",
                          dict(stop="ATR×1.5", tp=6.0, half=True, daily=True)),
    "MMM G · GMC long": ("MMM", "GMC haussier, entrée clôture c3, stop 1 ATR, ½ à +0,5 R, runner 1:3.", dict(stop="ATR×1", tp=3.0, half=True, daily=True)),
    "MMM B · GMC AFs contre": ("MMM", "GMC haussier dont c3 fait un nouveau haut puis réintègre c2 ; stop 1 ATR, runner 1:6.",
                               dict(stop="ATR×1", tp=6.0, half=True, daily=True)),
    "MMM GMC short": ("MMM", "Miroir baissier du GMC (contrôle).", dict(stop="ATR×1", tp=3.0, half=True, daily=True)),
    "MMM M · BC+ long": ("MMM", "BC+ sans plus bas inférieur, clôture dans la moitié haute ; stop fixe 50, ½ à +0,5 R, runner 1:2.",
                         dict(stop="Fixe 50", tp=2.0, half=True, daily=True)),
    "MMM C · contraction limite 75 %": ("MMM", "Cassure haussière d'une boîte de contraction ; limite à 75 % (MP) de la bougie de cassure.",
                                        dict(stop="Fixe 50", tp=2.0, half=True)),
    "MMM 09h30 · 1re cassure BZ (retest)": ("MMM", "1re cassure de la boîte 09h30 (50–100 pts), entrée au retest du bord, stop 50, 1:2.",
                                            dict(stop="Fixe 50", tp=2.0, half=False)),
    "MMM AFs+ limite P 12,5 %": ("MMM", "AFs+ avec limite au pullback de 12,5 %, stop sous la bougie, 1:3 (seul combo validé sur 7 contrôles côté site).",
                                 dict(stop="Structure", tp=3.0, half=False)),
    "MMM BuBC (doc)": ("MMM doc", "PDF : BuBC, entrée ouverture suivante, cible = haut de la bougie signal, stop = bas.",
                       dict(stop="Structure", tp="nat", half=False)),
    "MMM BeBC (doc)": ("MMM doc", "PDF : BeBC, cible = bas de la bougie signal, stop = haut.", dict(stop="Structure", tp="nat", half=False)),
    "MMM BuAF (doc)": ("MMM doc", "PDF : balayage haussier, cible = haut du range précédent, stop = bas balayé.", dict(stop="Structure", tp="nat", half=False)),
    "MMM BeAF (doc)": ("MMM doc", "PDF : balayage baissier, cible = bas précédent, stop = haut balayé.", dict(stop="Structure", tp="nat", half=False)),
}


# ------------------------------------------------------------- simulation
def _stop_dist(mode: str, s: dict, entry: float, a: float) -> float | None:
    if mode == "Structure":
        d = (entry - s["nat_stop"]) * s["dir"]
    elif mode.startswith("ATR"):
        d = a * float(mode.split("×")[1])
    elif mode == "Fixe 50":
        d = 50.0
    else:
        d = None
    return d if d and d >= 1.0 else None  # stops < 4 ticks ignorés


def simulate(df: pd.DataFrame, signals: list, stop: str = "Structure", tp=2.0, half: bool = False, cost: float = 1.0,
             max_bars: int = 64, session: str = "Toutes", gate: str = "Aucun", daily: bool = False,
             ctx: dict | None = None, half_r: float = 0.5) -> pd.DataFrame:
    ctx = ctx or context_arrays(df)
    o, h, l, c = ctx["o"], ctx["h"], ctx["l"], ctx["c"]
    N = len(df)
    rows, busy_until = [], -1
    for s in signals:
        i, d = s["i"], s["dir"]
        if i <= busy_until or i >= N - 1:
            continue
        if session != "Toutes" and not _session_ok(ctx["sess"][i], session):
            continue
        if gate == "MMPD 27 momentum" and not ((d == 1 and ctx["xp"][i]) or (d == -1 and ctx["xd"][i])):
            continue
        if daily and ctx["daily"][i] != d:
            continue
        # entrée
        if s["entry_kind"] == "close":
            e_i, entry = i, c[i]
        elif s["entry_kind"] == "next_open":
            e_i, entry = i + 1, o[i + 1]
        else:
            lim = s["limit"]
            e_i, entry = None, lim
            for k in range(i + 1, min(N, i + 21)):
                if (d == 1 and l[k] <= lim) or (d == -1 and h[k] >= lim):
                    e_i = k
                    entry = min(lim, o[k]) if d == 1 else max(lim, o[k])
                    break
                if (d == 1 and c[k] < s["nat_stop"]) or (d == -1 and c[k] > s["nat_stop"]):
                    break
            if e_i is None:
                continue
        risk = _stop_dist(stop, s, entry, ctx["atr"][i])
        if risk is None:
            continue
        sl_px = entry - d * risk
        if tp == "nat":
            if s.get("nat_tp") is None:
                continue
            tgt_pts = (s["nat_tp"] - entry) * d
            if tgt_pts <= 0.25:
                continue
            tp_px = s["nat_tp"]
        else:
            tp_px = entry + d * risk * float(tp)
        half_px = entry + d * risk * half_r
        start = e_i + 1 if s["entry_kind"] != "next_open" else e_i
        end = min(N, start + max_bars)
        if start >= N:
            continue
        hh, ll, cc = h[start:end], l[start:end], c[start:end]
        if d == 1:
            hit_sl, hit_tp, hit_half = ll <= sl_px, hh >= tp_px, hh >= half_px
        else:
            hit_sl, hit_tp, hit_half = hh >= sl_px, ll <= tp_px, ll <= half_px
        first = lambda m: int(np.argmax(m)) if m.any() else 10 ** 9
        k_sl, k_tp, k_half = first(hit_sl), first(hit_tp), first(hit_half)
        if not half:
            if k_sl <= k_tp and k_sl < 10 ** 9:
                pts, k_exit, why = -risk, k_sl, "stop"
            elif k_tp < 10 ** 9:
                pts, k_exit, why = (tp_px - entry) * d, k_tp, "objectif"
            else:
                k_exit = len(cc) - 1
                pts, why = (cc[-1] - entry) * d, "temps"
        else:
            if k_sl <= k_half and k_sl < 10 ** 9:
                pts, k_exit, why = -risk, k_sl, "stop"
            elif k_half < 10 ** 9:
                p1 = 0.5 * risk * half_r
                # runner : stop ramené à l'entrée après la ½ sortie
                rest = slice(k_half + 1, None)
                be_hit = (ll[rest] <= entry) if d == 1 else (hh[rest] >= entry)
                tp_hit = hit_tp[rest]
                k_be, k_t = first(be_hit), first(tp_hit)
                if k_tp == k_half:  # objectif atteint dans la même bougie que la ½
                    p2, k_exit, why = 0.5 * (tp_px - entry) * d, k_half, "objectif"
                elif k_be <= k_t and k_be < 10 ** 9:
                    p2, k_exit, why = 0.0, k_half + 1 + k_be, "½ + BE"
                elif k_t < 10 ** 9:
                    p2, k_exit, why = 0.5 * (tp_px - entry) * d, k_half + 1 + k_t, "½ + objectif"
                else:
                    p2, k_exit, why = 0.5 * (cc[-1] - entry) * d, len(cc) - 1, "½ + temps"
                pts = p1 + p2
            else:
                k_exit = len(cc) - 1
                pts, why = (cc[-1] - entry) * d, "temps"
        net = pts - cost
        rows.append(dict(time=df.index[i], i=i, entry_i=e_i, exit_i=start + k_exit, dir=d, entry=round(entry, 2),
                         stop=round(sl_px, 2), target=round(tp_px, 2), risk=round(risk, 2), pts=round(net, 2),
                         R=net / risk, exit=why, session=ctx["sess"][i]))
        busy_until = start + k_exit
    return pd.DataFrame(rows)


def _session_ok(lab: str, mode: str) -> bool:
    if mode == "Asie + NY AM":
        return lab in ("Asie", "NY AM")
    if mode == "NY AM":
        return lab == "NY AM"
    if mode == "Londres + NY AM":
        return lab in ("Londres", "NY AM")
    return True


def context_arrays(df: pd.DataFrame) -> dict:
    lc, lo = mmpd(df, 27)
    return dict(o=df["open"].values, h=df["high"].values, l=df["low"].values, c=df["close"].values,
                atr=atr(df), sess=np.array([session_label(t) for t in df.index]),
                xp=np.maximum(lc, lo) >= 80, xd=np.minimum(lc, lo) <= 20, daily=daily_direction(df))


def random_baseline(df: pd.DataFrame, trades: pd.DataFrame, tp, cost: float, ctx: dict, seed: int = 11, max_bars: int = 64) -> float:
    """Entrée au marché sur une bougie aléatoire de la même session, même sens, même taille de stop, X1."""
    if trades.empty:
        return np.nan
    rng = np.random.default_rng(seed)
    by_sess = {s: np.where(ctx["sess"] == s)[0] for s in np.unique(ctx["sess"])}
    res = []
    for _, t in trades.iterrows():
        pool = by_sess.get(t["session"], np.arange(len(df)))
        pool = pool[pool < len(df) - 2]
        if len(pool) == 0:
            continue
        i = int(rng.choice(pool))
        s = dict(i=i, dir=int(t["dir"]), entry_kind="close", nat_stop=ctx["c"][i] - t["dir"] * t["risk"], nat_tp=None)
        r = simulate(df, [s], stop="Structure", tp=(2.0 if tp == "nat" else tp), half=False, cost=cost, ctx=ctx, max_bars=max_bars)
        if not r.empty:
            res.append(r["R"].iloc[0])
    return float(np.mean(res)) if res else np.nan


# ------------------------------------------------------------- statistiques
def stats(tr: pd.DataFrame, point_value: float = 2.0) -> dict:
    if tr is None or tr.empty:
        return dict(n=0, wr=np.nan, avg_r=np.nan, pf=np.nan, t=np.nan, max_dd=np.nan, streak=0, net_pts=0.0, net_usd=0.0, avg_risk=np.nan)
    r = tr["R"].values
    wins, losses = r[r > 0], r[r <= 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf
    sd = r.std(ddof=1) if len(r) > 1 else np.nan
    t = r.mean() / (sd / np.sqrt(len(r))) if sd and sd > 0 else np.nan
    eq = np.cumsum(r)
    dd = float((np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max()) if len(eq) else 0.0
    streak = cur = 0
    for v in r:
        cur = cur + 1 if v <= 0 else 0
        streak = max(streak, cur)
    return dict(n=len(r), wr=len(wins) / len(r) * 100, avg_r=r.mean(), pf=pf, t=t, max_dd=dd, streak=streak,
                net_pts=float(tr["pts"].sum()), net_usd=float(tr["pts"].sum() * point_value), avg_risk=float(tr["risk"].mean()))


def evaluate(df: pd.DataFrame, trades: pd.DataFrame, tp, cost: float, ctx: dict, split: float = 0.7, neighbours: list | None = None) -> dict:
    """Les contrôles de preuve (inspirés des 7 contrôles du site) + verdict."""
    out = dict(all=stats(trades))
    if trades.empty:
        out.update(old=stats(trades), fresh=stats(trades), checks={}, verdict="DON'T TRADE", random=np.nan)
        return out
    cut = df.index[int(len(df) * split)]
    old, fresh = trades[trades["time"] < cut], trades[trades["time"] >= cut]
    out["old"], out["fresh"] = stats(old), stats(fresh)
    out["cut"] = cut
    rnd = random_baseline(df, trades, tp, cost, ctx)
    out["random"] = rnd
    a = out["all"]
    years = trades.groupby(trades["time"].dt.year)["R"].mean()
    minus5 = trades["R"].sort_values().iloc[:-5].mean() if len(trades) > 10 else np.nan
    chk = {
        "1 · avg RR > 0 et PF ≥ 1,3 après coûts": bool(a["avg_r"] > 0 and a["pf"] >= 1.3),
        "2 · bat le tirage ALÉATOIRE": bool(not np.isnan(rnd) and a["avg_r"] > rnd),
        "3 · t-score ≥ 2 (≥ 3 = preuve forte)": bool(a["t"] >= 2) if not np.isnan(a["t"]) else False,
        "4 · positif en période ancienne ET récente": bool(out["old"]["avg_r"] > 0 and out["fresh"]["avg_r"] > 0),
        "5 · plateau : voisins majoritairement positifs": bool(neighbours is not None and len(neighbours) and np.mean(np.array(neighbours) > 0) >= 2 / 3),
        "6 · positif sur la majorité des années": bool((years > 0).mean() > 0.5) if len(years) else False,
        "7 · reste positif sans les 5 meilleurs trades": bool(minus5 > 0) if not np.isnan(minus5) else False,
    }
    out["checks"], out["minus5"], out["years"] = chk, minus5, years
    n_old, n_fr = out["old"]["n"], out["fresh"]["n"]
    pos_both = chk["4 · positif en période ancienne ET récente"]
    t_old, t_fr = out["old"]["t"], out["fresh"]["t"]
    if pos_both and n_old >= 30 and n_fr >= 10 and (t_old or 0) >= 2 and (t_fr or 0) >= 1.5 and chk["2 · bat le tirage ALÉATOIRE"]:
        v = "TRADE"
    elif pos_both:
        v = "WATCH"
    else:
        v = "DON'T TRADE"
    out["verdict"] = v
    return out


def run_canonical(df: pd.DataFrame, swing_n: int = 2, cost: float = 1.0, session: str = "Toutes",
                  gate: str = "Aucun", max_bars: int = 64) -> tuple[dict, dict, dict]:
    """Chaque setup avec ses règles canoniques. Retourne (résultats, signaux, contexte)."""
    ctx = context_arrays(df)
    sigs = build_signals(df, swing_n)
    res = {}
    for name, (fam, desc, d) in SETUPS.items():
        tr = simulate(df, sigs[name], d["stop"], d["tp"], d["half"], cost, max_bars, session, gate, d.get("daily", False), ctx)
        neigh = []
        for alt_tp in ([1.5, 2.5] if d["tp"] != "nat" else []):
            t2 = simulate(df, sigs[name], d["stop"], alt_tp, d["half"], cost, max_bars, session, gate, d.get("daily", False), ctx)
            if not t2.empty:
                neigh.append(t2["R"].mean())
        alt_stop = "ATR×2" if d["stop"] != "ATR×2" else "ATR×1.5"
        t3 = simulate(df, sigs[name], alt_stop, d["tp"], d["half"], cost, max_bars, session, gate, d.get("daily", False), ctx)
        if not t3.empty:
            neigh.append(t3["R"].mean())
        ev = evaluate(df, tr, d["tp"], cost, ctx, neighbours=neigh)
        res[name] = dict(family=fam, desc=desc, rules=d, trades=tr, eval=ev)
    return res, sigs, ctx


def filter_tests(df: pd.DataFrame, sigs: dict, ctx: dict, cost: float = 1.0, max_bars: int = 64) -> list:
    """Teste chaque filtre sur tous les setups : USE AS FILTER s'il améliore l'avg RR dans les 2 périodes."""
    cut = df.index[int(len(df) * 0.7)]
    filters = [("Sessions Asie + NY AM", dict(session="Asie + NY AM")), ("Session NY AM seule", dict(session="NY AM")),
               ("Gate MMPD 27 momentum", dict(gate="MMPD 27 momentum")), ("Bougie journalière d'hier dans le sens", dict(daily=True))]
    out = []
    for fname, kw in filters:
        better_old = better_fr = tested = 0
        deltas = []
        for name, (fam, desc, d) in SETUPS.items():
            base = simulate(df, sigs[name], d["stop"], d["tp"], d["half"], cost, max_bars, ctx=ctx)
            args = dict(session=kw.get("session", "Toutes"), gate=kw.get("gate", "Aucun"), daily=kw.get("daily", False))
            filt = simulate(df, sigs[name], d["stop"], d["tp"], d["half"], cost, max_bars, ctx=ctx, **args)
            if len(base) < 10 or len(filt) < 5:
                continue
            tested += 1
            bo, bf = base[base.time < cut]["R"].mean(), base[base.time >= cut]["R"].mean()
            fo, ff = filt[filt.time < cut]["R"].mean(), filt[filt.time >= cut]["R"].mean()
            better_old += int((fo or 0) > (bo or 0))
            better_fr += int((ff or 0) > (bf or 0))
            deltas.append(filt["R"].mean() - base["R"].mean())
        if tested:
            ok = better_old / tested >= 0.6 and better_fr / tested >= 0.6
            out.append(dict(filtre=fname, setups_testés=tested, améliore_ancien=f"{better_old}/{tested}",
                            améliore_récent=f"{better_fr}/{tested}", delta_avg_R=round(float(np.mean(deltas)), 3),
                            verdict="USE AS FILTER" if ok else ("WATCH" if np.mean(deltas) > 0 else "DON'T TRADE")))
    return out


def run_grid(df: pd.DataFrame, sigs: dict, ctx: dict, cost: float = 1.0, max_bars: int = 64, progress=None) -> pd.DataFrame:
    stops = ["Structure", "ATR×1", "ATR×1.5", "ATR×2", "Fixe 50"]
    tps = [1.0, 2.0, 3.0, 6.0]
    sessions = ["Toutes", "Asie + NY AM", "NY AM"]
    halves = [False, True]
    rows = []
    cut = df.index[int(len(df) * 0.7)]
    total = len(SETUPS) * len(stops) * len(tps) * len(sessions) * len(halves)
    k = 0
    for name in SETUPS:
        for stp in stops:
            for tp in tps:
                for se in sessions:
                    for hf in halves:
                        k += 1
                        tr = simulate(df, sigs[name], stp, tp, hf, cost, max_bars, se, ctx=ctx)
                        if progress and k % 40 == 0:
                            progress(k / total)
                        if len(tr) < 10:
                            continue
                        s = stats(tr)
                        o_, f_ = tr[tr.time < cut]["R"], tr[tr.time >= cut]["R"]
                        rows.append(dict(setup=name, stop=stp, objectif=f"1:{tp:g}", session=se, demi_sortie="½ à +0,5R" if hf else "non",
                                         trades=s["n"], WR=round(s["wr"], 1), avg_RR=round(s["avg_r"], 3),
                                         PF=round(s["pf"], 2) if np.isfinite(s["pf"]) else 99.0, t=round(s["t"], 2) if not np.isnan(s["t"]) else 0,
                                         avg_RR_ancien=round(o_.mean(), 3) if len(o_) else np.nan,
                                         avg_RR_récent=round(f_.mean(), 3) if len(f_) else np.nan,
                                         max_DD_R=round(s["max_dd"], 1), pertes_de_suite=s["streak"]))
    return pd.DataFrame(rows)


# ----------------------------------------------------------- odds & niveaux
def candle_odds(df: pd.DataFrame, horizon: int = 2) -> pd.DataFrame:
    """Méthode du PDF : après une bougie BC/AFs clôturée, la cible (extrême de la bougie signal) est-elle
    atteinte avant l'invalidation (extrême opposé) dans les `horizon` bougies suivantes ?"""
    ty = candle_types(df)
    h, l, o = df["high"].values, df["low"].values, df["open"].values
    rows = []
    for i in range(1, len(df) - 1):
        t = ty[i]
        if t not in ("BC+", "BC−", "AFs+", "AFs−"):
            continue
        d = 1 if t.endswith("+") else -1
        tgt = h[i] if t == "BC+" else (l[i] if t == "BC−" else (h[i - 1] if t == "AFs+" else l[i - 1]))
        stp = l[i] if d == 1 else h[i]
        win = inv = both = 0
        bars = np.nan
        for k in range(i + 1, min(len(df), i + 1 + horizon)):
            ht = h[k] >= tgt if d == 1 else l[k] <= tgt
            hs = l[k] <= stp if d == 1 else h[k] >= stp
            if ht and hs:
                both = 1
                break
            if ht:
                win, bars = 1, k - i
                break
            if hs:
                inv = 1
                break
        rows.append(dict(time=df.index[i], type=t, win=win, inv=inv, both=both, bars=bars,
                         reward=abs(tgt - o[i + 1]), risk=abs(o[i + 1] - stp)))
    return pd.DataFrame(rows)


def odds_table(od: pd.DataFrame, by: str = "heure") -> pd.DataFrame:
    if od.empty:
        return od
    x = od.copy()
    x["heure"] = x["time"].dt.strftime("%Hh")
    x["session"] = [session_label(t) for t in x["time"]]
    x["jour"] = x["time"].dt.day_name()
    g = x.groupby([by, "type"]).agg(N=("win", "size"), Win=("win", "mean"), Invalid=("inv", "mean"),
                                    Les_deux=("both", "mean"), Barres=("bars", "mean"),
                                    gain_pts=("reward", "median"), risque_pts=("risk", "median")).reset_index()
    for k in ["Win", "Invalid", "Les_deux"]:
        g[k] = (g[k] * 100).round(1)
    g["Barres"] = g["Barres"].round(2)
    g["Feu"] = np.where(g["Win"] >= 65, "🟢", np.where(g["Win"] >= 55, "🟡", "🔴"))
    return g.sort_values([by, "Win"], ascending=[True, False])


def momentum_wall(df: pd.DataFrame) -> pd.DataFrame:
    """Probabilité qu'une série de bougies de construction (BC dans le même sens) continue après k bougies."""
    ty = candle_types(df)
    rows = []
    for sign, lab in [("BC+", "Haussier"), ("BC−", "Baissier")]:
        runs, cur = [], 0
        for t in ty:
            if t == sign:
                cur += 1
            elif cur:
                runs.append(cur)
                cur = 0
        runs = np.array(runs)
        for k in range(1, 6):
            reach = (runs >= k).sum()
            cont = (runs >= k + 1).sum()
            rows.append(dict(sens=lab, compte=k, séries=int(reach), continue_pct=round(cont / reach * 100, 1) if reach else np.nan))
    return pd.DataFrame(rows)


def prop_montecarlo(r: np.ndarray, risk_usd: float, target: float = 3000.0, max_dd: float = 2500.0,
                    n_sims: int = 3000, max_trades: int = 300, seed: int = 3) -> dict:
    """Passage d'une évaluation (type Apex 50K) en tirant les trades au hasard dans l'échantillon."""
    if len(r) < 10:
        return {}
    rng = np.random.default_rng(seed)
    passed = failed = 0
    lens = []
    for _ in range(n_sims):
        bal = hwm = 0.0
        for k in range(max_trades):
            bal += rng.choice(r) * risk_usd
            hwm = max(hwm, bal)
            if bal >= target:
                passed += 1
                lens.append(k + 1)
                break
            if bal <= min(hwm, 100.0) - max_dd:  # drawdown suiveur bloqué à +100 $
                failed += 1
                break
    return dict(pass_rate=passed / n_sims * 100, fail_rate=failed / n_sims * 100,
                undecided=(n_sims - passed - failed) / n_sims * 100, trades_to_pass=float(np.median(lens)) if lens else np.nan)
