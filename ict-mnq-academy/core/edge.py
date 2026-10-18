"""Edge 5 Desk — moteur commun à la plateforme ET au script TradingView « Edge 5 Desk » (mêmes règles).

Setups (15 min, MNQ) — inspirés des 5 setups publiés par maxmaserati.com, réimplémentés ici :
  M1 Z  · marche T3+ (LDs2+/SDs2+) à la clôture, long + short · stop 1,5 ATR · ½ à +0,5 R · runner 1:6 ou flip opposé · filtre : journalière d'hier
  M2 G  · GMC haussier (c2 = BC+, c3 laisse un vide) · clôture c3 · stop 1 ATR · ½ à +0,75 R · runner 1:3 · filtre : journalière
  M3 B  · GMC haussier dont c3 fait un nouveau haut et réintègre c2 (AFs contre) · stop 1 ATR · ½ à +0,5 R · runner 1:6 · journalière + 1H
  M4 C  · contraction (5 bougies ≤ 1,6 ATR) cassée vers le haut → limite à 75 % de la bougie de cassure, 1 tick au travers,
          remplie en Asie (18h–02h) · stop fixe 50 · ½ à +0,5 R · runner 1:2 · pas de filtre HTF
  M5 M  · BC+ sans plus bas inférieur, clôture dans la moitié haute · stop fixe 50 · ½ à +0,5 R · runner 1:2 · journalière + 1H
Communs : gate MMPD 27 momentum (long si max(c,o) ≥ 80, short si min ≤ 20), sessions Asie 18h–02h + NY AM 09h30–13h30,
00h–02h exclu sauf C, 2 positions max, 1 par setup, coût 1 point par trade, stop prioritaire si stop et objectif dans la même bougie,
après la ½ sortie le stop du runner passe à l'entrée (« profit kept »), sortie forcée après `max_bars` bougies.
Aucune décision n'utilise une bougie non clôturée ni une information future."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import resample
from .mmm import _stair_engine, atr, candle_types, daily_direction, in_window, minute_of_day, mmpd

SETUPS = {
    1: dict(code="Z", name="M1 · Z T3+ BREAK", sides=(1, -1), stop=("atr", 1.5), half=0.5, tp=6.0, flip_exit=True,
            daily=True, h1=False, htf="D · 15m · 15m"),
    2: dict(code="G", name="M2 · G GMC LONG", sides=(1,), stop=("atr", 1.0), half=0.75, tp=3.0, flip_exit=False,
            daily=True, h1=False, htf="D · 15m · 15m"),
    3: dict(code="B", name="M3 · B GMC AFs", sides=(1,), stop=("atr", 1.0), half=0.5, tp=6.0, flip_exit=False,
            daily=True, h1=True, htf="D+1H · 15m · 15m"),
    4: dict(code="C", name="M4 · C CONTR LIMIT", sides=(1,), stop=("fix", 50.0), half=0.5, tp=2.0, flip_exit=False,
            daily=False, h1=False, htf="— · 15m · 15m lmt"),
    5: dict(code="M", name="M5 · M BC+ LONG", sides=(1,), stop=("fix", 50.0), half=0.5, tp=2.0, flip_exit=False,
            daily=True, h1=True, htf="D+1H · 15m · 15m"),
}
ASIA = (18 * 60, 2 * 60)
NY_AM = (9 * 60 + 30, 13 * 60 + 30)
DEAD = (0, 2 * 60)
TICK = 0.25


@dataclass
class Config:
    enabled: tuple = (1, 2, 3, 4, 5)
    half_out: bool = True
    gate: bool = True
    use_daily: bool = True
    use_h1: bool = True
    sessions: bool = True
    max_open: int = 2
    cost_pts: float = 1.0
    max_bars: int = 96
    swing_n: int = 2
    point_value: float = 2.0      # MNQ
    contracts: int = 2
    skip_dates: tuple = ()        # jours CPI / NFP / FOMC à ignorer (dates NY, AAAA-MM-JJ)


@dataclass
class EdgeResult:
    df: pd.DataFrame
    trades: pd.DataFrame
    open_trades: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    ctx: dict = field(default_factory=dict)
    signals_now: list = field(default_factory=list)
    cfg: Config = None


# ----------------------------------------------------------------- contexte
def h1_direction(df: pd.DataFrame, swing_n: int = 2) -> np.ndarray:
    """Sens de l'escalier 1H de la DERNIÈRE bougie 1H clôturée avant l'heure en cours (= request.security(..., [1], lookahead_on))."""
    h1 = resample(df, "1h")
    if len(h1) < 10:
        return np.zeros(len(df), int)
    st = np.sign(_stair_engine(h1, swing_n)["state"]).astype(int)
    cur_hour = df.index.floor("1h")
    pos = np.searchsorted(h1.index.values, cur_hour.values, side="left") - 1  # bougie 1H précédant l'heure courante
    out = np.where(pos >= 0, st[np.clip(pos, 0, len(st) - 1)], 0)
    return out.astype(int)


def build_context(df: pd.DataFrame, cfg: Config) -> dict:
    o, h, l, c = (df[k].values for k in ["open", "high", "low", "close"])
    N = len(df)
    ty = candle_types(df)
    a = atr(df)
    mc, mo = mmpd(df, 27)
    eng = _stair_engine(df, cfg.swing_n)
    ev_kind = np.zeros(N, int)   # 1 flip, 2 continuation
    ev_dir = np.zeros(N, int)
    for e in eng["events"]:
        ev_kind[e["i"]] = 1 if e["kind"] in ("CDL", "CDS") else 2
        ev_dir[e["i"]] = e["dir"]
    st = eng["state"]
    m = minute_of_day(df.index)
    asia, ny, dead = in_window(m, ASIA), in_window(m, NY_AM), in_window(m, DEAD)
    ph = np.concatenate([[np.nan], h[:-1]])
    ph2 = np.concatenate([[np.nan, np.nan], h[:-2]])
    pl = np.concatenate([[np.nan], l[:-1]])
    bc_up = c > ph
    gmc_up = np.zeros(N, bool)
    gmc_up[2:] = bc_up[1:-1] & (l[2:] > ph2[2:])
    afs_ag = (h > ph) & (c <= ph)
    rng = h - l
    m_long = bc_up & (l >= pl) & (rng > 0) & ((c - l) >= 0.5 * rng)
    box_hi = pd.Series(h).rolling(5).max().shift(1).values
    box_lo = pd.Series(l).rolling(5).min().shift(1).values
    a_prev = np.concatenate([[np.nan], a[:-1]])
    contr = (box_hi - box_lo) <= 1.6 * a_prev
    c_break = contr & (c > box_hi)
    return dict(date=np.array([d.strftime("%Y-%m-%d") for d in df.index]), o=o, h=h, l=l, c=c, ty=ty, atr=a, xp=np.maximum(mc, mo) >= 80, xd=np.minimum(mc, mo) <= 20,
                mmpd_c=mc, mmpd_o=mo, ev_kind=ev_kind, ev_dir=ev_dir, state=st, protect=eng["protect"],
                pending_P=eng["pending_P"], asia=asia, ny=ny, dead=dead,
                daily=daily_direction(df), h1=h1_direction(df, cfg.swing_n),
                sig={1: (ev_kind == 2) & (st >= 3), -1: (ev_kind == 2) & (st <= -3)},  # Z
                gmc_up=gmc_up, afs_ag=afs_ag, m_long=m_long, c_break=c_break, box_hi=box_hi)


def raw_signal(ctx: dict, sid: int, i: int, d: int) -> bool:
    if sid == 1:
        return bool(ctx["sig"][d][i])
    if d != 1:
        return False
    if sid == 2:
        return bool(ctx["gmc_up"][i])
    if sid == 3:
        return bool(ctx["gmc_up"][i] and ctx["afs_ag"][i])
    if sid == 5:
        return bool(ctx["m_long"][i])
    return False


def filter_reason(ctx: dict, cfg: Config, sid: int, i: int, d: int) -> str | None:
    """None si le trade est autorisé, sinon la raison (time / gate / daily / 1h)."""
    s = SETUPS[sid]
    if cfg.skip_dates and ctx["date"][i] in cfg.skip_dates:
        return "news"
    if cfg.sessions and sid != 4:
        if not (ctx["asia"][i] or ctx["ny"][i]) or ctx["dead"][i]:
            return "time"
    if cfg.gate and not ((d == 1 and ctx["xp"][i]) or (d == -1 and ctx["xd"][i])):
        return "gate"
    if cfg.use_daily and s["daily"] and ctx["daily"][i] != d:
        return "daily"
    if cfg.use_h1 and s["h1"] and ctx["h1"][i] != d:
        return "1h"
    return None


# ----------------------------------------------------------------- simulation
def _new_trade(sid, num, d, entry, i, risk, cfg):
    s = SETUPS[sid]
    return dict(sid=sid, code=s["code"], label=f"M{sid}T{num}", dir=d, entry=entry, entry_i=i, risk=risk,
                stop=entry - d * risk, init_stop=entry - d * risk,
                half_px=entry + d * risk * s["half"] if cfg.half_out else None,
                tp=entry + d * risk * s["tp"], half_done=False)


def _close(t, i, px, reason, cfg, df):
    d, risk = t["dir"], t["risk"]
    s = SETUPS[t["sid"]]
    if t["half_done"]:
        r_gross = 0.5 * s["half"] + 0.5 * (px - t["entry"]) * d / risk
    else:
        r_gross = (px - t["entry"]) * d / risk
    r = r_gross - cfg.cost_pts / risk
    pts = r * risk
    t.update(exit_i=i, exit=px, reason=reason, R=r, pts=pts, usd=pts * cfg.point_value * cfg.contracts,
             time=df.index[t["entry_i"]], exit_time=df.index[i])
    return t


def run_edge(df: pd.DataFrame, cfg: Config | None = None) -> EdgeResult:
    cfg = cfg or Config()
    N = len(df)
    res = EdgeResult(df=df, trades=pd.DataFrame(), cfg=cfg)
    if N < 60:
        return res
    ctx = build_context(df, cfg)
    o, h, l, c, a = ctx["o"], ctx["h"], ctx["l"], ctx["c"], ctx["atr"]
    open_t, pending, closed = [], [], []
    count = {k: 0 for k in SETUPS}
    for i in range(N):
        # 1) gestion des positions ouvertes (à partir de la bougie suivant l'entrée)
        for t in list(open_t):
            if t["entry_i"] >= i:
                continue
            d = t["dir"]
            hit_stop = l[i] <= t["stop"] if d == 1 else h[i] >= t["stop"]
            if hit_stop:
                px = min(o[i], t["stop"]) if d == 1 else max(o[i], t["stop"])
                closed.append(_close(t, i, px, "stop" if not t["half_done"] else "trail stop, profit kept", cfg, df))
                open_t.remove(t)
                continue
            if t["half_px"] is not None and not t["half_done"] and ((h[i] >= t["half_px"]) if d == 1 else (l[i] <= t["half_px"])):
                t["half_done"] = True
                t["stop"] = t["entry"]
            if (h[i] >= t["tp"]) if d == 1 else (l[i] <= t["tp"]):
                closed.append(_close(t, i, t["tp"], "TP", cfg, df))
                open_t.remove(t)
                continue
            if SETUPS[t["sid"]]["flip_exit"] and ctx["ev_kind"][i] == 1 and ctx["ev_dir"][i] == -d:
                closed.append(_close(t, i, c[i], "flip opposé", cfg, df))
                open_t.remove(t)
                continue
            if i - t["entry_i"] >= cfg.max_bars:
                closed.append(_close(t, i, c[i], "temps", cfg, df))
                open_t.remove(t)
        # 2) ordre limite C : remplissage 1 tick au travers, en Asie uniquement
        for p in list(pending):
            if i <= p["i"]:
                continue
            if i - p["i"] > 20 or h[i] >= p["limit"] + 2 * p["risk"]:
                pending.remove(p)
                continue
            if l[i] <= p["limit"] - TICK and (ctx["asia"][i] or not cfg.sessions) and ctx["date"][i] not in cfg.skip_dates:
                if len(open_t) < cfg.max_open and not any(t["sid"] == 4 for t in open_t):
                    count[4] += 1
                    t = _new_trade(4, count[4], 1, p["limit"], i, p["risk"], cfg)
                    open_t.append(t)
                pending.remove(p)
        # 3) nouveaux signaux à la clôture de la bougie i
        for sid in SETUPS:
            if sid not in cfg.enabled:
                continue
            if sid == 4:
                if ctx["c_break"][i] and not pending and (not cfg.gate or ctx["xp"][i]):
                    lim = l[i] + 0.75 * (h[i] - l[i])
                    pending.append(dict(i=i, limit=float(lim), risk=SETUPS[4]["stop"][1]))
                continue
            for d in SETUPS[sid]["sides"]:
                if not raw_signal(ctx, sid, i, d) or filter_reason(ctx, cfg, sid, i, d):
                    continue
                if len(open_t) >= cfg.max_open or any(t["sid"] == sid for t in open_t):
                    continue
                kind, k = SETUPS[sid]["stop"]
                risk = k * a[i] if kind == "atr" else k
                if not risk or risk < 4 * TICK or np.isnan(risk):
                    continue
                count[sid] += 1
                open_t.append(_new_trade(sid, count[sid], d, float(c[i]), i, float(risk), cfg))
    res.trades = pd.DataFrame(closed)
    res.open_trades, res.pending, res.ctx = open_t, pending, ctx
    res.signals_now = signals_now(ctx, cfg, N - 1)
    return res


# ------------------------------------------------------------ lecture live
def signals_now(ctx: dict, cfg: Config, i: int) -> list:
    """Statut de chaque setup sur la DERNIÈRE bougie clôturée : FIRE, ON (attente) ou OFF · raison."""
    out = []
    for sid, s in SETUPS.items():
        if sid not in cfg.enabled:
            out.append(dict(sid=sid, status="OFF · désactivé", dir=0))
            continue
        if sid == 4:
            fired = bool(ctx["c_break"][i])
            r = None if (ctx["asia"][i] or not cfg.sessions) else "time"
            out.append(dict(sid=sid, status=("FIRE · limite posée" if fired else "ON · attend une contraction") if not r
                            else ("FIRE · limite (remplissage en Asie)" if fired else "OFF · time"), dir=1 if fired else 0))
            continue
        best = None
        for d in s["sides"]:
            reason = filter_reason(ctx, cfg, sid, i, d)
            fired = raw_signal(ctx, sid, i, d)
            if fired and not reason:
                best = dict(sid=sid, status="FIRE", dir=d)
                break
            if best is None:
                best = dict(sid=sid, status=("OFF · " + reason) if reason else "ON · attend le signal", dir=0)
        out.append(best)
    return out


def order_ticket(res: EdgeResult, sid: int, d: int, risk_usd: float) -> dict:
    """Ticket d'ordre pour un signal FIRE de la dernière bougie : entrée, SL, ½ TP, TP, contrats pour un risque en $."""
    ctx, df = res.ctx, res.df
    i = len(df) - 1
    s = SETUPS[sid]
    if sid == 4:
        entry = float(ctx["l"][i] + 0.75 * (ctx["h"][i] - ctx["l"][i]))
        risk = s["stop"][1]
    else:
        entry = float(ctx["c"][i])
        risk = s["stop"][1] * ctx["atr"][i] if s["stop"][0] == "atr" else s["stop"][1]
    q = max(1, int(risk_usd // (risk * res.cfg.point_value))) if risk > 0 else 1
    return dict(setup=s["name"], side="LONG" if d == 1 else "SHORT", type="Limite" if sid == 4 else "Marché (clôture)",
                entry=round(entry / TICK) * TICK, stop=round((entry - d * risk) / TICK) * TICK,
                half=round((entry + d * risk * s["half"]) / TICK) * TICK, tp=round((entry + d * risk * s["tp"]) / TICK) * TICK,
                risk_pts=round(risk, 2), contracts=q, risk_usd=round(q * risk * res.cfg.point_value, 2))


# ------------------------------------------------------------------ stats
def setup_stats(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = [(sid, trades[trades["sid"] == sid]) for sid in SETUPS] + [(0, trades)] if not trades.empty else []
    for sid, g in groups:
        name = SETUPS[sid]["name"] if sid else "ALL 5"
        if g.empty:
            rows.append(dict(sid=sid, setup=name, trades=0))
            continue
        r = g["R"].values
        n = len(r)
        sd = r.std(ddof=1) if n > 1 else np.nan
        eq = np.cumsum(r)
        dd = float((np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max())
        cut = int(n * 0.7)
        streak = cur = 0
        for v in r:
            cur = cur + 1 if v <= 0 else 0
            streak = max(streak, cur)
        gl = -r[r <= 0].sum()
        rows.append(dict(sid=sid, setup=name, trades=n, WR=(r > 0).mean() * 100, avg_RR=r.mean(),
                         avg_RR_ancien=r[:cut].mean() if cut else np.nan, avg_RR_récent=r[cut:].mean() if n - cut else np.nan,
                         PF=r[r > 0].sum() / gl if gl > 0 else np.inf, t=r.mean() / (sd / np.sqrt(n)) if sd and sd > 0 else np.nan,
                         worst_run_R=dd, pertes_de_suite=streak, net_usd=g["usd"].sum()))
    return pd.DataFrame(rows)


def verdict(row) -> str:
    if not row.get("trades"):
        return "—"
    n, t = row["trades"], row.get("t", np.nan)
    old, new = row.get("avg_RR_ancien", np.nan), row.get("avg_RR_récent", np.nan)
    if n >= 30 and old > 0 and new > 0 and t >= 2.5:
        return "TRADE"
    if old > 0 and new > 0:
        return "WATCH"
    return "DON'T TRADE"


def prop_helper(trades: pd.DataFrame, contracts: int, target: float = 3000.0, max_dd: float = 2500.0,
                lock_at: float = 100.0, point_value: float = 2.0) -> dict:
    """« Tes règles sur l'historique de ce graphique » : on démarre une évaluation à chaque trade de l'historique
    et on rejoue la suite réelle jusqu'à l'objectif (PASS) ou au drawdown suiveur (FAIL). Le seuil suit le plus haut
    et se bloque à +lock_at (règle type Apex)."""
    if trades is None or trades.empty:
        return dict(n=0, pass_rate=np.nan, fail_rate=np.nan, days=np.nan, passes=0, fails=0)
    usd = (trades["pts"].values * point_value * contracts)
    t0 = pd.to_datetime(trades["time"]).values
    t1 = pd.to_datetime(trades["exit_time"]).values
    passes, fails, days = 0, 0, []
    for j in range(len(usd)):
        eq = peak = 0.0
        for k in range(j, len(usd)):
            eq += usd[k]
            peak = max(peak, eq)
            floor = min(peak - max_dd, lock_at)
            if eq >= target:
                passes += 1
                days.append((t1[k] - t0[j]) / np.timedelta64(1, "D"))
                break
            if eq <= floor:
                fails += 1
                break
    dec = passes + fails
    return dict(n=dec, passes=passes, fails=fails, pass_rate=passes / dec * 100 if dec else np.nan,
                fail_rate=fails / dec * 100 if dec else np.nan, days=float(np.median(days)) if days else np.nan)


def prop_table(trades_half: pd.DataFrame, trades_full: pd.DataFrame, contracts: int, target: float, max_dd: float,
               point_value: float = 2.0, sizes=(1, 2, 3, 4, 5, 6, 8, 10)) -> pd.DataFrame:
    rows = []
    for label, tr in (("½", trades_half), ("FULL", trades_full)):
        if tr is None or tr.empty:
            continue
        for sid in list(SETUPS) + [0]:
            g = tr if sid == 0 else tr[tr["sid"] == sid]
            name = ("ALL 5" if sid == 0 else f"M{sid}") + f" · {label}"
            if len(g) < 3:
                rows.append(dict(setup=name, trades=len(g), pass_you="pas assez de trades"))
                continue
            you = prop_helper(g, contracts, target, max_dd, point_value=point_value)
            best = None
            for s in sizes:
                x = prop_helper(g, s, target, max_dd, point_value=point_value)
                if x["n"] and (best is None or x["pass_rate"] > best[1]["pass_rate"] + 1e-9):
                    best = (s, x)
            rows.append(dict(setup=name, trades=len(g),
                             pass_you=f"{you['pass_rate']:.0f} % ({you['passes']}✓ {you['fails']}✗)" if you["n"] else "aucune décidée",
                             jours_médians=round(you["days"], 1) if not np.isnan(you["days"]) else None,
                             meilleure_taille=f"{best[0]} MNQ" if best and best[1]["pass_rate"] > 0 else "aucune ne passe",
                             pass_meilleure=f"{best[1]['pass_rate']:.0f} %" if best and best[1]["pass_rate"] > 0 else "—"))
    return pd.DataFrame(rows)


def desk_rows(res: EdgeResult) -> list:
    """Lignes du tableau de bord (format proche du panneau TradingView)."""
    df, ctx, cfg = res.df, res.ctx, res.cfg
    if not ctx:
        return []
    i = len(df) - 1
    t = df.index[i]
    m = t.hour * 60 + t.minute
    if (in_window([m], ASIA)[0] and not in_window([m], DEAD)[0]) or in_window([m], NY_AM)[0]:
        win = "OPEN · " + ("Asie" if in_window([m], ASIA)[0] else "NY AM")
    else:
        nxt = "18:00" if m >= NY_AM[1] else ("09:30" if m < NY_AM[0] else "18:00")
        win = f"CLOSED · opens {nxt}" + (" (C reste actif 00–02)" if in_window([m], DEAD)[0] else "")
    st = int(ctx["state"][i])
    nxtP = res.ctx["pending_P"]
    z_txt = (f"{'▲' if st > 0 else '▼'} T{abs(st)}" if st else "—") + (
        f" · M1 fires {'>' if st > 0 else '<'} {nxtP[1]:.2f}" if nxtP is not None and abs(st) >= 2 else "")
    mcv, mov = ctx["mmpd_c"][i], ctx["mmpd_o"][i]
    zone = "XP" if max(mcv, mov) >= 80 else ("XD" if min(mcv, mov) <= 20 else "MID")
    gate = {"XP": "longs OK · shorts wait", "XD": "longs wait · shorts OK", "MID": "longs wait · shorts wait"}[zone]
    gm = "GMC ▲ actif (M2/M3 possibles)" if ctx["gmc_up"][max(0, i - 3):i + 1].any() else "pas de GMC récent"
    return [("NOW", f"{t:%a %H:%M} NY"), ("WINDOW", win),
            ("DAILY", {1: "▲ BULL · last session", -1: "▼ BEAR · last session", 0: "neutre"}[int(ctx["daily"][i])]),
            ("1H TREND", {1: "▲ BULL · stair engine", -1: "▼ BEAR · stair engine", 0: "neutre"}[int(ctx["h1"][i])]),
            ("15m stair", z_txt), ("15m c", gm), ("MMPD 27", f"{mcv:.0f} · {zone} · {gate}"),
            ("OPEN", ", ".join(f"{x['label']} {'L' if x['dir'] == 1 else 'S'} @ {x['entry']:.2f}" for x in res.open_trades) or "flat")]
