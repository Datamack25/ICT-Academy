"""Agent expert : analyse technique ICT + conditions de marché (économiques, financières,
politiques, géopolitiques) + analyse de CSV. Fonctionne sans IA externe (moteur expert à règles) ;
peut enrichir ses réponses avec Claude (clé API) ou Ollama (local) si configurés."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st

from .content import FIGURES
from .ict import Analysis, describe_trend, killzone

MACRO_TICKERS = {
    "VIX (peur)": "^VIX", "Dollar DXY": "DX-Y.NYB", "Taux US 10 ans": "^TNX", "Taux US 3 mois": "^IRX",
    "Pétrole WTI": "CL=F", "Or": "GC=F", "S&P 500 fut.": "ES=F", "Nasdaq fut.": "NQ=F",
    "Semi-conducteurs SOX": "^SOX", "Bitcoin": "BTC-USD", "USD/JPY": "JPY=X",
}

THEMES = {
    "Économique": ["cpi", "inflation", "jobs", "payroll", "nfp", "unemployment", "gdp", "pce", "retail sales",
                   "ism", "pmi", "consumer", "recession", "jobless", "wages", "housing", "economy", "growth"],
    "Financier": ["fed", "powell", "rate", "yield", "treasury", "bond", "earnings", "guidance", "nvidia", "apple",
                  "microsoft", "tesla", "meta", "amazon", "alphabet", "ai ", "chip", "semiconductor", "stock",
                  "nasdaq", "rally", "selloff", "ipo", "buyback", "dollar", "liquidity", "credit", "bank"],
    "Politique": ["trump", "biden", "congress", "senate", "white house", "election", "shutdown", "tariff",
                  "tax", "budget", "debt ceiling", "regulation", "antitrust", "sec ", "policy", "administration"],
    "Géopolitique": ["china", "taiwan", "russia", "ukraine", "iran", "israel", "gaza", "middle east", "war",
                     "sanction", "opec", "export control", "missile", "conflict", "nato", "north korea", "strike",
                     "geopolit", "trade war", "red sea"],
}
POS_WORDS = ["rally", "surge", "gain", "beat", "record", "soar", "jump", "rise", "optimism", "cut rates",
             "rate cut", "cooling inflation", "strong", "upgrade", "deal", "ceasefire", "rebound", "higher"]
NEG_WORDS = ["fall", "drop", "plunge", "slump", "miss", "fear", "selloff", "sell-off", "tumble", "worry",
             "hike", "hot inflation", "war", "attack", "sanction", "tariff", "downgrade", "recession", "crash",
             "lower", "warning", "escalat", "shutdown", "sink"]

STOP_KEYS = {"swing", "high", "low", "break", "market", "structure", "open", "the", "and", "block", "range",
             "liquidity", "value", "area", "model", "price", "time", "buy", "sell", "side", "fair", "gap", "inverse",
             "balanced", "volume", "optimal", "trade", "entry", "shift", "zones", "kill", "equal", "highs", "lows",
             "maker", "points", "control", "monday", "midnight", "weekly"}

SYSTEM_PROMPT = (
    "Tu es un analyste senior en trading de futures Nasdaq (MNQ/NQ), expert de la méthodologie ICT / Smart Money "
    "(structure, liquidité, orderblocks, breakers, FVG, OTE, kill zones, Monday range, Power of 3) et de l'analyse "
    "macro (économie, banques centrales, taux, dollar, politique, géopolitique). Tu réponds en français, de façon "
    "structurée et concrète, en t'appuyant UNIQUEMENT sur les données fournies (analyse technique calculée, macro, "
    "actualités). Tu proposes des scénarios (haussier / baissier / invalidation) et des niveaux précis, mais tu "
    "rappelles qu'il s'agit d'entraînement et non d'un conseil en investissement. Pas d'invention de chiffres."
)


# ------------------------------------------------------------------- MACRO
@st.cache_data(ttl=600, show_spinner=False)
def macro_snapshot() -> pd.DataFrame:
    import yfinance as yf

    rows = []
    try:
        data = yf.download(list(MACRO_TICKERS.values()), period="3mo", interval="1d", progress=False,
                           auto_adjust=False, threads=False, group_by="ticker")
    except Exception:
        data = pd.DataFrame()
    for name, tk in MACRO_TICKERS.items():
        try:
            s = data[tk]["Close"].dropna() if isinstance(data.columns, pd.MultiIndex) else pd.Series(dtype=float)
            if len(s) < 3:
                continue
            last = float(s.iloc[-1])

            def ch(n):
                return (last / float(s.iloc[-1 - n]) - 1) * 100 if len(s) > n else np.nan

            rows.append(dict(Actif=name, Ticker=tk, Dernier=round(last, 2), **{"1 j %": round(ch(1), 2),
                        "5 j %": round(ch(5), 2), "20 j %": round(ch(20), 2)}))
        except Exception:
            continue
    return pd.DataFrame(rows)


def macro_regime(m: pd.DataFrame) -> dict:
    """Lecture risk-on / risk-off pour le Nasdaq à partir des marchés liés."""
    if m is None or m.empty:
        return dict(score=0, label="Indisponible", points=["Données macro indisponibles (Yahoo)."])
    g = m.set_index("Actif")
    pts, score = [], 0

    def val(a, col="Dernier"):
        return g.loc[a, col] if a in g.index else None

    vix = val("VIX (peur)")
    if vix is not None:
        if vix < 16:
            score += 1; pts.append(f"VIX {vix:.1f} : volatilité faible, environnement favorable aux achats sur repli.")
        elif vix > 24:
            score -= 2; pts.append(f"VIX {vix:.1f} : stress élevé — mouvements violents, réduire la taille.")
        else:
            pts.append(f"VIX {vix:.1f} : volatilité normale.")
        d5 = val("VIX (peur)", "5 j %")
        if d5 is not None and d5 > 20:
            score -= 1; pts.append(f"VIX +{d5:.0f} % sur 5 jours : montée de l'aversion au risque.")
    tnx = val("Taux US 10 ans", "5 j %")
    if tnx is not None:
        if tnx > 3:
            score -= 1; pts.append(f"Taux 10 ans en hausse ({tnx:+.1f} % sur 5 j) : pression sur les valorisations tech.")
        elif tnx < -3:
            score += 1; pts.append(f"Taux 10 ans en baisse ({tnx:+.1f} % sur 5 j) : soutien pour le Nasdaq.")
    t10, t3m = val("Taux US 10 ans"), val("Taux US 3 mois")
    if t10 is not None and t3m is not None:
        spread = t10 - t3m
        pts.append(f"Courbe 10 ans – 3 mois : {spread:+.2f} pt " + ("(inversée : signal récessif historique)." if spread < 0 else "(positive)."))
    dxy = val("Dollar DXY", "5 j %")
    if dxy is not None:
        if dxy > 1:
            score -= 1; pts.append(f"Dollar fort ({dxy:+.1f} % sur 5 j) : resserrement des conditions financières.")
        elif dxy < -1:
            score += 1; pts.append(f"Dollar faible ({dxy:+.1f} % sur 5 j) : conditions plus souples.")
    sox, nq = val("Semi-conducteurs SOX", "5 j %"), val("Nasdaq fut.", "5 j %")
    if sox is not None and nq is not None:
        if sox > nq + 1:
            score += 1; pts.append(f"Semi-conducteurs en tête ({sox:+.1f} % vs NQ {nq:+.1f} %) : leadership sain.")
        elif sox < nq - 1:
            score -= 1; pts.append(f"Semi-conducteurs à la traîne ({sox:+.1f} % vs NQ {nq:+.1f} %) : divergence à surveiller.")
    es = val("S&P 500 fut.", "1 j %")
    nq1 = val("Nasdaq fut.", "1 j %")
    if es is not None and nq1 is not None and np.sign(es) != np.sign(nq1) and abs(es - nq1) > 0.3:
        pts.append(f"Divergence NQ/ES sur la veille (NQ {nq1:+.2f} % / ES {es:+.2f} %) : possible SMT à vérifier sur les swings.")
    oil = val("Pétrole WTI", "5 j %")
    if oil is not None and oil > 6:
        score -= 1; pts.append(f"Pétrole +{oil:.0f} % sur 5 j : risque inflation / géopolitique.")
    gold = val("Or", "5 j %")
    if gold is not None and gold > 3:
        pts.append(f"Or +{gold:.1f} % sur 5 j : demande de valeur refuge.")
    jpy = val("USD/JPY", "5 j %")
    if jpy is not None and jpy < -2:
        score -= 1; pts.append(f"Yen en forte hausse (USD/JPY {jpy:+.1f} %) : risque de débouclage de carry trade.")
    label = "RISK-ON (favorable au Nasdaq)" if score >= 2 else ("RISK-OFF (défavorable au Nasdaq)" if score <= -2 else "MITIGÉ / neutre")
    return dict(score=score, label=label, points=pts)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_news(limit: int = 30) -> list:
    import yfinance as yf

    seen, out = set(), []
    for tk in ["NQ=F", "QQQ", "^IXIC", "^GSPC", "NVDA"]:
        try:
            items = yf.Ticker(tk).news or []
        except Exception:
            items = []
        for it in items:
            c = it.get("content", it)
            title = c.get("title") or it.get("title")
            if not title or title in seen:
                continue
            seen.add(title)
            url = (c.get("canonicalUrl") or {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else it.get("link")
            prov = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else it.get("publisher")
            date = c.get("pubDate") or it.get("providerPublishTime")
            if isinstance(date, (int, float)):
                date = datetime.fromtimestamp(date, tz=timezone.utc).isoformat()
            out.append(dict(title=title, url=url, source=prov or "", date=str(date or "")[:16],
                            summary=(c.get("summary") or "")[:300]))
    return out[:limit]


def classify_news(items: list) -> pd.DataFrame:
    rows = []
    for it in items:
        txt = (it["title"] + " " + it.get("summary", "")).lower()
        themes = [t for t, kws in THEMES.items() if any(k in txt for k in kws)] or ["Autre"]
        s = sum(w in txt for w in POS_WORDS) - sum(w in txt for w in NEG_WORDS)
        rows.append(dict(Date=it["date"].replace("T", " "), Thème=", ".join(themes),
                         Tonalité="Positive" if s > 0 else ("Négative" if s < 0 else "Neutre"),
                         Titre=it["title"], Source=it["source"], Lien=it["url"], _s=s))
    return pd.DataFrame(rows)


def news_digest(df: pd.DataFrame) -> list:
    if df.empty:
        return ["Aucune actualité récupérée (Yahoo peut limiter l'accès ; réessaie plus tard)."]
    pts = []
    for th in ["Économique", "Financier", "Politique", "Géopolitique"]:
        sub = df[df["Thème"].str.contains(th)]
        if sub.empty:
            pts.append(f"**{th}** : rien de saillant dans le flux récent.")
            continue
        s = sub["_s"].sum()
        tone = "plutôt positive" if s > 0 else ("plutôt négative" if s < 0 else "neutre")
        pts.append(f"**{th}** : {len(sub)} titre(s), tonalité {tone}. Ex. : « {sub.iloc[0]['Titre'][:110]} »")
    return pts


def calendar_flags(now: pd.Timestamp | None = None) -> list:
    """Rappels d'agenda récurrents (heure NY) — sans flux calendrier externe."""
    now = now or pd.Timestamp.now(tz="America/New_York")
    f = []
    wd = now.dayofweek
    if wd == 0:
        f.append("Lundi : laisse le Monday range se former, plan à bâtir après la clôture.")
    if wd == 3:
        f.append("Jeudi 8h30 NY (14h30 Paris) : inscriptions hebdo au chômage — volatilité à l'ouverture.")
    if wd == 4 and now.day <= 7:
        f.append("1er vendredi du mois : NFP 8h30 NY (14h30 Paris) — éviter d'être en position juste avant.")
    if wd == 4:
        f.append("Vendredi : fin de semaine, liquidité qui se réduit l'après-midi ; attention aux renversements.")
    if 10 <= now.day <= 15:
        f.append("Mi-mois : fenêtre habituelle du CPI / PPI (8h30 NY) — vérifie le calendrier économique.")
    f.append("Toujours vérifier : FOMC (14h NY), PCE, ISM (10h NY), résultats des méga-caps (NVDA, AAPL, MSFT…).")
    return f


