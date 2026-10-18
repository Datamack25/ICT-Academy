"""ICT MNQ Academy — plateforme d'entraînement au trading ICT sur le Nasdaq (MNQ).
Streamlit + HTML · données Yahoo Finance · compte fictif · coach · agent expert."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import agent, coach, paper
from core.charts import add_mmm_layer, bar_chart, equity_chart, ict_chart, mmpd_chart
from core.mmm import analyze_mmm, map_table, mmpd_zone, momentum_phase
from core.pages_bt import render_backtests, render_scripts
from core.pages_desk import render_desk
from core.content import CHEATSHEET_HTML, FIGURES, QUIZ, STUDY_STEPS
from core.data import (NY_TZ, PERIOD_CHOICES, csv_to_ohlc, demo_data, detect_csv_kind, load_market,
                       load_yahoo, read_csv_any)
from core.ict import analyze, describe_trend, killzone
from core.style import apply_theme, card, pill

st.set_page_config(page_title="ICT MNQ Academy", page_icon="📈", layout="wide")
apply_theme()

PAGES = ["🏠 Accueil", "🖥️ Edge Desk (live)", "🎯 Simulateur MNQ", "📒 Journal & Coach", "📊 Backtests & Verdicts", "🤖 Agent expert",
         "📚 Figures ICT", "🧭 Méthode d'étude", "📜 Scripts TradingView", "⚙️ Mode d'emploi"]
SETUPS = ["Méthode C — sweep + MSS + OB/OTE", "Breaker strategy", "Méthode A — OB courant",
          "Méthode B — OB + OTE 0.705", "FVG (ICT 2022 / Silver Bullet)", "Range / déviation + MSB",
          "Monday range", "Scalp S/D (sweep LTF dans zone HTF)", "Autre / hors plan"]


# ------------------------------------------------------------------ helpers
def show_fig(fig, key=None):
    try:
        st.plotly_chart(fig, width="stretch", key=key, config={"scrollZoom": True, "displaylogo": False})
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key, config={"scrollZoom": True, "displaylogo": False})


def show_df(df, **kw):
    try:
        st.dataframe(df, width="stretch", **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, **kw)


def init_state():
    ss = st.session_state
    ss.setdefault("page", PAGES[0])
    ss.setdefault("acc", paper.new_account())
    ss.setdefault("replay_idx", None)
    ss.setdefault("data_sig", None)
    ss.setdefault("chat", [])
    ss.setdefault("last_feedback", None)
    ss.setdefault("mode", "Replay (entraînement)")


def _json_default(o):
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def export_session() -> str:
    acc = dict(st.session_state.acc)
    return json.dumps(dict(version=1, account=acc), default=_json_default, ensure_ascii=False, indent=1)


def import_session(raw: bytes):
    d = json.loads(raw.decode("utf-8"))
    acc = d["account"]
    for t in acc.get("trades", []):
        t["entry_time"], t["exit_time"] = pd.Timestamp(t["entry_time"]), pd.Timestamp(t["exit_time"])
    if acc.get("position"):
        acc["position"]["entry_time"] = pd.Timestamp(acc["position"]["entry_time"])
    for p in acc.get("pending", []):
        p["time"] = pd.Timestamp(p["time"])
    acc["last_time"] = None
    acc.setdefault("log", [])
    st.session_state.acc = acc


init_state()
ss = st.session_state
_PAGE_QP = {"desk": 1, "simulateur": 2, "journal": 3, "backtests": 4, "agent": 5, "figures": 6, "methode": 7, "scripts": 8, "aide": 9}
if "qp_done" not in ss:
    ss.qp_done = True
    _pq = st.query_params.get("page", "")
    if _pq in _PAGE_QP:
        ss.page = PAGES[_PAGE_QP[_pq]]
        ss["nav"] = ss.page

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("## 📈 ICT MNQ Academy")
    if ss.get("nav") not in PAGES:
        ss["nav"] = ss.page if ss.page in PAGES else PAGES[0]
    ss.page = st.radio("Navigation", PAGES, key="nav", label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### Données")
    _src_opts = ["Yahoo Finance", "Fichier CSV", "Démo hors-ligne"]
    _qp = st.query_params.get("source", "")
    source = st.selectbox("Source", _src_opts, key="source", index=2 if _qp == "demo" else (1 if _qp == "csv" else 0))
    csv_file = None
    if source == "Yahoo Finance":
        ticker = st.selectbox("Contrat", ["MNQ=F", "NQ=F", "QQQ", "^NDX"], key="ticker",
                              help="MNQ=F et NQ=F ont la même cotation ; le P&L est toujours calculé en MNQ (2 $/pt).")
        interval = st.selectbox("Unité de temps", list(PERIOD_CHOICES.keys()), index=2, key="interval")
        period = st.selectbox("Historique", PERIOD_CHOICES[interval], index=len(PERIOD_CHOICES[interval]) - 1, key="period")
    elif source == "Fichier CSV":
        csv_file = st.file_uploader("CSV OHLC (TradingView, NinjaTrader, Excel…)", type=["csv", "txt"], key="csv_ohlc")
        tz_csv = st.selectbox("Fuseau des dates du CSV", [NY_TZ, "Europe/Paris", "UTC", "America/Chicago"], key="tz_csv")
    else:
        interval = st.selectbox("Unité de temps (démo)", ["5m", "15m", "1h"], index=1, key="demo_iv")
    st.markdown("### Moteur ICT")
    swing_n = st.slider("Sensibilité des swings (bougies de chaque côté)", 1, 6, 2, key="swing_n")
    fvg_min = st.number_input("Taille mini d'un FVG (points)", 0.5, 50.0, 4.0, 0.5, key="fvg_min")
    vue = st.radio("Lecture du graphique", ["ICT", "MMM (order flow)", "ICT + MMM (allégé)"], index=2, key="vue",
                   help="ICT = cours Warren (structure, OB, breakers, FVG, OTE). MMM = boussole, GMC, escalier T#, boîtes, MMPD.")
    with st.expander("Affichage du graphique"):
        show = {k: st.checkbox(lbl, True, key=f"show_{k}") for k, lbl in [
            ("structure", "Structure BOS / MSS"), ("ob", "Orderblocks"), ("breaker", "Breakers"),
            ("fvg", "FVG"), ("sweeps", "Sweeps de liquidité"), ("range", "Range / EQ / OTE"),
            ("levels", "Niveaux clés (PDH, Monday…)"), ("poc", "POC J-1"), ("sessions", "Sessions")]}
        st.markdown("**Couche MMM (order flow)**")
        show.update({k: st.checkbox(lbl, dflt, key=f"show_{k}") for k, lbl, dflt in [
            ("mmm_stairs", "Escalier T# · CDL/LD · niveau protégé", True), ("mmm_boxes", "Boîtes de session BZ + balance control", True),
            ("mmm_gmc", "Lignes GMC", True), ("mmm_pb", "Zone de pullback P–MP / BAL–MD", True),
            ("mmm_candles", "Boussole des bougies (BC+, AFs…)", False), ("mmpd", "Oscillateur MMPD sous le graphique", True)]})
    ICT_KEYS = ["structure", "ob", "breaker", "fvg", "sweeps", "range", "levels", "poc"]
    MMM_KEYS = ["mmm_stairs", "mmm_boxes", "mmm_gmc", "mmm_pb", "mmm_candles", "mmpd"]
    if vue == "ICT":
        show.update({k: False for k in MMM_KEYS})
    elif vue.startswith("MMM"):
        show.update({k: False for k in ICT_KEYS if k not in ("range",)})
        show["range"] = False
    else:
        show["lite"] = True
        show["levels"] = False
    window = st.slider("Bougies affichées", 80, 600, 220, 20, key="window")
    with st.expander("Compte fictif"):
        sb = st.number_input("Capital de départ ($)", 1000.0, 1_000_000.0, float(ss.acc["start"]), 1000.0)
        dd = st.number_input("Drawdown suiveur ($, type Apex)", 0.0, 100_000.0, float(ss.acc["trailing_dd"]), 250.0)
        com = st.number_input("Commission par contrat et par côté ($)", 0.0, 10.0, float(ss.acc["commission"]), 0.01)
        mx = st.number_input("Contrats max", 1, 100, int(ss.acc["max_contracts"]), 1)
        if st.button("🔄 Réinitialiser le compte"):
            ss.acc = paper.new_account(sb, dd, com, int(mx))
            ss.last_feedback = None
            st.rerun()
        st.download_button("💾 Sauvegarder ma session (JSON)", export_session(), "ict_mnq_session.json", "application/json")
        up = st.file_uploader("Recharger une session", type=["json"], key="sess_up")
        if up is not None and st.button("Importer la session"):
            import_session(up.getvalue())
            st.success("Session rechargée.")
            st.rerun()

# ------------------------------------------------------------------ data load
msg, src_label = "", ""
if source == "Yahoo Finance":
    with st.spinner("Téléchargement Yahoo Finance…"):
        df_full, used, msg = load_market(ticker, interval, period)
    src_label = f"Yahoo · {used or ticker} · {interval}"
    sig = ("yahoo", ticker, interval, period)
elif source == "Fichier CSV":
    if csv_file is not None:
        try:
            df_full = csv_to_ohlc(read_csv_any(csv_file), tz_csv)
            msg = "" if not df_full.empty else "Le CSV ne contient pas de colonnes open/high/low/close exploitables."
        except Exception as e:
            df_full, msg = pd.DataFrame(), f"CSV illisible : {e}"
        src_label = f"CSV · {csv_file.name}"
        sig = ("csv", csv_file.name, csv_file.size)
    else:
        df_full, sig = pd.DataFrame(), ("csv", None)
        msg = "Charge un CSV OHLC dans la barre latérale."
else:
    iv = {"5m": 5, "15m": 15, "1h": 60}[interval]
    df_full = demo_data(3000, iv)
    src_label, sig = f"Démo synthétique · {interval}", ("demo", interval)
    msg = "Mode démo : prix synthétiques (pour tester sans connexion). Passe sur Yahoo Finance pour le vrai MNQ."

if sig != ss.data_sig:
    acc = ss.acc
    if acc["position"] and len(df_full):
        paper.close_position(acc, float(df_full["close"].iloc[-1]), df_full.index[-1], "Changement de données")
    acc["pending"], acc["last_time"] = [], None
    ss.replay_idx = None
    ss.data_sig = sig

HAS_DATA = not df_full.empty and len(df_full) >= 30


def visible_df() -> pd.DataFrame:
    if not HAS_DATA:
        return df_full
    if ss.mode.startswith("Replay"):
        if ss.replay_idx is None:
            ss.replay_idx = max(60, int(len(df_full) * 0.5))
        ss.replay_idx = int(min(max(ss.replay_idx, 40), len(df_full)))
        return df_full.iloc[:ss.replay_idx]
    return df_full


def current_analysis():
    v = visible_df()
    lookback = 3000
    return analyze(v.iloc[-lookback:], st.session_state.swing_n, st.session_state.fvg_min), v


def coach_panel(a):
    """Checklist guidée en direct : ce que l'étudiant doit regarder maintenant."""
    if len(a.df) < 20:
        return
    t = a.df.index[-1]
    N = len(a.df)
    kz = killzone(t)
    sw = [s for s in a.sweeps if s["i"] >= N - 40]
    ev = [e for e in a.events if e["i"] >= N - 40]
    items = [
        ("Biais multi-UT", a.bias_score != 0, f"{a.bias} — " + ", ".join(f"{k} {describe_trend(v)}" for k, v in a.htf.items())),
        ("Liquidité prise récemment", bool(sw), ("Dernier : " + ("SSL" if sw[-1]["dir"] == 1 else "BSL") + f" {sw[-1]['level']:.2f}") if sw else "Aucun sweep sur 40 bougies : attendre."),
        ("Rupture de structure", bool(ev), (ev[-1]["kind"] + (" haussier" if ev[-1]["dir"] == 1 else " baissier")) if ev else "Pas de MSB/BOS récent."),
        ("Emplacement dans le range", bool(a.rng) and a.rng["zone"] in ("PREMIUM", "DISCOUNT"), a.rng["zone"] if a.rng else "n/d"),
        ("Kill zone", kz in coach.GOOD_KZ, kz),
        ("Setup prêt", any(s["in_zone"] for s in a.setups), (a.setups[0]["direction"] + " " + a.setups[0]["zone"]) if a.setups else "Aucun"),
    ]
    html = "".join(f"<div>{'✅' if ok else '⬜'} <b>{lab}</b> — {txt}</div>" for lab, ok, txt in items)
    n_ok = sum(ok for _, ok, _ in items)
    missing = [lab for lab, ok, _ in items if not ok]
    advice = ("Toutes les conditions sont réunies : prépare ton ordre (entrée, stop au-delà de la zone, cible liquidité opposée)."
              if n_ok == 6 else f"Presque prêt — il manque : {', '.join(missing)}. Attends cette condition ou réduis la taille."
              if n_ok == 5 else "Conditions partielles : observe, marque tes niveaux, ne force pas l'entrée."
              if n_ok >= 3 else "Marché sans setup : avance les bougies et note ce que fait le prix autour des niveaux.")
    card(f"🧭 Coach en direct — {n_ok}/6 conditions", html + f"<div style='margin-top:8px'><i>{advice}</i></div>")


