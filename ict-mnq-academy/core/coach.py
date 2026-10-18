"""Coach : photographie le contexte ICT à l'entrée puis note chaque trade selon la méthode du cours."""
from __future__ import annotations

from collections import Counter

import pandas as pd

from .ict import Analysis, killzone

GOOD_KZ = {"London KZ", "NY AM KZ", "Silver Bullet AM", "NY PM KZ"}


def entry_context(a: Analysis, side: str, price: float, time: pd.Timestamp) -> dict:
    """Ce que le moteur voit objectivement au moment de l'entrée (pour comparer au plan déclaré)."""
    d = 1 if side == "LONG" else -1
    N = len(a.df)
    ctx = dict(killzone=killzone(time), bias=a.bias, bias_score=a.bias_score,
               htf=a.htf.copy(), zone=a.rng["zone"] if a.rng else "n/d",
               range_pos=round(a.rng["position"], 2) if a.rng else None)
    recent_sw = [s for s in a.sweeps if s["i"] >= N - 40 and s["dir"] == d]
    ctx["sweep_recent"] = bool(recent_sw)
    recent_ev = [e for e in a.events if e["i"] >= N - 40]
    ctx["mss_in_dir"] = any(e["dir"] == d and e["kind"] == "MSS" for e in recent_ev)
    ctx["bos_in_dir"] = any(e["dir"] == d for e in recent_ev)
    ctx["last_structure"] = (recent_ev[-1]["kind"] + (" ↑" if recent_ev[-1]["dir"] == 1 else " ↓")) if recent_ev else "aucune"
    zones = []
    for ob in a.obs[-25:]:
        if ob["bottom"] - 2 <= price <= ob["top"] + 2:
            if ob["breaker"] and ob["breaker_status"] != "invalidé" and -ob["dir"] == d:
                zones.append("Breaker")
            elif not ob["breaker"] and ob["dir"] == d:
                zones.append("Orderblock")
    for g in a.fvgs[-40:]:
        if g["status"] != "comblé" and g["dir"] == d and g["bottom"] - 1 <= price <= g["top"] + 1:
            zones.append("FVG")
    if a.rng and a.rng["ote_bottom"] <= price <= a.rng["ote_top"]:
        zones.append("OTE")
    ctx["pd_zones"] = sorted(set(zones))
    if a.rng and 0 <= a.rng["position"] <= 1:
        ctx["premium_discount_ok"] = (a.rng["position"] < 0.5) if d == 1 else (a.rng["position"] > 0.5)
        ctx["at_eq"] = 0.45 <= a.rng["position"] <= 0.55
    else:
        ctx["premium_discount_ok"], ctx["at_eq"] = None, False
    ctx["weekday"] = time.day_name()
    return ctx