# --------------------------------------------------------------- TECHNIQUE
def _fmt(v):
    return f"{v:,.2f}".replace(",", " ")


def technical_report(a: Analysis, label: str = "MNQ") -> str:
    df = a.df
    if len(df) < 20:
        return "Pas assez de bougies pour une analyse (minimum 20)."
    last = df.iloc[-1]
    t = df.index[-1]
    L = [f"### Analyse technique ICT — {label} — {t:%d/%m/%Y %H:%M} (heure NY)",
         f"**Prix** : {_fmt(last.close)} · **Session** : {killzone(t)} · **Biais composite** : **{a.bias}**"]
    htf = ", ".join(f"{k} {describe_trend(v)}" for k, v in a.htf.items())
    L.append(f"**Structure multi-UT** : {htf}.")
    ev = a.events[-3:]
    if ev:
        L.append("**Dernières ruptures** : " + " · ".join(
            f"{e['kind']} {'↑' if e['dir'] == 1 else '↓'} {_fmt(e['level'])} ({df.index[e['i']]:%d/%m %H:%M})" for e in ev))
    if a.rng:
        r = a.rng
        L.append(f"**Range de travail** : {_fmt(r['lo'])} → {_fmt(r['hi'])} · EQ {_fmt(r['eq'])} · "
                 f"position {r['position'] * 100:.0f} % → **{r['zone']}** · OTE {_fmt(r['ote_bottom'])}–{_fmt(r['ote_top'])} "
                 f"(0.705 = {_fmt(r['ote_705'])}).")
    sw = a.sweeps[-3:]
    if sw:
        L.append("**Liquidité récemment prise** : " + " · ".join(
            f"{'SSL' if s['dir'] == 1 else 'BSL'} {_fmt(s['level'])} ({df.index[s['i']]:%d/%m %H:%M})" for s in sw))
    act_ob = [o for o in a.obs[-15:] if not o["breaker"] and o["status"] != "cassé → breaker"][-3:]
    brk = [o for o in a.obs[-15:] if o["breaker"] and o["breaker_status"] != "invalidé"][-3:]
    if act_ob:
        L.append("**Orderblocks** : " + " · ".join(
            f"{'OB+' if o['dir'] == 1 else 'OB−'} {_fmt(o['bottom'])}–{_fmt(o['top'])} ({o['status']})" for o in act_ob))
    if brk:
        L.append("**Breakers actifs** : " + " · ".join(
            f"{'↓' if o['dir'] == 1 else '↑'} {_fmt(o['bottom'])}–{_fmt(o['top'])} ({o['breaker_status']})" for o in brk))
    gaps = [g for g in a.fvgs if g["status"] != "comblé"][-4:]
    if gaps:
        L.append("**FVG ouverts** : " + " · ".join(
            f"{'↑' if g['dir'] == 1 else '↓'} {_fmt(g['bottom'])}–{_fmt(g['top'])}" for g in gaps))
    if a.levels:
        L.append("**Niveaux clés** : " + " · ".join(f"{k} {_fmt(v)}" for k, v in a.levels.items()))
    if a.profile:
        L.append(f"**Profil J-1** : POC {_fmt(a.profile['poc'])} · VAH {_fmt(a.profile['vah'])} · VAL {_fmt(a.profile['val'])}.")
    # Liquidité la plus proche
    above = sorted([v for v in a.levels.values() if v > last.close])
    below = sorted([v for v in a.levels.values() if v < last.close], reverse=True)
    if above or below:
        L.append(f"**Aimants de liquidité** : au-dessus {_fmt(above[0]) if above else '—'} · en dessous {_fmt(below[0]) if below else '—'}.")
    L.append("#### Scénarios")
    if a.setups:
        for s in a.setups[:3]:
            L.append(f"- **{s['direction']}** sur {s['zone']} {_fmt(s['bottom'])}–{_fmt(s['top'])} · entrée {_fmt(s['entry'])} · "
                     f"stop {_fmt(s['stop'])} · cible {_fmt(s['target'])} · R:R {s['rr']} · qualité {s['score']}/100 "
                     f"({'sweep ✔' if s['sweep'] else 'sans sweep'}, {'MSS ✔' if s['mss'] else 'BOS'}, {'OTE ✔' if s['ote'] else 'hors OTE'})"
                     + (" — **prix dans la zone**" if s["in_zone"] else f" — à {s['distance']} pts"))
    else:
        L.append("- Aucun setup structuré : patience, attendre sweep + MSS.")
    if a.rng:
        inv = a.rng["lo"] if a.bias_score >= 0 else a.rng["hi"]
        L.append(f"- **Invalidation du biais** : clôture {'sous' if a.bias_score >= 0 else 'au-dessus de'} {_fmt(inv)}.")
    return "\n\n".join(L)


