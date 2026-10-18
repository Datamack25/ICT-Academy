"""Compte de trading fictif MNQ (paper trading) — exécution bougie par bougie, sans regarder le futur."""
from __future__ import annotations

import uuid

import pandas as pd

from .data import MNQ_SPEC


def new_account(start: float = 50_000.0, trailing_dd: float = 2_500.0, commission: float = 0.52,
                max_contracts: int = 10, spec: dict | None = None) -> dict:
    return dict(start=start, balance=start, hwm=start, trailing_dd=trailing_dd, commission=commission,
                max_contracts=max_contracts, spec=spec or MNQ_SPEC, position=None, pending=[],
                trades=[], last_time=None, failed=False, log=[])


def _round_tick(p: float, tick: float) -> float:
    return round(round(p / tick) * tick, 2)


def threshold(acc: dict) -> float:
    """Seuil de liquidation type Apex : trailing drawdown qui se bloque à start + 100 $."""
    return min(acc["hwm"] - acc["trailing_dd"], acc["start"] + 100)


def unrealized(acc: dict, price: float) -> float:
    pos = acc["position"]
    if not pos:
        return 0.0
    d = 1 if pos["side"] == "LONG" else -1
    return (price - pos["entry"]) * d * pos["qty"] * acc["spec"]["point_value"]


def validate_order(acc, side, qty, price, sl, tp):
    errs = []
    if acc["position"]:
        errs.append("Une position est déjà ouverte : clôture-la avant d'en ouvrir une autre.")
    if qty < 1 or qty > acc["max_contracts"]:
        errs.append(f"Quantité entre 1 et {acc['max_contracts']} contrats.")
    if sl is None or sl == 0:
        errs.append("Stop-loss obligatoire (règle n°1 du cours : toujours une invalidation).")
    else:
        if side == "LONG" and sl >= price:
            errs.append("Pour un LONG, le stop doit être SOUS le prix d'entrée.")
        if side == "SHORT" and sl <= price:
            errs.append("Pour un SHORT, le stop doit être AU-DESSUS du prix d'entrée.")
    if tp:
        if side == "LONG" and tp <= price:
            errs.append("Pour un LONG, l'objectif doit être AU-DESSUS de l'entrée.")
        if side == "SHORT" and tp >= price:
            errs.append("Pour un SHORT, l'objectif doit être SOUS l'entrée.")
    return errs


def open_position(acc, side, qty, price, time, sl, tp, plan=None, context=None):
    tick = acc["spec"]["tick_size"]
    acc["position"] = dict(id=str(uuid.uuid4())[:8], side=side, qty=int(qty), entry=_round_tick(price, tick),
                           entry_time=time, sl=_round_tick(sl, tick), initial_sl=_round_tick(sl, tick),
                           tp=_round_tick(tp, tick) if tp else None, mae=0.0, mfe=0.0,
                           plan=plan or {}, context=context or {})
    acc["balance"] -= acc["commission"] * qty
    acc["log"].append(f"{time:%d/%m %H:%M} — {side} {qty} MNQ @ {acc['position']['entry']:.2f}")


def place_limit(acc, side, qty, price, sl, tp, time, plan=None, context=None):
    acc["pending"].append(dict(id=str(uuid.uuid4())[:8], side=side, qty=int(qty), price=float(price),
                               sl=sl, tp=tp, time=time, plan=plan or {}, context=context or {}))