def mmm_panel(m):
    """Lecture order flow MMM de la dernière bougie clôturée."""
    if m is None or m.types is None:
        return
    last = m.types[-1]
    lc, lo = m.mmpd27[0][-1], m.mmpd27[1][-1]
    z = mmpd_zone(lc, lo)
    st_ = m.steps[-1] if m.steps else None
    bx = m.boxes[-1] if m.boxes else None
    al = m.align
    html = (f"<div>🕯️ <b>Dernière bougie</b> : {last} · <b>bougie journalière d'hier</b> : "
            f"{'haussière' if m.daily_dir == 1 else 'baissière' if m.daily_dir == -1 else 'neutre'}</div>"
            f"<div>🪜 <b>Escalier</b> : " + (f"{st_['label']} · T{st_['T']} {'haussier' if st_['dir'] == 1 else 'baissier'}"
                                              f"{' ★ zone Z (T3+)' if st_['T'] >= 3 else ''} · niveau protégé {st_['r_level']:.2f}" if st_ else "—") + "</div>"
            f"<div>📦 <b>Boîte</b> : " + (f"{bx['name']} {bx['kind']} {bx['bot']:.2f}–{bx['top']:.2f} · "
                                         f"{'acheteurs en contrôle (tiers haut)' if bx['control'] == 1 else 'vendeurs en contrôle (tiers bas)' if bx['control'] == -1 else 'milieu de boîte'}"
                                         f"{' · cassée ' + ('▲' if bx['brk_dir'] == 1 else '▼') if bx['brk_i'] else ''}" if bx else "—") + "</div>"
            f"<div>📈 <b>MMPD 27</b> : {lc:.0f} / {lo:.0f} → <b>{z}</b> "
            f"({'longs autorisés' if z == 'XP' else 'shorts autorisés' if z == 'XD' else 'pas de gate de momentum'})</div>"
            f"<div>🌪️ <b>Alignement</b> : " + " · ".join(f"{k} {v}" for k, v in al.get("tf", {}).items()) +
            f" → {al.get('count', 0)} UT {'▲' if al.get('dir') == 1 else '▼' if al.get('dir') == -1 else ''} (doc : {al.get('prob_doc', '—')})</div>")
    card("🧭 Lecture order flow (MMM)", html)
    with st.expander("🗺️ MAP — lecture live complète (structure, contrôle, bougie, MMPD, GMC, boîte, session, alignement)"):
        show_df(pd.DataFrame(map_table(m), columns=["Élément", "Lecture"]), hide_index=True)