def evaluate_trade(t: dict, start_balance: float) -> dict:
    """Note /100 + points forts + erreurs, d'après la checklist Warren / ICT."""
    c, p = t.get("context", {}), t.get("plan", {})
    d = 1 if t["side"] == "LONG" else -1
    score, good, bad, tips = 0, [], [], []

    # 1. Biais / structure (20)
    if c.get("bias_score") == d:
        score += 20; good.append(f"Trade dans le sens du biais ({c.get('bias')}).")
    elif c.get("bias_score") == 0:
        score += 8; tips.append("Biais neutre : en range, on ne joue que les extrêmes (range high / range low), jamais l'EQ.")
    else:
        bad.append(f"Contre le biais multi-UT ({c.get('bias')}). Le cours : « trader la tendance », attendre un MSS avant de se retourner.")
    # 2. Liquidité prise (15)
    if c.get("sweep_recent"):
        score += 15; good.append("Liquidité balayée juste avant (SFP) — condition de la méthode C.")
    else:
        bad.append("Aucun sweep de liquidité récent : « avant que le smart money manipule, il faut de la liquidité à collecter ».")
    # 3. MSS / MSB (15)
    if c.get("mss_in_dir"):
        score += 15; good.append("Changement de structure (MSS) confirmé dans ton sens.")
    elif c.get("bos_in_dir"):
        score += 9; good.append("BOS dans ton sens (continuation).")
    else:
        bad.append("Pas de rupture de structure dans ton sens : « ne prenez pas de position sur un breaker sans nouveau plus haut/plus bas validé ».")
    # 4. Zone d'entrée (15)
    z = c.get("pd_zones", [])
    if z:
        score += 15 if len(z) >= 2 else 11
        good.append("Entrée dans une zone d'intérêt : " + ", ".join(z) + ".")
    else:
        bad.append("Entrée hors OB / breaker / FVG / OTE : entrée « au milieu de nulle part ».")
    if c.get("at_eq"):
        score -= 5; bad.append("Entrée à l'EQ du range : zone à éviter (ni acheteurs ni vendeurs en contrôle).")
    if c.get("premium_discount_ok") is True:
        score += 5; good.append("Achat en discount / vente en premium.")
    elif c.get("premium_discount_ok") is False:
        bad.append("Achat en premium ou vente en discount : mauvais emplacement dans le range.")
    # 5. Timing (10)
    if c.get("killzone") in GOOD_KZ:
        score += 10; good.append(f"Exécuté dans une kill zone ({c.get('killzone')}).")
    else:
        bad.append(f"Hors kill zone ({c.get('killzone')}) : liquidité et intention institutionnelle plus faibles.")
    if c.get("weekday") == "Monday":
        tips.append("Lundi : le cours recommande d'attendre la clôture du lundi pour bâtir le gameplan (Monday range).")
    # 6. Gestion du risque (20)
    risk_pct = t.get("risk_usd", 0) / start_balance * 100 if start_balance else 0
    rr_plan = abs(t["tp"] - t["entry"]) / abs(t["entry"] - t["sl"]) if t.get("tp") and t["entry"] != t["sl"] else None
    if risk_pct <= 1.5:
        score += 10; good.append(f"Risque maîtrisé : {risk_pct:.2f} % du compte (cours : 1–1,5 % intraday).")
    elif risk_pct <= 2:
        score += 5; tips.append(f"Risque {risk_pct:.2f} % : réservé aux setups swing selon le cours.")
    else:
        bad.append(f"Risque trop élevé : {risk_pct:.2f} % du compte (> 2 %).")
    if rr_plan is not None and rr_plan >= 2:
        score += 10; good.append(f"R:R planifié {rr_plan:.1f}.")
    elif rr_plan is not None:
        score += 3; bad.append(f"R:R planifié faible ({rr_plan:.1f}). Vise ≥ 2R en ciblant la liquidité opposée.")
    else:
        bad.append("Pas d'objectif défini : cibler les plus bas/hauts non exploités (liquidité non tapée).")
    # Cohérence plan déclaré vs réalité
    if p.get("sweep") and not c.get("sweep_recent"):
        tips.append("Tu as déclaré un sweep, mais le moteur n'en détecte pas de récent : revois ta lecture des swings.")
    if p.get("mss") and not (c.get("mss_in_dir") or c.get("bos_in_dir")):
        tips.append("Tu as déclaré un MSS, non confirmé à la clôture : une mèche ne suffit pas, il faut une clôture au-delà.")
    # Exécution
    if t["reason"] == "Manuel" and t["r"] < 0 and t.get("mae", 0) < abs(t["entry"] - t["sl"]) * 0.5:
        tips.append("Sortie manuelle en perte avant l'invalidation : laisse le plan travailler ou ne prends pas le trade.")
    if t["mfe"] >= abs(t["entry"] - t["sl"]) and t["r"] <= 0:
        tips.append("Le trade a atteint +1R puis est revenu : applique la gestion du cours (prendre 1/3 à 1R, stop à BE).")
    score = max(0, min(100, score))
    if not c.get("sweep_recent"):
        score = min(score, 79)  # méthode C : sans prise de liquidité, pas de note A
    grade = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"
    return dict(score=score, grade=grade, good=good, bad=bad, tips=tips, risk_pct=round(risk_pct, 2),
                rr_plan=round(rr_plan, 2) if rr_plan else None)


def journal_insights(trades: list, start_balance: float) -> dict:
    if not trades:
        return {}
    rows, mistakes = [], Counter()
    for t in trades:
        ev = evaluate_trade(t, start_balance)
        for b in ev["bad"]:
            mistakes[b.split(":")[0].split("(")[0].strip()] += 1
        c = t.get("context", {})
        rows.append(dict(id=t["id"], date=t["entry_time"], side=t["side"], setup=t.get("plan", {}).get("setup", "n/d"),
                         killzone=c.get("killzone", "n/d"), score=ev["score"], grade=ev["grade"], r=t["r"], pnl=t["pnl"]))
    df = pd.DataFrame(rows)
    by_setup = df.groupby("setup").agg(trades=("pnl", "size"), pnl=("pnl", "sum"), r_moy=("r", "mean"),
                                       winrate=("pnl", lambda s: (s > 0).mean() * 100)).round(2)
    by_kz = df.groupby("killzone").agg(trades=("pnl", "size"), pnl=("pnl", "sum"), r_moy=("r", "mean")).round(2)
    hi, lo = df[df.score >= 65], df[df.score < 65]
    disc = dict(hi_n=len(hi), hi_r=hi.r.mean() if len(hi) else 0, lo_n=len(lo), lo_r=lo.r.mean() if len(lo) else 0)
    return dict(table=df, by_setup=by_setup, by_kz=by_kz, mistakes=mistakes.most_common(6), discipline=disc,
                avg_score=df.score.mean())