def close_position(acc, price, time, reason="Manuel"):
    pos = acc["position"]
    if not pos:
        return None
    d = 1 if pos["side"] == "LONG" else -1
    price = _round_tick(price, acc["spec"]["tick_size"])
    pts = (price - pos["entry"]) * d
    gross = pts * pos["qty"] * acc["spec"]["point_value"]
    comm = acc["commission"] * pos["qty"] * 2
    risk_pts = abs(pos["entry"] - pos["initial_sl"])
    trade = dict(id=pos["id"], side=pos["side"], qty=pos["qty"], entry=pos["entry"], exit=price,
                 entry_time=pos["entry_time"], exit_time=time, sl=pos["initial_sl"], tp=pos["tp"],
                 points=round(pts, 2), pnl=round(gross - comm, 2), commission=round(comm, 2),
                 r=round(pts / risk_pts, 2) if risk_pts else 0.0, reason=reason,
                 mae=round(pos["mae"], 2), mfe=round(pos["mfe"], 2),
                 risk_usd=round(risk_pts * pos["qty"] * acc["spec"]["point_value"], 2),
                 plan=pos["plan"], context=pos["context"])
    acc["balance"] += gross - acc["commission"] * pos["qty"]
    acc["trades"].append(trade)
    acc["position"] = None
    acc["hwm"] = max(acc["hwm"], acc["balance"])
    if acc["balance"] <= threshold(acc):
        acc["failed"] = True
    acc["log"].append(f"{time:%d/%m %H:%M} — Sortie {reason} @ {price:.2f} ({trade['pnl']:+.2f} $)")
    return trade


def process_bars(acc: dict, df: pd.DataFrame) -> list:
    """Traite les bougies postérieures à acc['last_time'] : remplit les limites, vérifie SL/TP.
    Règle prudente : si SL et TP sont touchés dans la même bougie, on retient le SL."""
    closed = []
    if df.empty:
        return closed
    new = df if acc["last_time"] is None else df[df.index > acc["last_time"]]
    for t, bar in new.iterrows():
        # 1) ordres limites
        for p in list(acc["pending"]):
            if acc["position"]:
                break
            hit = bar["low"] <= p["price"] if p["side"] == "LONG" else bar["high"] >= p["price"]
            if hit:
                open_position(acc, p["side"], p["qty"], p["price"], t, p["sl"], p["tp"], p["plan"], p["context"])
                acc["pending"].remove(p)
        # 2) gestion de la position
        pos = acc["position"]
        if pos and t > pos["entry_time"]:
            d = 1 if pos["side"] == "LONG" else -1
            fav = (bar["high"] - pos["entry"]) if d == 1 else (pos["entry"] - bar["low"])
            adv = (pos["entry"] - bar["low"]) if d == 1 else (bar["high"] - pos["entry"])
            pos["mfe"], pos["mae"] = max(pos["mfe"], fav), max(pos["mae"], adv)
            sl_hit = bar["low"] <= pos["sl"] if d == 1 else bar["high"] >= pos["sl"]
            tp_hit = pos["tp"] and (bar["high"] >= pos["tp"] if d == 1 else bar["low"] <= pos["tp"])
            if sl_hit:
                gap_px = min(bar["open"], pos["sl"]) if d == 1 else max(bar["open"], pos["sl"])
                closed.append(close_position(acc, gap_px, t, "Stop-loss" if pos["sl"] != pos["entry"] else "Break-even"))
            elif tp_hit:
                closed.append(close_position(acc, pos["tp"], t, "Take-profit"))
        # 3) drawdown suiveur (équité latente à la clôture)
        eq = acc["balance"] + unrealized(acc, bar["close"])
        acc["hwm"] = max(acc["hwm"], eq)
        if eq <= threshold(acc):
            acc["failed"] = True
        acc["last_time"] = t
    return [c for c in closed if c]


def stats(trades: list) -> dict:
    if not trades:
        return {}
    df = pd.DataFrame(trades)
    wins, losses = df[df.pnl > 0], df[df.pnl <= 0]
    gp, gl = wins.pnl.sum(), -losses.pnl.sum()
    eq = df.pnl.cumsum()
    dd = (eq - eq.cummax()).min()
    streak = cur = 0
    for v in df.pnl:
        cur = cur + 1 if v <= 0 else 0
        streak = max(streak, cur)
    return dict(n=len(df), winrate=len(wins) / len(df) * 100, net=df.pnl.sum(),
                pf=(gp / gl) if gl > 0 else float("inf"), avg_win=wins.pnl.mean() if len(wins) else 0,
                avg_loss=losses.pnl.mean() if len(losses) else 0, expectancy=df.pnl.mean(),
                avg_r=df.r.mean(), max_dd=dd, max_loss_streak=streak, best=df.pnl.max(), worst=df.pnl.min())