# ====================================================================== PAGES
if ss.page == "🏠 Accueil":
    st.title("ICT MNQ Academy")
    st.markdown("Plateforme d'entraînement au trading **ICT / Smart Money** sur le **Micro Nasdaq (MNQ)** : "
                "graphique réel Yahoo Finance, **compte fictif**, mode **replay** bougie par bougie, **coach** qui note "
                "chaque trade selon la méthode du cours Warren, et **agent expert** technique + macro.")
    c1, c2, c3, c4 = st.columns(4)
    acc = ss.acc
    st_ = paper.stats(acc["trades"])
    c1.metric("Capital fictif", f"{acc['balance']:,.2f} $", f"{acc['balance'] - acc['start']:+,.2f} $")
    c2.metric("Trades", st_.get("n", 0))
    c3.metric("Win rate", f"{st_.get('winrate', 0):.1f} %")
    c4.metric("Seuil drawdown", f"{paper.threshold(acc):,.0f} $")
    if msg:
        st.info(msg)
    if HAS_DATA:
        a, v = current_analysis()
        st.markdown(f"**{src_label}** · dernière bougie visible : {v.index[-1]:%d/%m/%Y %H:%M} (NY) · "
                    f"biais {pill(a.bias, 'green' if a.bias_score == 1 else 'red' if a.bias_score == -1 else 'orange')}",
                    unsafe_allow_html=True)
        show_fig(ict_chart(a, window=min(window, 200), show=show, title="Aperçu du marché"), key="home_chart")
    st.markdown("### Par où commencer ?")
    cols = st.columns(3)
    with cols[0]:
        card("1 · Apprendre", "Lis les <b>Figures ICT</b> puis la <b>Méthode d'étude</b> (10 étapes du cours) et fais le quiz.")
    with cols[1]:
        card("2 · S'entraîner", "Dans le <b>Simulateur</b>, mode Replay : avance bougie par bougie, suis le coach en direct, prends tes trades avec stop et cible.")
    with cols[2]:
        card("3 · Progresser", "Le <b>Journal & Coach</b> note chaque trade (A à D) et repère tes erreurs récurrentes. L'<b>Agent</b> analyse marché, macro et tes CSV.")