# --------------------------------------------------------------------- LLM
def secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:  # pas de fichier secrets
        return default


def llm_answer(provider: str, question: str, context: str, history: list | None = None) -> str | None:
    msgs = (history or [])[-6:] + [{"role": "user", "content": f"DONNÉES :\n{context}\n\nQUESTION : {question}"}]
    try:
        if provider == "Claude (API Anthropic)":
            key = secret("ANTHROPIC_API_KEY") or st.session_state.get("anthropic_key", "")
            if not key:
                return None
            model = secret("ANTHROPIC_MODEL", "claude-sonnet-5-5")
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=90,
                              headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                              json={"model": model, "max_tokens": 1800, "system": SYSTEM_PROMPT, "messages": msgs})
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json().get("content", []))
        if provider == "Ollama (local)":
            host = st.session_state.get("ollama_host", "http://localhost:11434")
            model = st.session_state.get("ollama_model", "mistral")
            r = requests.post(f"{host}/api/chat", timeout=180,
                              json={"model": model, "stream": False,
                                    "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + msgs})
            r.raise_for_status()
            return r.json().get("message", {}).get("content")
    except Exception as e:
        return f"⚠️ IA externe indisponible ({e}). Réponse du moteur expert intégré ci-dessous."
    return None


def expert_answer(question: str, a: Analysis | None, regime: dict | None, news_pts: list | None) -> str:
    """Moteur expert à règles : répond à partir des calculs, sans IA externe."""
    q = question.lower()
    out = []
    for cat, name, definition, ident, exe, src, _ in FIGURES:
        parts = [w.strip().lower() for w in re.split(r"[/—()·,]", name) if len(w.strip()) >= 3]
        keys = parts + [w for p_ in parts for w in p_.split() if len(w) >= 3 and w not in STOP_KEYS]
        if any(k in q for k in keys):
            out.append(f"**{name}** ({src}) — {definition}\n\n*Identifier* : {ident}\n\n*Exécuter* : {exe}")
            if len(out) >= 2:
                break
    if a is not None and len(a.df) >= 20 and any(k in q for k in ["biais", "bias", "direction", "tendance", "long", "short",
                                                                   "acheter", "vendre", "setup", "entrée", "trade", "analyse",
                                                                   "niveau", "cible", "stop", "aujourd", "maintenant", "plan"]):
        out.append(technical_report(a))
    if regime and any(k in q for k in ["macro", "vix", "taux", "fed", "dollar", "pétrole", "or ", "risk", "économ",
                                       "conditions", "marché", "inflation", "contexte"]):
        out.append("### Conditions de marché\n" + f"**Régime : {regime['label']}** (score {regime['score']:+d})\n\n" +
                   "\n".join(f"- {p}" for p in regime["points"]))
    if news_pts and any(k in q for k in ["news", "actu", "politique", "géopol", "geopol", "guerre", "élection",
                                         "tarif", "chine", "contexte", "conditions"]):
        out.append("### Actualités\n" + "\n".join(f"- {p}" for p in news_pts))
    if not out:
        parts = []
        if a is not None and len(a.df) >= 20:
            parts.append(technical_report(a))
        if regime:
            parts.append("### Conditions de marché\n" + f"**Régime : {regime['label']}**\n\n" +
                         "\n".join(f"- {p}" for p in regime["points"]))
        out = parts or ["Charge des données (Yahoo ou CSV) pour que je puisse analyser."]
    out.append("_Entraînement uniquement — pas un conseil en investissement._")
    return "\n\n".join(out)


# --------------------------------------------------------------------- CSV
TRADE_MAP = {
    "pnl": ["pnl", "p&l", "profit", "net p&l", "net pnl", "résultat", "resultat", "gain", "profit/loss", "realized pnl"],
    "side": ["side", "sens", "direction", "type", "b/s", "action"],
    "entry": ["entry", "entry price", "prix entrée", "entrée", "buy price", "open price", "avg entry", "buyprice"],
    "exit": ["exit", "exit price", "prix sortie", "sortie", "sell price", "close price", "avg exit", "sellprice"],
    "qty": ["qty", "quantity", "quantité", "contracts", "size", "volume", "contrats"],
    "time": ["entry time", "open time", "date", "time", "boughttimestamp", "date entrée", "datetime", "entered at"],
}


def analyze_trades_csv(df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    cols = {re.sub(r"\s+", " ", str(c).strip().lower()): c for c in df.columns}
    m = {}
    for k, al in TRADE_MAP.items():
        for a_ in al:
            if a_ in cols:
                m[k] = cols[a_]
                break
    if "pnl" not in m:
        if "entry" in m and "exit" in m:
            side = df[m["side"]].astype(str).str.lower() if "side" in m else pd.Series(["long"] * len(df))
            sign = np.where(side.str.contains("short|sell|vente"), -1, 1)
            qty = pd.to_numeric(df[m["qty"]], errors="coerce").fillna(1) if "qty" in m else 1
            df["_pnl"] = (pd.to_numeric(df[m["exit"]], errors="coerce") - pd.to_numeric(df[m["entry"]], errors="coerce")) * sign * qty * 2.0
            m["pnl"] = "_pnl"
        else:
            return "Colonne de résultat (PnL) introuvable : ajoute une colonne « pnl » ou « entry/exit ».", pd.DataFrame()
    pnl = pd.to_numeric(df[m["pnl"]].astype(str).str.replace(r"[$€\s]", "", regex=True).str.replace(",", "."), errors="coerce")
    pnl = pnl.dropna()
    if pnl.empty:
        return "PnL illisible.", pd.DataFrame()
    w, l_ = pnl[pnl > 0], pnl[pnl <= 0]
    pf = w.sum() / -l_.sum() if l_.sum() < 0 else float("inf")
    eq = pnl.cumsum()
    dd = (eq - eq.cummax()).min()
    L = ["### Analyse de ton journal de trades (CSV)",
         f"- **Trades** : {len(pnl)} · **Net** : {pnl.sum():,.2f} $ · **Win rate** : {len(w) / len(pnl) * 100:.1f} %",
         f"- **Profit factor** : {pf:.2f} · **Gain moyen** : {w.mean() if len(w) else 0:,.2f} $ · **Perte moyenne** : {l_.mean() if len(l_) else 0:,.2f} $",
         f"- **Espérance / trade** : {pnl.mean():,.2f} $ · **Drawdown max (réalisé)** : {dd:,.2f} $"]
    payoff = (w.mean() / -l_.mean()) if len(w) and len(l_) and l_.mean() < 0 else None
    if payoff:
        be = 1 / (1 + payoff) * 100
        L.append(f"- **Ratio gain/perte** : {payoff:.2f} → win rate d'équilibre {be:.1f} %.")
    advice = []
    if payoff and payoff < 1:
        advice.append("Tes pertes moyennes dépassent tes gains moyens : vise des cibles sur la liquidité opposée (≥ 2R) et coupe à l'invalidation.")
    if len(l_) and l_.min() < 3 * l_.mean():
        advice.append(f"Une perte extrême ({l_.min():,.2f} $) pèse lourd : vérifie que chaque trade a un stop fixé avant l'entrée.")
    streak = cur = 0
    for v in pnl:
        cur = cur + 1 if v <= 0 else 0
        streak = max(streak, cur)
    if streak >= 4:
        advice.append(f"{streak} pertes d'affilée au maximum : instaure une règle d'arrêt (ex. 2 pertes = fin de session).")
    by = pd.DataFrame()
    if "time" in m:
        t = pd.to_datetime(df.loc[pnl.index, m["time"]], errors="coerce")
        if t.notna().mean() > 0.7:
            tmp = pd.DataFrame({"pnl": pnl, "heure": t.dt.hour, "jour": t.dt.day_name()})
            by = tmp.groupby("heure")["pnl"].agg(["count", "sum", "mean"]).round(2)
            worst = by["sum"].idxmin()
            best = by["sum"].idxmax()
            advice.append(f"Heure la plus rentable : {best}h · la plus coûteuse : {worst}h (heure du fichier). Concentre-toi sur tes kill zones gagnantes.")
            dj = tmp.groupby("jour")["pnl"].sum()
            advice.append("Résultat par jour : " + ", ".join(f"{k} {v:,.0f} $" for k, v in dj.items()))
    if advice:
        L.append("#### Recommandations du coach")
        L += [f"- {x}" for x in advice]
    return "\n".join(L), by
