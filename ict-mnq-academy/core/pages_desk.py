"""Page « Edge Desk » : poste de pilotage live (même règles que le script TradingView « Edge 5 Desk »)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from . import coach, edge, paper
from .charts import edge_chart
from .data import load_market, resample
from .mmm import analyze_mmm
from .style import card, pill

LIVE_MODE = "Live différé (Yahoo ~10-15 min)"
ORDER_PAGE = "🎯 PASSER UN ORDRE (compte fictif)"


def _go_order():
    st.session_state["nav"] = ORDER_PAGE
    st.session_state.page = ORDER_PAGE
    st.session_state.mode = LIVE_MODE
    st.session_state["mode_radio"] = LIVE_MODE
STATUS_KIND = {"TRADE": "green", "WATCH": "orange", "DON'T TRADE": "red"}


def _df(d, **kw):
    try:
        st.dataframe(d, width="stretch", **kw)
    except TypeError:
        st.dataframe(d, use_container_width=True, **kw)


def _fig(f, key):
    try:
        st.plotly_chart(f, width="stretch", key=key, theme=None, config={"scrollZoom": True, "displaylogo": False})
    except TypeError:
        st.plotly_chart(f, use_container_width=True, key=key, theme=None, config={"scrollZoom": True, "displaylogo": False})


def _to_15m(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    if df.empty or len(df) < 3:
        return df, ""
    step = df.index[1] - df.index[0]
    if step < pd.Timedelta("15min"):
        return resample(df, "15min"), "Données agrégées en 15 min (unité de décision des setups)."
    if step > pd.Timedelta("15min"):
        return df, "⚠️ Les 5 setups sont calibrés en 15 min : choisis l'unité 15m (ou plus fine) pour des résultats comparables."
    return df, ""


def _warnings():
    with st.expander("⚠️ Avant d'utiliser ces analyses pour trader en réel — à lire", expanded=not st.session_state.get("desk_ack")):
        st.markdown("""
- **Les données Yahoo sont différées (~10-15 min)** : la plateforme sert à préparer et vérifier. Pour **exécuter**, utilise le script
  **Edge 5 Desk** sur ton graphique TradingView en temps réel (mêmes règles, alertes à la clôture de la bougie 15 min).
- **Un verdict n'a de valeur qu'avec assez d'historique** : Yahoo ne donne que 60 jours en 15 min. Importe un export CSV TradingView
  (6-12 mois minimum) ou lance le Strategy Tester / le tableau du script sur ton historique avant de faire confiance à un setup.
- **Ne trade en réel que les setups au statut TRADE** sur ton historique, après **au moins 30 trades en paper / forward-test** cohérents
  avec le backtest. Un setup WATCH se teste en simulation, un DON'T TRADE ne se trade pas.