# ---------------------------------------------------------------- SIMULATEUR
elif ss.page == "🎯 Simulateur MNQ":
    st.title("🎯 Simulateur MNQ — compte fictif")
    if msg:
        st.info(msg)
    if not HAS_DATA:
        st.warning("Pas de données exploitables. Essaie une autre unité de temps, le mode démo ou un CSV.")
        st.stop()
    mode = st.radio("Mode", ["Replay (entraînement)", "Live différé (Yahoo ~10-15 min)"], horizontal=True,
                    index=0 if ss.mode.startswith("Replay") else 1, key="mode_radio")
    if mode != ss.mode:
        acc = ss.acc
        if acc["position"]:
            vv = visible_df()
            paper.close_position(acc, float(vv["close"].iloc[-1]), vv.index[-1], "Changement de mode")
        acc["pending"], acc["last_time"] = [], None
        ss.mode = mode
        st.rerun()

    acc = ss.acc
    visible_df()  # initialise la position du replay si besoin
    if ss.mode.startswith("Replay"):
        rc = st.columns([1.3, 1, 1, 1, 1, 1, 1.3])
        dates = sorted(set(df_full.index.date))
        start_d = rc[0].selectbox("Démarrer le replay au", dates[1:-1] if len(dates) > 3 else dates,
                                  index=max(0, len(dates) // 2 - 1), key="replay_start", format_func=lambda d: d.strftime("%a %d/%m/%Y"))
        if rc[0].button("⏮ Positionner", help="Recommence le replay à cette date (le futur est masqué)."):
            if acc["position"]:
                vv = visible_df()
                paper.close_position(acc, float(vv["close"].iloc[-1]), vv.index[-1], "Repositionnement replay")
            acc["pending"], acc["last_time"] = [], None
            ss.replay_idx = int(np.searchsorted(df_full.index.date, start_d))
            st.rerun()
        step = {"▶ +1": 1, "⏩ +5": 5, "⏭ +20": 20}
        for col, (lab, n) in zip(rc[1:4], step.items()):
            if col.button(lab):
                ss.replay_idx += n
        if rc[4].button("☀ +1 jour"):
            cur = df_full.index[min(ss.replay_idx, len(df_full) - 1)]
            ss.replay_idx = int(np.searchsorted(df_full.index, cur + pd.Timedelta(days=1)))
        if rc[5].button("🕘 NY open"):
            cur = df_full.index[min(ss.replay_idx, len(df_full) - 1)]
            nxt = df_full.index[(df_full.index > cur) & (df_full.index.hour == 9) & (df_full.index.minute >= 30)]
            if len(nxt):
                ss.replay_idx = int(np.searchsorted(df_full.index, nxt[0])) + 1
        if rc[6].button("⏩ Jusqu'à sortie", help="Avance jusqu'à ce que la position (ou l'ordre limite) soit résolue."):
            k = ss.replay_idx
            while k < len(df_full) and (acc["position"] or acc["pending"]) and k - ss.replay_idx < 2000:
                k += 1
                for t_ in paper.process_bars(acc, df_full.iloc[:k]):
                    ss.last_feedback = (t_, coach.evaluate_trade(t_, acc["start"]))
            ss.replay_idx = k
        ss.replay_idx = min(ss.replay_idx, len(df_full))
        if ss.replay_idx >= len(df_full):
            st.warning("Fin des données : repositionne le replay plus tôt ou charge plus d'historique.")
    else:
        if st.button("🔄 Rafraîchir les cotations"):
            load_yahoo.clear()
            st.rerun()

    a, vis = current_analysis()
    closed = paper.process_bars(acc, vis)
    for t in closed:
        ev = coach.evaluate_trade(t, acc["start"])
        ss.last_feedback = (t, ev)
        st.toast(f"Trade clôturé ({t['reason']}) : {t['pnl']:+.2f} $ · note {ev['grade']}")
    last = vis.iloc[-1]
    price = float(last["close"])
    upnl = paper.unrealized(acc, price)
    m = st.columns(6)
    m[0].metric("Prix MNQ", f"{price:,.2f}", f"{price - float(vis['close'].iloc[-2]):+.2f}")
    m[1].metric("Solde", f"{acc['balance']:,.0f} $")
    m[2].metric("P&L latent", f"{upnl:+,.0f} $")
    m[3].metric("Équité", f"{acc['balance'] + upnl:,.0f} $")
    m[4].metric("Seuil liquidation", f"{paper.threshold(acc):,.0f} $")
    m[5].metric(f"NY · {vis.index[-1]:%a %d/%m}", f"{vis.index[-1]:%H:%M}", killzone(vis.index[-1]), delta_color="off")
    if acc["failed"]:
        st.error("⚠️ Le drawdown suiveur a été touché : en conditions réelles, ce compte d'évaluation serait perdu. "
                 "Analyse tes trades dans le Journal puis réinitialise le compte.")

    left, right = st.columns([3.1, 1.25])
    with left:
        m = analyze_mmm(a.df, ss.swing_n)
        fig = ict_chart(a, window=window, show=show, trades=acc["trades"][-15:], position=acc["position"],
                        pending=acc["pending"], title=f"{src_label} — {ss.mode.split(' ')[0]}")
        show_fig(add_mmm_layer(fig, m, window, show), key="sim_chart")
        if show.get("mmpd", True) and m.mmpd27 is not None:
            show_fig(mmpd_chart(m, window), key="sim_mmpd")
        coach_panel(a)
        mmm_panel(m)
        if a.setups:
            with st.expander(f"📌 Setups détectés par le moteur ({len(a.setups)}) — à valider par toi-même"):
                show_df(pd.DataFrame([{k: s[k] for k in ["direction", "zone", "entry", "stop", "target", "rr", "score",
                                                         "sweep", "mss", "ote", "in_zone", "distance"]} for s in a.setups]),
                        hide_index=True)
    with right:
        st.markdown("### Passer un ordre")
        pos = acc["position"]
        if pos:
            d = 1 if pos["side"] == "LONG" else -1
            st.markdown(f"**Position : {pos['side']} {pos['qty']} MNQ @ {pos['entry']:.2f}**  \n"
                        f"SL {pos['sl']:.2f} · TP {pos['tp'] or '—'}  \nP&L latent : **{upnl:+,.2f} $** "
                        f"({(price - pos['entry']) * d:+.2f} pts)")
            mp = momentum_phase(vis, pos["side"], pos["entry"], pos["entry_time"])
            st.markdown(f"**Cycle du momentum : {mp['phase']}** · construction {mp['construction']} · touches {mp['touches']}  \n_{mp['advice']}_")
            b1, b2 = st.columns(2)
            if b1.button("Clôturer au marché"):
                t = paper.close_position(acc, price, vis.index[-1], "Manuel")
                ss.last_feedback = (t, coach.evaluate_trade(t, acc["start"]))
                st.rerun()
            if b2.button("Stop à break-even"):
                pos["sl"] = pos["entry"]
                st.rerun()
            new_sl = st.number_input("Déplacer le stop", value=float(pos["sl"]), step=0.25, format="%.2f")
            new_tp = st.number_input("Déplacer l'objectif", value=float(pos["tp"] or 0), step=0.25, format="%.2f")
            if st.button("Mettre à jour SL / TP"):
                pos["sl"], pos["tp"] = new_sl, (new_tp or None)
                st.rerun()
        else:
            pre = ["Manuel"] + [f"{i + 1}. {s['direction']} {s['zone']} (R:R {s['rr']})" for i, s in enumerate(a.setups)]
            choice = st.selectbox("Pré-remplir", pre, help="Reprend les niveaux d'un setup détecté — vérifie-les !")
            s0 = a.setups[pre.index(choice) - 1] if choice != "Manuel" else None
            side = st.radio("Sens", ["LONG", "SHORT"], horizontal=True,
                            index=0 if not s0 or s0["direction"] == "LONG" else 1)
            otype = st.radio("Type", ["Marché", "Limite"], horizontal=True, index=1 if s0 and not s0["in_zone"] else 0)
            entry = price if otype == "Marché" else st.number_input(
                "Prix limite", value=float(s0["entry"] if s0 else price), step=0.25, format="%.2f")
            d = 1 if side == "LONG" else -1
            sl = st.number_input("Stop-loss", value=float(s0["stop"] if s0 else round(entry - d * 20, 2)), step=0.25, format="%.2f")
            tp = st.number_input("Objectif (0 = aucun)", value=float(s0["target"] if s0 else round(entry + d * 40, 2)), step=0.25, format="%.2f")
            risk_pct = st.slider("Risque visé (% du capital)", 0.25, 3.0, 1.0, 0.25)
            pts = abs(entry - sl)
            sugg = int(max(1, min(acc["max_contracts"], (acc["start"] * risk_pct / 100) // max(pts * 2, 0.5))))
            qty = st.number_input("Contrats MNQ", 1, int(acc["max_contracts"]), sugg)
            risk_usd = pts * qty * 2
            rr = abs(tp - entry) / pts if tp and pts else 0
            st.markdown(f"Risque : **{risk_usd:,.2f} $** ({risk_usd / acc['start'] * 100:.2f} %) · "
                        f"R:R **{rr:.2f}** · {pts:.2f} pts de stop")
            with st.expander("📝 Mon plan (le coach comparera)", expanded=True):
                setup = st.selectbox("Setup joué", SETUPS)
                pc = st.columns(2)
                plan = dict(setup=setup, bias=pc[0].checkbox("Biais HTF aligné"), sweep=pc[1].checkbox("Sweep vu"),
                            mss=pc[0].checkbox("MSS validé"), ote=pc[1].checkbox("Dans OB/OTE"),
                            kz=pc[0].checkbox("En kill zone"), note=st.text_area("Pourquoi ce trade ?", height=70))
            if st.button(f"{'🟢 ACHETER' if side == 'LONG' else '🔴 VENDRE'} {qty} MNQ"):
                errs = paper.validate_order(acc, side, qty, entry, sl, tp or None)
                if otype == "Limite":
                    if (side == "LONG" and entry > price) or (side == "SHORT" and entry < price):
                        errs.append("Un ordre limite LONG se place sous le prix (SHORT : au-dessus). Sinon, utilise le marché.")
                if errs:
                    for e in errs:
                        st.error(e)
                else:
                    ctx = coach.entry_context(a, side, entry, vis.index[-1])
                    if otype == "Marché":
                        paper.open_position(acc, side, qty, entry, vis.index[-1], sl, tp or None, plan, ctx)
                    else:
                        paper.place_limit(acc, side, qty, entry, sl, tp or None, vis.index[-1], plan, ctx)
                    acc["last_time"] = vis.index[-1]
                    st.rerun()
        if acc["pending"]:
            st.markdown("**Ordres en attente**")
            for p in list(acc["pending"]):
                c_a, c_b = st.columns([3, 1])
                c_a.write(f"{p['side']} {p['qty']} @ {p['price']:.2f} (SL {p['sl']:.2f})")
                if c_b.button("✖", key=f"cx_{p['id']}"):
                    acc["pending"].remove(p)
                    st.rerun()
    if ss.last_feedback:
        t, ev = ss.last_feedback
        st.markdown(f"### Dernier trade : {t['side']} {t['entry']:.2f} → {t['exit']:.2f} · {t['pnl']:+.2f} $ "
                    f"({t['r']:+.2f} R) · note **{ev['grade']} ({ev['score']}/100)**")
        g1, g2, g3 = st.columns(3)
        g1.markdown("**✅ Bien fait**\n" + "\n".join(f"- {x}" for x in ev["good"]) if ev["good"] else "**✅ Bien fait**\n- —")
        g2.markdown("**❌ À corriger**\n" + "\n".join(f"- {x}" for x in ev["bad"]) if ev["bad"] else "**❌ À corriger**\n- Rien à signaler.")
        g3.markdown("**💡 Conseils**\n" + "\n".join(f"- {x}" for x in ev["tips"]) if ev["tips"] else "**💡 Conseils**\n- —")
    if acc["log"]:
        with st.expander("Historique des exécutions"):
            st.text("\n".join(acc["log"][-30:][::-1]))

# ---------------------------------------------------------------- JOURNAL
elif ss.page == "📒 Journal & Coach":
    st.title("📒 Journal de trading & analyse du coach")
    acc = ss.acc
    trades = acc["trades"]
    if not trades:
        st.info("Aucun trade pour l'instant. Va dans le Simulateur, prends quelques trades : ils apparaîtront ici, notés par le coach.")
        st.stop()
    s = paper.stats(trades)
    ins = coach.journal_insights(trades, acc["start"])
    c = st.columns(6)
    c[0].metric("Résultat net", f"{s['net']:+,.2f} $")
    c[1].metric("Trades", s["n"])
    c[2].metric("Win rate", f"{s['winrate']:.1f} %")
    c[3].metric("Profit factor", "∞" if s["pf"] == float("inf") else f"{s['pf']:.2f}")
    c[4].metric("R moyen", f"{s['avg_r']:+.2f}")
    c[5].metric("Note moyenne", f"{ins['avg_score']:.0f}/100")
    show_fig(equity_chart(trades, acc["start"]), key="eq")
    t1, t2, t3 = st.tabs(["Trades", "Erreurs & discipline", "Par setup / session"])
    with t1:
        tab = ins["table"].copy()
        tab["date"] = pd.to_datetime(tab["date"]).dt.strftime("%d/%m/%Y %H:%M")
        show_df(tab, hide_index=True)
        pick = st.selectbox("Revoir un trade", [f"{t['id']} · {t['side']} {t['entry']:.2f} → {t['exit']:.2f} ({t['pnl']:+.0f} $)" for t in trades][::-1])
        tr = next(t for t in trades if t["id"] == pick.split(" · ")[0])
        ev = coach.evaluate_trade(tr, acc["start"])
        st.markdown(f"**Note {ev['grade']} — {ev['score']}/100** · risque {ev['risk_pct']} % · R:R planifié {ev['rr_plan'] or '—'} · "
                    f"sortie : {tr['reason']} · MAE {tr['mae']} pts · MFE {tr['mfe']} pts")
        cc = st.columns(3)
        cc[0].markdown("**✅ Bien fait**\n" + "\n".join(f"- {x}" for x in ev["good"] or ["—"]))
        cc[1].markdown("**❌ À corriger**\n" + "\n".join(f"- {x}" for x in ev["bad"] or ["Rien à signaler."]))
        cc[2].markdown("**💡 Conseils**\n" + "\n".join(f"- {x}" for x in ev["tips"] or ["—"]))
        ctx = tr.get("context", {})
        st.markdown(f"**Contexte détecté à l'entrée** : biais {ctx.get('bias')} · {ctx.get('killzone')} · zone {ctx.get('zone')} · "
                    f"structure {ctx.get('last_structure')} · zones {', '.join(ctx.get('pd_zones', [])) or 'aucune'}")
        if tr.get("plan", {}).get("note"):
            st.markdown(f"**Ta justification** : _{tr['plan']['note']}_")
        if HAS_DATA and df_full.index[0] <= pd.Timestamp(tr["exit_time"]) <= df_full.index[-1]:
            k = int(np.searchsorted(df_full.index, pd.Timestamp(tr["exit_time"]))) + 15
            aa = analyze(df_full.iloc[max(0, k - 1500):k], ss.swing_n, ss.fvg_min)
            show_fig(ict_chart(aa, window=160, show=show, trades=[tr], title="Rejeu du trade"), key="rev")
    with t2:
        if ins["mistakes"]:
            st.markdown("#### Erreurs les plus fréquentes")
            for txt, n in ins["mistakes"]:
                st.markdown(f"- **{n}×** {txt}")
        d = ins["discipline"]
        st.markdown(f"#### Discipline\n- Trades notés **A/B** (≥ 65) : {d['hi_n']} · R moyen **{d['hi_r']:+.2f}**\n"
                    f"- Trades notés **C/D** : {d['lo_n']} · R moyen **{d['lo_r']:+.2f}**")
        if d["hi_n"] and d["lo_n"]:
            st.info("Conclusion : " + ("tes trades conformes au plan rapportent plus — ne prends que les setups A/B."
                                       if d["hi_r"] > d["lo_r"] else
                                       "pas encore d'avantage net des setups A/B : continue à accumuler un échantillon (≥ 30 trades)."))
        st.markdown(f"- Plus grosse série de pertes : **{s['max_loss_streak']}** · drawdown max : **{s['max_dd']:,.2f} $**")
    with t3:
        if not ins["by_setup"].empty:
            show_fig(bar_chart(ins["by_setup"].index.tolist(), ins["by_setup"]["pnl"].tolist(), "P&L par setup ($)", "pnl"), key="bs")
            show_df(ins["by_setup"])
        if not ins["by_kz"].empty:
            show_fig(bar_chart(ins["by_kz"].index.tolist(), ins["by_kz"]["pnl"].tolist(), "P&L par session / kill zone ($)", "pnl"), key="bk")
    exp = pd.DataFrame([{k: v for k, v in t.items() if k not in ("plan", "context")} |
                        {"setup": t.get("plan", {}).get("setup"), "note": t.get("plan", {}).get("note"),
                         "killzone": t.get("context", {}).get("killzone")} for t in trades])
    st.download_button("⬇️ Exporter le journal (CSV)", exp.to_csv(index=False).encode("utf-8"), "journal_mnq.csv", "text/csv")

# ---------------------------------------------------------------- AGENT
elif ss.page == "🤖 Agent expert":
    st.title("🤖 Agent expert — technique ICT & conditions de marché")
    prov = st.selectbox("Moteur de réponse", ["Moteur expert intégré", "Claude (API Anthropic)", "Ollama (local)"],
                        help="Le moteur intégré fonctionne sans clé. Claude/Ollama rédigent une analyse plus riche à partir des mêmes données.")
    if prov == "Claude (API Anthropic)" and not agent.secret("ANTHROPIC_API_KEY"):
        ss.anthropic_key = st.text_input("Clé API Anthropic (ou dans les Secrets Streamlit)", type="password",
                                         value=ss.get("anthropic_key", ""))
    if prov == "Ollama (local)":
        o1, o2 = st.columns(2)
        ss.ollama_host = o1.text_input("Hôte Ollama", ss.get("ollama_host", "http://localhost:11434"))
        ss.ollama_model = o2.text_input("Modèle", ss.get("ollama_model", "mistral"))
    tA, tB, tC = st.tabs(["📊 Analyse du marché", "💬 Discuter avec l'agent", "📂 Analyser un CSV"])
    a = current_analysis()[0] if HAS_DATA else None

    def macro_bundle():
        with st.spinner("Lecture des marchés liés et de l'actualité…"):
            m = agent.macro_snapshot()
            reg = agent.macro_regime(m)
            news = agent.classify_news(agent.fetch_news())
            return m, reg, news, agent.news_digest(news)

    with tA:
        if st.button("Lancer l'analyse complète"):
            ss.macro = macro_bundle()
        if a is not None:
            st.markdown(agent.technical_report(a, src_label))
        else:
            st.info(msg or "Charge des données pour l'analyse technique.")
        if "macro" in ss:
            m, reg, news, digest = ss.macro
            st.markdown(f"### Conditions de marché — régime **{reg['label']}** (score {reg['score']:+d})")
            for p_ in reg["points"]:
                st.markdown(f"- {p_}")
            if not m.empty:
                show_df(m.drop(columns=["Ticker"]), hide_index=True)
            st.markdown("### Actualités : économique · financier · politique · géopolitique")
            for p_ in digest:
                st.markdown(f"- {p_}")
            if not news.empty:
                show_df(news.drop(columns=["_s"]), hide_index=True,
                        column_config={"Lien": st.column_config.LinkColumn("Lien", display_text="ouvrir")})
            st.markdown("### Agenda à surveiller")
            for f in agent.calendar_flags():
                st.markdown(f"- {f}")
            ctx = (agent.technical_report(a, src_label) if a is not None else "") + "\n\nMACRO:\n" + \
                "\n".join(reg["points"]) + "\n\nACTUALITÉS:\n" + "\n".join(digest)
            if prov != "Moteur expert intégré":
                with st.spinner("Rédaction de la synthèse…"):
                    ans = agent.llm_answer(prov, "Fais une synthèse de trading pour la prochaine session MNQ : biais, "
                                                 "scénarios, niveaux, risques macro et géopolitiques.", ctx)
                if ans:
                    st.markdown("### Synthèse de l'agent")
                    st.markdown(ans)
        else:
            st.caption("Clique sur « Lancer l'analyse complète » pour ajouter la macro (VIX, DXY, taux, pétrole, or, SOX…) et l'actualité.")

    with tB:
        for msg_ in ss.chat:
            with st.chat_message(msg_["role"]):
                st.markdown(msg_["content"])
        q = st.chat_input("Ex. : quel est mon biais pour NY AM ? Où est le prochain setup ? Explique le breaker.")
        if q:
            ss.chat.append({"role": "user", "content": q})
            if "macro" not in ss and any(k in q.lower() for k in ["macro", "news", "actu", "géopol", "politique", "fed", "vix", "taux", "contexte", "conditions"]):
                ss.macro = macro_bundle()
            reg = ss.macro[1] if "macro" in ss else None
            dig = ss.macro[3] if "macro" in ss else None
            ans = None
            if prov != "Moteur expert intégré":
                ctx = (agent.technical_report(a, src_label) if a is not None else "") + \
                    ("\n\nMACRO:\n" + "\n".join(reg["points"]) if reg else "") + ("\n\nACTUALITÉS:\n" + "\n".join(dig) if dig else "")
                ans = agent.llm_answer(prov, q, ctx, ss.chat[:-1])
            base = agent.expert_answer(q, a, reg, dig)
            if ans is None:
                ans = base
            elif ans.startswith("⚠️"):
                ans = ans + "\n\n" + base
            ss.chat.append({"role": "assistant", "content": ans})
            st.rerun()
        if ss.chat and st.button("Effacer la conversation"):
            ss.chat = []
            st.rerun()

    with tC:
        st.markdown("Dépose un **CSV de bougies** (export TradingView, NinjaTrader, Tradovate, Excel…) ou un **CSV de trades** "
                    "(journal Apex / Tradovate / maison avec une colonne PnL ou entrée/sortie).")
        f = st.file_uploader("Fichier CSV", type=["csv", "txt"], key="agent_csv")
        if f is not None:
            try:
                raw = read_csv_any(f)
            except Exception as e:
                st.error(f"Lecture impossible : {e}")
                raw = None
            if raw is not None:
                kind = detect_csv_kind(raw)
                kind = st.radio("Type détecté", ["ohlc", "trades", "generic"], index=["ohlc", "trades", "generic"].index(kind),
                                horizontal=True, format_func={"ohlc": "Bougies OHLC", "trades": "Journal de trades",
                                                              "generic": "Autre tableau"}.get)
                with st.expander("Aperçu du fichier"):
                    show_df(raw.head(30))
                if kind == "ohlc":
                    tzc = st.selectbox("Fuseau des dates", [NY_TZ, "Europe/Paris", "UTC", "America/Chicago"], key="tz_agent")
                    o = csv_to_ohlc(raw, tzc)
                    if len(o) < 30:
                        st.error("Moins de 30 bougies exploitables.")
                    else:
                        aa = analyze(o.iloc[-3000:], ss.swing_n, ss.fvg_min)
                        show_fig(ict_chart(aa, window=min(300, len(o)), show=show, title=f.name), key="csv_chart")
                        rep = agent.technical_report(aa, f.name)
                        st.markdown(rep)
                        if prov != "Moteur expert intégré":
                            ans = agent.llm_answer(prov, "Analyse ce graphique uploadé : biais, structure, liquidités, setups et plan.", rep)
                            if ans:
                                st.markdown("### Lecture de l'agent")
                                st.markdown(ans)
                elif kind == "trades":
                    rep, by = agent.analyze_trades_csv(raw.copy())
                    st.markdown(rep)
                    if not by.empty:
                        show_fig(bar_chart([f"{h}h" for h in by.index], by["sum"].tolist(), "P&L par heure", "pnl"), key="csv_h")
                    if prov != "Moteur expert intégré":
                        ans = agent.llm_answer(prov, "Analyse mon journal et donne-moi un plan d'amélioration concret.", rep)
                        if ans:
                            st.markdown(ans)
                else:
                    st.markdown("### Statistiques descriptives")
                    show_df(raw.describe(include="all").T)
                    if prov != "Moteur expert intégré":
                        ans = agent.llm_answer(prov, "Analyse ce tableau pour un trader Nasdaq.", raw.head(200).to_csv(index=False))
                        if ans:
                            st.markdown(ans)

elif ss.page == "🖥️ Edge Desk (live)":
    if msg and not HAS_DATA:
        st.title("🖥️ Edge Desk — poste de pilotage MNQ")
        st.warning(msg)
    elif HAS_DATA:
        render_desk(df_full, src_label, show, window)

elif ss.page == "📊 Backtests & Verdicts":
    if not HAS_DATA:
        st.title("📊 Backtests · Verdicts · Stratégies")
        st.warning(msg or "Charge des données.")
    else:
        render_backtests(df_full, src_label, ss.swing_n, show, window)

elif ss.page == "📜 Scripts TradingView":
    render_scripts(src_label)

# ---------------------------------------------------------------- FIGURES
elif ss.page == "📚 Figures ICT":
    st.title("📚 Les figures de l'ICT trading")
    st.markdown("Bibliothèque des concepts ICT / Smart Money, reliée aux pages du **cours Warren**. "
                f"{pill('Auto', 'green')} = détecté automatiquement sur le graphique de la plateforme.", unsafe_allow_html=True)
    if hasattr(st, "html"):
        st.html(CHEATSHEET_HTML)
    else:
        components.html(CHEATSHEET_HTML, height=300, scrolling=True)
    if HAS_DATA:
        a = current_analysis()[0]
        cnt = dict(MSS=sum(e["kind"] == "MSS" for e in a.events[-200:]), BOS=sum(e["kind"] == "BOS" for e in a.events[-200:]),
                   OB=sum(not o["breaker"] for o in a.obs[-200:]), Breakers=sum(o["breaker"] for o in a.obs[-200:]),
                   FVG_ouverts=sum(g["status"] != "comblé" for g in a.fvgs), Sweeps=len(a.sweeps[-200:]), EQH_EQL=len(a.eq_levels))
        st.markdown("**Sur les données actuelles** : " + " · ".join(f"{k.replace('_', ' ')} {v}" for k, v in cnt.items()))
    cats = sorted(set(f[0] for f in FIGURES), key=[f[0] for f in FIGURES].index)
    sel = st.multiselect("Catégories", cats, default=cats)
    for cat in sel:
        st.markdown(f"### {cat}")
        for c_, name, definition, ident, exe, src, auto in [f for f in FIGURES if f[0] == cat]:
            with st.expander(("🟢 " if auto else "⚪ ") + name):
                st.markdown(f"**Définition** — {definition}\n\n**Comment l'identifier** — {ident}\n\n"
                            f"**Comment le trader** — {exe}\n\n*Source : {src}*"
                            + ("\n\n✅ Détecté automatiquement par la plateforme." if auto else "\n\nÀ repérer manuellement."))

# ---------------------------------------------------------------- MÉTHODE
elif ss.page == "🧭 Méthode d'étude":
    st.title("🧭 Méthode d'étude d'un graphique (cours Warren)")
    t1, t2, t3 = st.tabs(["Les 10 étapes", "Exercice guidé sur le graphique", "Quiz"])
    with t1:
        for title, body, quote in STUDY_STEPS:
            with st.expander(title, expanded=title.startswith("1.")):
                st.markdown(body)
                st.markdown(f"> {quote}")
    with t2:
        if not HAS_DATA:
            st.info("Charge des données pour faire l'exercice.")
        else:
            a, vis = current_analysis()
            st.markdown("Analyse le graphique **avant** de regarder les réponses du moteur. "
                        "Astuce : décoche les annotations dans la barre latérale pour t'entraîner « à nu ».")
            show_fig(ict_chart(a, window=window, show={k: False for k in show}, title="Graphique nu — à toi de lire"), key="ex_chart")
            with st.form("exo"):
                g1 = st.radio("1. Quel est le biais multi-UT ?", ["Haussier", "Baissier", "Neutre / range"], horizontal=True)
                g2 = st.radio("2. Le prix est-il en premium ou en discount du range de travail ?", ["PREMIUM", "DISCOUNT", "EQ (équilibre)", "Hors range"], horizontal=True)
                g3 = st.radio("3. Dernière rupture de structure ?", ["MSS haussier", "MSS baissier", "BOS haussier", "BOS baissier"], horizontal=True)
                g4 = st.number_input("4. Niveau de l'EQ du range (prix)", value=float(vis["close"].iloc[-1]), step=0.25)
                g5 = st.radio("5. Que fais-tu ?", ["J'attends", "Je cherche un LONG", "Je cherche un SHORT"], horizontal=True)
                ok = st.form_submit_button("Corriger")
            if ok:
                sc = 0
                st.markdown(f"1. Biais moteur : **{a.bias}** " + ("✅" if g1 == a.bias else "❌")); sc += g1 == a.bias
                z = a.rng["zone"] if a.rng else "n/d"
                z2 = z if z in ("PREMIUM", "DISCOUNT", "EQ (équilibre)") else "Hors range"
                st.markdown(f"2. Zone : **{z}** " + ("✅" if g2 == z2 else "❌")); sc += g2 == z2
                if a.events:
                    e = a.events[-1]
                    lab = f"{e['kind']} {'haussier' if e['dir'] == 1 else 'baissier'}"
                    st.markdown(f"3. Dernière rupture : **{lab}** à {e['level']:.2f} " + ("✅" if g3 == lab else "❌")); sc += g3 == lab
                if a.rng:
                    err = abs(g4 - a.rng["eq"])
                    good = err <= max(5, (a.rng["hi"] - a.rng["lo"]) * 0.05)
                    st.markdown(f"4. EQ : **{a.rng['eq']:.2f}** (écart {err:.2f} pts) " + ("✅" if good else "❌")); sc += good
                exp_action = "J'attends" if not any(s["in_zone"] for s in a.setups) else \
                    ("Je cherche un LONG" if a.setups[0]["direction"] == "LONG" else "Je cherche un SHORT")
                st.markdown(f"5. Action attendue : **{exp_action}** " + ("✅" if g5 == exp_action else "❌")); sc += g5 == exp_action
                st.success(f"Score : {sc}/5. Regarde maintenant le graphique annoté dans le Simulateur pour comprendre les écarts.")
    with t3:
        with st.form("quiz"):
            answers = [st.radio(f"{i + 1}. {q}", opts, index=None, key=f"q{i}") for i, (q, opts, _) in enumerate(QUIZ)]
            done = st.form_submit_button("Valider le quiz")
        if done:
            score = sum(1 for (q, opts, good), r in zip(QUIZ, answers) if r == opts[good])
            for (q, opts, good), r in zip(QUIZ, answers):
                st.markdown(("✅ " if r == opts[good] else "❌ ") + f"{q} → **{opts[good]}**")
            st.success(f"Résultat : {score}/{len(QUIZ)}")

# ---------------------------------------------------------------- AIDE
else:
    st.title("⚙️ Mode d'emploi & mise à jour")
    st.markdown("""
#### Utilisation quotidienne
1. **Simulateur → Replay** : choisis une date, clique *Positionner*, puis avance avec *+1 / +5 / +20 / +1 jour / NY open*. Le futur est masqué.
2. Suis le **Coach en direct** (6 conditions). Quand le setup est prêt, remplis l'ordre : **stop obligatoire**, cible, risque en %.
3. Coche ton **plan** (setup, sweep, MSS…) et écris pourquoi tu prends le trade : le coach compare ton plan à ce que le moteur voit.
4. *Jusqu'à sortie* fait défiler les bougies jusqu'au stop ou à l'objectif. La note (A à D) s'affiche avec les erreurs.
5. **Journal & Coach** : erreurs récurrentes, P&L par setup et par kill zone, rejeu de chaque trade.
6. **Sauvegarde ta session** (barre latérale → Compte fictif) : Streamlit Cloud ne conserve rien entre deux visites.

#### Données
- Yahoo Finance : `MNQ=F` (repli automatique sur `NQ=F`, même cotation). Limites Yahoo : 1 min = 7 jours, 5/15/30 min = 60 jours, 1 h = 2 ans. Cotations différées d'environ 10-15 min.
- Heures affichées en **heure de New York** (référence ICT). Paris = NY + 6 h (5 h pendant les semaines de décalage d'heure d'été).
- P&L calculé en **MNQ : 2 $ par point**, tick 0,25 = 0,50 $, commission paramétrable.

#### Backtests & Verdicts
- Clique sur **Lancer** : 17 setups ICT et MMM sont rejoués bougie par bougie **après coûts** (1 pt par trade), puis jugés sur la période ancienne (70 %) et récente (30 %).
- Plus il y a de bougies, plus le verdict est fiable : en 1 h, Yahoo donne 2 ans ; pour plus, importe un export TradingView (CSV).
- *Rejouer un setup* dessine chaque trade (entrée, stop, objectif, R) sur le graphique avec l'escalier, les boîtes et le MMPD.

#### Scripts TradingView
- Télécharge le **Word** (mode d'emploi + code + tes derniers verdicts) ou les fichiers **.pine** à coller dans le Pine Editor.

#### Agent expert
- *Moteur expert intégré* : sans clé, analyse calculée (structure, liquidité, OB, breakers, FVG, OTE, niveaux, POC) + macro (VIX, DXY, taux, pétrole, or, SOX, BTC, USD/JPY) + actualités classées économique / financier / politique / géopolitique.
- *Claude* : ajoute `ANTHROPIC_API_KEY = "..."` (et facultatif `ANTHROPIC_MODEL`) dans les **Secrets** de Streamlit Cloud.
- *Ollama* : uniquement en local (`ollama run mistral`), hôte `http://localhost:11434`.

#### Déploiement GitHub + Streamlit Cloud
```bash
git init && git add . && git commit -m "ICT MNQ Academy v1"
git branch -M main
git remote add origin https://github.com/<ton-compte>/ict-mnq-academy.git
git push -u origin main
```
Puis sur share.streamlit.io : *New app* → dépôt → fichier principal `main.py`.

#### Mettre à jour
Modifie les fichiers, puis `git add . && git commit -m "maj" && git push` : Streamlit Cloud redéploie automatiquement.

_Plateforme d'entraînement — aucune donnée n'est un conseil en investissement._
""")

st.markdown('<div class="footer">ICT MNQ Academy · entraînement au trading sur compte fictif · '
            'données Yahoo Finance différées · aucune information n\'est un conseil en investissement</div>', unsafe_allow_html=True)