- **Risque** : 1 % max par trade (0,5 % les jours d'annonces), stop placé avant l'entrée, 2 positions max, journée arrêtée à −3 %.
  Évite les jours CPI / NFP / FOMC (ajoute leurs dates dans les réglages).
- Rien ici n'est un conseil en investissement : les performances passées ne garantissent pas les résultats futurs, et la décision
  finale (et le risque) restent les tiens.
""")
        if st.checkbox("J'ai lu ces points", key="desk_ack"):
            pass


def render_desk(df_full: pd.DataFrame, src_label: str, show: dict, window: int, analyze_ict=None):
    ss = st.session_state
    st.title("🔴 Trader en direct — signaux live MNQ")
    st.caption("Mêmes règles que l'indicateur TradingView « Edge 5 Desk » (onglet Scripts) : 5 setups ICT × MMM, ½ sortie, "
               "stop ramené à l'entrée, gate MMPD 27, sessions Asie + NY AM, 2 positions max, coût 1 pt par trade.")
    _warnings()
    st.button("🎯 Passer un ordre manuel sur le graphique live (compte fictif)", on_click=_go_order)

    with st.expander("⚙️ Réglages du desk", expanded=False):
        c = st.columns(4)
        enabled = c[0].multiselect("Setups actifs", list(edge.SETUPS), default=list(edge.SETUPS),
                                   format_func=lambda k: edge.SETUPS[k]["name"], key="desk_en")
        half = c[1].checkbox("½ sortie puis stop à l'entrée", True, key="desk_half")
        gate = c[1].checkbox("Gate MMPD 27 momentum", True, key="desk_gate")
        dly = c[1].checkbox("Filtre journalière d'hier", True, key="desk_daily")
        h1 = c[1].checkbox("Filtre tendance 1H", True, key="desk_h1")
        sess = c[1].checkbox("Sessions Asie + NY AM (00–02 exclu sauf C)", True, key="desk_sess")
        qty = c[2].number_input("Contrats MNQ", 1, 50, 2, key="desk_qty")
        maxo = c[2].number_input("Positions max", 1, 5, 2, key="desk_maxo")
        cost = c[2].number_input("Coût par trade (points)", 0.0, 5.0, 1.0, 0.25, key="desk_cost")
        target = c[3].number_input("Objectif évaluation prop ($)", 500.0, 20000.0, 3000.0, 250.0, key="desk_target")
        dd = c[3].number_input("Drawdown suiveur ($)", 500.0, 10000.0, 2500.0, 250.0, key="desk_dd")
        news = st.text_input("Jours à ignorer (CPI, NFP, FOMC…) — dates AAAA-MM-JJ séparées par des virgules", key="desk_news")
        auto = False  # le rafraîchissement live est géré globalement (barre latérale « Live auto »)
    cfg = edge.Config(enabled=tuple(enabled), half_out=half, gate=gate, use_daily=dly, use_h1=h1, sessions=sess,
                      max_open=int(maxo), cost_pts=float(cost), contracts=int(qty),
                      skip_dates=tuple(x.strip() for x in news.split(",") if x.strip()))

    def body():
        df = df_full
        if auto and ss.get("source") == "Yahoo Finance":
            fresh, _, _ = load_market(ss.get("ticker", "MNQ=F"), ss.get("interval", "15m"), ss.get("period", "60d"))
            if not fresh.empty:
                df = fresh
        if df is None or df.empty or len(df) < 100:
            st.warning("Pas assez de données (100 bougies minimum).")
            return
        df15, note = _to_15m(df)
        if note:
            st.info(note)
        res = edge.run_edge(df15, cfg)
        res_full = edge.run_edge(df15, edge.Config(**{**cfg.__dict__, "half_out": False}))
        stats = edge.setup_stats(res.trades)
        ss.desk_res = res

        top = st.columns([2.2, 1])
        with top[0]:
            _fig(edge_chart(res, window=window, title=f"{src_label} — Edge 5 Desk (15 min)", mmm=None), "desk_chart")
        with top[1]:
            st.markdown("#### EDGE DESK")
            _df(pd.DataFrame(edge.desk_rows(res), columns=["", "Lecture"]), hide_index=True)
            fires = [x for x in res.signals_now if x["status"].startswith("FIRE")]
            if fires:
                for f in fires:
                    tk = edge.order_ticket(res, f["sid"], f["dir"] or 1, risk_usd=ss.acc["balance"] * 0.01)
                    card(f"🔔 {tk['setup']} — {tk['side']}",
                         f"{tk['type']} · entrée <b>{tk['entry']:.2f}</b> · SL <b>{tk['stop']:.2f}</b> ({tk['risk_pts']} pts) · "
                         f"½ TP <b>{tk['half']:.2f}</b> · TP <b>{tk['tp']:.2f}</b><br>{tk['contracts']} MNQ pour ≈ {tk['risk_usd']:.0f} $ "
                         f"de risque (1 % du compte fictif)")
                    if st.button(f"Envoyer {tk['setup'].split(' ·')[0]} au compte fictif", key=f"send_{f['sid']}"):
                        _send(tk, f, res, df15)
            else:
                st.markdown("Aucun setup ne se déclenche sur la dernière bougie clôturée.")

        st.markdown("#### Edges testés sur l'historique chargé")
        rows = []
        for x in res.signals_now:
            s = edge.SETUPS[x["sid"]]
            r = stats[stats["sid"] == x["sid"]].iloc[0].to_dict() if not stats.empty and (stats["sid"] == x["sid"]).any() else {}
            rows.append(dict(Setup=s["name"], NOW=x["status"], HTF_CTF_ETF=s["htf"], Trades=r.get("trades", 0),
                             WR=f"{r['WR']:.0f} %" if r.get("trades") else "—",
                             avg_RR=f"{r['avg_RR_ancien']:+.2f} → {r['avg_RR_récent']:+.2f}" if r.get("trades") else "—",
                             PF=round(r["PF"], 2) if r.get("trades") else None, t=round(r["t"], 2) if r.get("trades") and not np.isnan(r["t"]) else None,
                             worst_run_R=round(r["worst_run_R"], 1) if r.get("trades") else None, Verdict=edge.verdict(r)))
        if not stats.empty:
            r = stats[stats["sid"] == 0].iloc[0].to_dict()
            rows.append(dict(Setup="ALL 5", NOW=f"{len(res.open_trades)} ouvert(s) · {len(res.pending)} limite(s)", HTF_CTF_ETF="",
                             Trades=r["trades"], WR=f"{r['WR']:.0f} %", avg_RR=f"{r['avg_RR_ancien']:+.2f} → {r['avg_RR_récent']:+.2f}",
                             PF=round(r["PF"], 2), t=round(r["t"], 2) if not np.isnan(r["t"]) else None,
                             worst_run_R=round(r["worst_run_R"], 1), Verdict=edge.verdict(r)))
        _df(pd.DataFrame(rows).astype(object).where(pd.DataFrame(rows).notna(), "—").astype(str), hide_index=True)
        st.caption("WR = trades gagnants · avg RR ancien (70 % des trades) → récent (30 %) après coûts · worst run = pire drawdown en R · "
                   "TRADE = ≥ 30 trades, positif ancien ET récent, t ≥ 2,5.")

        st.markdown("#### PROP HELPER — tes règles rejouées sur cet historique")
        pt = edge.prop_table(res.trades, res_full.trades, int(qty), float(target), float(dd))
        if pt.empty:
            st.info("Pas encore de trades sur cet historique.")
        else:
            pt = pt.astype(object).where(pt.notna(), "—").astype(str)
            _df(pt.rename(columns={"pass_you": f"pass @ {int(qty)} MNQ", "jours_médians": "jours (médiane)",
                                   "meilleure_taille": "meilleure taille", "pass_meilleure": "pass @ meilleure"}), hide_index=True)
            st.caption("Une évaluation démarre à chaque trade de l'historique et rejoue la suite réelle jusqu'à l'objectif (✓) ou au "
                       "drawdown suiveur (✗, seuil bloqué à +100 $). « aucune décidée » = l'historique est trop court pour conclure.")

        if not res.trades.empty:
            with st.expander(f"Journal des {len(res.trades)} trades simulés"):
                t = res.trades[["label", "time", "dir", "entry", "init_stop", "half_px", "tp", "exit", "reason", "R", "pts", "usd"]].copy()
                t["time"] = pd.to_datetime(t["time"]).dt.strftime("%d/%m %H:%M")
                _df(t.round(2).iloc[::-1], hide_index=True)
                st.download_button("⬇️ Exporter (CSV)", t.to_csv(index=False).encode("utf-8"), "edge5_trades.csv", "text/csv")

    if auto and hasattr(st, "fragment"):
        st.fragment(run_every=60)(body)()
    else:
        body()


def _send(tk: dict, f: dict, res, df15: pd.DataFrame):
    ss = st.session_state
    acc = ss.acc
    if acc["position"]:
        st.error("Une position est déjà ouverte dans le compte fictif.")
        return
    if not ss.get("mode", "").startswith("Live"):
        ss.mode = LIVE_MODE
        ss["mode_radio"] = LIVE_MODE
        acc["pending"], acc["last_time"] = [], None
    t = df15.index[-1]
    tk = dict(tk, contracts=int(min(tk["contracts"], acc["max_contracts"])))
    plan = dict(setup=tk["setup"], bias=True, sweep=False, mss=f["sid"] == 1, ote=False, kz=True,
                note=f"Signal Edge Desk {tk['setup']} ({tk['type']})")
    ctx = dict(killzone="", bias="", bias_score=0, htf={}, zone="n/d", sweep_recent=False, mss_in_dir=f["sid"] == 1,
               bos_in_dir=True, last_structure="", pd_zones=[], premium_discount_ok=None, at_eq=False, weekday=t.day_name())
    if tk["type"].startswith("Limite"):
        paper.place_limit(acc, tk["side"], tk["contracts"], tk["entry"], tk["stop"], tk["tp"], t, plan, ctx)
    else:
        paper.open_position(acc, tk["side"], tk["contracts"], tk["entry"], t, tk["stop"], tk["tp"], plan, ctx)
    acc["last_time"] = t
    st.success("Ordre envoyé au compte fictif (Simulateur en mode Live différé). La ½ sortie se gère dans le Simulateur.")
