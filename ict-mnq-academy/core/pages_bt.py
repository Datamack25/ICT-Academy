"""Pages « Backtests & Verdicts » et « Scripts TradingView »."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import backtest as bt
from .charts import LAYOUT, add_bt_trades, add_mmm_layer, ict_chart, mmpd_chart
from .ict import analyze
from .mmm import alignment, analyze_mmm
from .pine import SCRIPTS
from .word_export import READ_NUMBERS, build_docx

STATUS_COL = {"TRADE": "#0B7A3E", "USE AS FILTER": "#00796B", "WATCH": "#B85C00", "DON'T TRADE": "#B3261E"}
STATUS_FR = {"TRADE": "Positif dans les deux périodes, t-score suffisant, assez de trades, bat le hasard.",
             "USE AS FILTER": "Pas un trade seul : améliore les setups auxquels on l'ajoute, dans les deux périodes.",
             "WATCH": "Positif dans les deux périodes mais trop peu de trades ou t-score < 2 : à tester en avant.",
             "DON'T TRADE": "Perd après coûts, s'est effacé, ou ne marche que sur une période."}


def _fig(fig, key):
    try:
        st.plotly_chart(fig, width="stretch", key=key, theme=None, config={"displaylogo": False, "scrollZoom": True})
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key, theme=None)


def _df(d, **kw):
    try:
        st.dataframe(d, width="stretch", **kw)
    except TypeError:
        st.dataframe(d, use_container_width=True, **kw)


def badge(status: str) -> str:
    c = STATUS_COL.get(status, "#000")
    return (f'<span style="display:inline-block;border:1.5px solid {c};color:{c};border-radius:4px;padding:1px 7px;'
            f'font-family:monospace;font-weight:700;font-size:0.78rem;letter-spacing:0.5px">{status}</span>')


def _f(v, fmt="{:+.2f}"):
    return "—" if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))) else fmt.format(v)


def _sig(df: pd.DataFrame) -> str:
    return hashlib.md5(pd.util.hash_pandas_object(df[["open", "high", "low", "close"]], index=True).values.tobytes()).hexdigest()


@st.cache_data(show_spinner=False, max_entries=6)
def _run(_df_, sig, swing_n, cost, session, gate, max_bars):
    res, sigs, ctx = bt.run_canonical(_df_, swing_n, cost, session, gate, max_bars)
    filt = bt.filter_tests(_df_, sigs, ctx, cost, max_bars)
    return res, sigs, ctx, filt


@st.cache_data(show_spinner=False, max_entries=4)
def _grid(_df_, sig, _sigs, _ctx, cost, max_bars):
    return bt.run_grid(_df_, _sigs, _ctx, cost, max_bars)


def verdict_rows(res: dict, filt: list) -> list:
    rows = []
    for name, r in res.items():
        e = r["eval"]
        rows.append(dict(verdict=e["verdict"], setup=name, n=e["all"]["n"], wr=_f(e["all"]["wr"], "{:.0f} %"),
                         old_new=f"{_f(e['old']['avg_r'])} → {_f(e['fresh']['avg_r'])}",
                         pf=_f(e["all"]["pf"], "{:.2f}"), t=_f(e["all"]["t"], "{:.2f}")))
    for f in filt:
        rows.append(dict(verdict=f["verdict"], setup=f"Filtre · {f['filtre']}", n=f["setups_testés"], wr="—",
                         old_new=f"améliore {f['améliore_ancien']} → {f['améliore_récent']}", pf="—", t=f"Δ {f['delta_avg_R']:+.3f}"))
    order = {"TRADE": 0, "USE AS FILTER": 1, "WATCH": 2, "DON'T TRADE": 3}
    return sorted(rows, key=lambda x: order.get(x["verdict"], 9))


# ====================================================================== BACKTESTS
def render_backtests(df: pd.DataFrame, src_label: str, swing_n: int, show: dict, window: int):
    st.title("📊 Backtests · Verdicts · Stratégies")
    if df is None or len(df) < 300:
        st.warning("Il faut au moins 300 bougies pour un backtest crédible. Sur Yahoo : 15 min / 60 jours ou 1 h / 2 ans ; "
                   "ou importe un export TradingView en CSV (barre latérale → Fichier CSV).")
        return
    step = df.index[1] - df.index[0]
    st.markdown(f"**{src_label}** · {len(df):,} bougies du {df.index[0]:%d/%m/%Y} au {df.index[-1]:%d/%m/%Y} · "
                "chaque chiffre est **après coûts** · période ancienne = 70 % des dates, récente = 30 %".replace(",", " "))
    with st.expander("⚙️ Paramètres du test", expanded=False):
        c = st.columns(4)
        cost = c[0].number_input("Coût par trade (points)", 0.0, 10.0, 1.0, 0.25, help="1 pt = slippage 1 tick de chaque côté + commission.")
        max_bars = c[1].number_input("Sortie forcée après (bougies)", 4, 500, 64, 4)
        session = c[2].selectbox("Sessions", ["Toutes", "Asie + NY AM", "NY AM", "Londres + NY AM"])
        gate = c[3].selectbox("Gate", ["Aucun", "MMPD 27 momentum"])
    if st.button("▶ Lancer / actualiser les backtests"):
        st.session_state.bt_go = True
    if not st.session_state.get("bt_go"):
        st.info("Clique sur « Lancer » : la plateforme rejoue 17 setups ICT et MMM sur tes données, puis 4 filtres.")
        _static_tabs(df)
        return
    sig = _sig(df)
    with st.spinner("Rejeu des setups bougie par bougie…"):
        res, sigs, ctx, filt = _run(df, sig, swing_n, cost, session, gate, int(max_bars))
    st.session_state.bt_rows = verdict_rows(res, filt)
    st.session_state.bt_label = src_label
    cut = df.index[int(len(df) * 0.7)]
    n_trade = sum(r["eval"]["verdict"] == "TRADE" for r in res.values())
    n_watch = sum(r["eval"]["verdict"] == "WATCH" for r in res.values())
    tabs = st.tabs(["Start here", "Verdicts", "Rejouer un setup", "Grille", "Niveaux & odds", "Prop & taille",
                    "Mots & indicateurs", "Comment on a testé", "Lire les chiffres"])
    # ---------------------------------------------------------- START HERE
    with tabs[0]:
        tiles = [(f"{(cut - df.index[0]).days} j", "Période ancienne", f"{df.index[0]:%d/%m/%y} → {cut:%d/%m/%y} : on construit."),
                 (f"{(df.index[-1] - cut).days} j", "Période récente", f"{cut:%d/%m/%y} → {df.index[-1]:%d/%m/%y} : on vérifie."),
                 (f"{len(res)}", "Setups testés", "ICT (cours Warren) + MMM (site + PDF), règles canoniques."),
                 (f"{n_trade}", "TRADE", "Positifs dans les deux périodes avec t-score."),
                 (f"{n_watch}", "WATCH", "Positifs partout mais pas encore prouvés."),
                 (f"{cost:g} pt", "Coût / trade", f"= {cost * 2:.2f} $ par contrat MNQ.")]
        cols = st.columns(6)
        for col, (big, lab, sub) in zip(cols, tiles):
            col.markdown(f'<div class="card"><div style="font-size:1.6rem;font-weight:800;font-family:monospace">{big}</div>'
                         f'<b>{lab}</b><div style="font-size:0.85rem">{sub}</div></div>', unsafe_allow_html=True)
        best = sorted(res.items(), key=lambda kv: -(kv[1]["eval"]["all"]["avg_r"] if kv[1]["eval"]["all"]["n"] >= 20 else -9))
        good_f = [f["filtre"] for f in filt if f["verdict"] == "USE AS FILTER"]
        st.markdown("### Ce que disent TES données")
        lines = []
        if best and best[0][1]["eval"]["all"]["n"] >= 20:
            b = best[0]
            lines.append(f"Meilleur avg RR (≥ 20 trades) : **{b[0]}** ({_f(b[1]['eval']['all']['avg_r'])} R, t {_f(b[1]['eval']['all']['t'], '{:.2f}')}, "
                         f"verdict {b[1]['eval']['verdict']}).")
        doc = [k for k in res if "(doc)" in k]
        if doc:
            d0 = res[doc[0]]["eval"]["all"]
            lines.append(f"Règles « bougie seule » du PDF (BuBC/BeBC…) : win rate {_f(d0['wr'], '{:.0f} %')} mais avg RR {_f(d0['avg_r'])} après coûts — "
                         "la cible (extrême de la bougie) est petite face au stop : un taux de réussite élevé ne suffit pas.")
        lines.append("Filtres qui aident dans les deux périodes : " + (", ".join(good_f) if good_f else "aucun sur cet échantillon") + ".")
        mins = int(step.total_seconds() // 60)
        lines.append(f"Unité de temps du test : {mins} min. Les tests du site montrent que 1–5 min perdent presque toujours à cause des coûts ; privilégie 15 min et plus.")
        for x in lines:
            st.markdown(f"- {x}")
        st.markdown("### Les grandes leçons retenues (site maxmaserati.com, reformulées)")
        for x in ["Aucune bougie ni cassure ne gagne seule : le contexte décide (marche T3+, heure, bougie journalière).",
                  "Trader le 15 min en Asie et à New York matin ; 1–5 min perdent à cause des coûts.",
                  "Entrer à la clôture : les limites profondes sont les pires entrées.",
                  "Stops larges basés sur la volatilité : les stops de structure serrés sont touchés par le bruit.",
                  "Sortir la moitié à +0,5 R fait dépasser 60 % de réussite ; une cible fixe 1:2 seule ne dépasse pas 50 %.",
                  "Le MMPD est une porte de momentum : on va avec XP/XD, on ne joue pas le retournement des extrêmes."]:
            st.markdown(f"- {x}")
        st.markdown("### Statuts")
        st.markdown("".join(f"<div style='margin:4px 0'>{badge(k)} &nbsp; {v}</div>" for k, v in STATUS_FR.items()), unsafe_allow_html=True)
    # ------------------------------------------------------------ VERDICTS
    with tabs[1]:
        rows = verdict_rows(res, filt)
        c1, c2 = st.columns([2, 2])
        stf = c1.radio("Statut", ["Tous", "TRADE", "USE AS FILTER", "WATCH", "DON'T TRADE"], horizontal=True)
        fam = c2.radio("Famille", ["Toutes", "ICT", "MMM", "MMM doc", "Filtres"], horizontal=True)
        cards = []
        for name, r in res.items():
            e = r["eval"]
            if stf != "Tous" and e["verdict"] != stf:
                continue
            if fam not in ("Toutes",) and r["family"] != fam:
                continue
            a, o, f_ = e["all"], e["old"], e["fresh"]
            rules = r["rules"]
            rtxt = f"stop {rules['stop']} · objectif {'extrême bougie' if rules['tp'] == 'nat' else '1:' + str(rules['tp'])}" + \
                   (" · ½ à +0,5 R" if rules["half"] else "") + (" · journalière d'hier dans le sens" if rules.get("daily") else "")
            stats_line = (f"{a['n']} trades · WR {_f(o['wr'], '{:.0f}')} → {_f(f_['wr'], '{:.0f}')} % · avg RR {_f(o['avg_r'])} → {_f(f_['avg_r'])} · "
                          f"PF {_f(a['pf'], '{:.2f}')} · t {_f(o['t'], '{:.1f}')} / {_f(f_['t'], '{:.1f}')} · DD {_f(a['max_dd'], '{:.1f}')} R · "
                          f"{a['streak']} pertes de suite · hasard {_f(e['random'])}")
            cards.append((e["verdict"], r["family"], name, r["desc"], rtxt, stats_line))
        if fam in ("Toutes", "Filtres"):
            for f in filt:
                if stf != "Tous" and f["verdict"] != stf:
                    continue
                cards.append((f["verdict"], "Filtre", f["filtre"], "Ajouté à tous les setups : améliore-t-il l'avg RR dans les deux périodes ?",
                              f"testé sur {f['setups_testés']} setups", f"améliore l'ancien {f['améliore_ancien']} · le récent {f['améliore_récent']} · "
                              f"Δ avg RR moyen {f['delta_avg_R']:+.3f}"))
        _ord = {"TRADE": 0, "USE AS FILTER": 1, "WATCH": 2, "DON'T TRADE": 3}
        cards.sort(key=lambda c_: _ord.get(c_[0], 9))
        cols = st.columns(3)
        for k, (v, fm, name, desc, rtxt, sl) in enumerate(cards):
            c = STATUS_COL[v]
            cols[k % 3].markdown(
                f'<div class="card" style="border-left:6px solid {c}">{badge(v)} <span class="pill">{fm}</span>'
                f'<h4 style="margin-top:6px">{name}</h4><div>{desc}</div><div style="margin-top:4px"><i>{rtxt}</i></div>'
                f'<div style="margin-top:6px;background:#F2F4F8;border-radius:6px;padding:6px;font-family:monospace;font-size:0.8rem">{sl}</div></div>',
                unsafe_allow_html=True)
        if not cards:
            st.info("Aucun setup avec ce filtre.")
        with st.expander("Les 7 contrôles de preuve par setup"):
            chk = pd.DataFrame({n: r["eval"].get("checks", {}) for n, r in res.items()}).T
            if not chk.empty:
                _df(chk.map(lambda v: "✅" if v is True else "❌"))
    # ------------------------------------------------------- REJOUER UN SETUP
    with tabs[2]:
        name = st.selectbox("Setup à rejouer sur le graphique", list(res.keys()))
        tr = res[name]["trades"]
        if tr.empty:
            st.info("Aucun trade pour ce setup sur ces données.")
        else:
            k = st.slider("Trade affiché (fin de la fenêtre)", 1, len(tr), len(tr))
            end = int(min(len(df), tr.iloc[k - 1]["exit_i"] + 25))
            sub = df.iloc[max(0, end - 1500):end]
            off = max(0, end - 1500)
            trs = tr.copy()
            for col in ["i", "entry_i", "exit_i"]:
                trs[col] = trs[col] - off
            trs = trs[(trs.exit_i >= 0) & (trs.entry_i < len(sub))]
            a = analyze(sub, swing_n)
            m = analyze_mmm(sub, swing_n)
            win = min(window, len(sub))
            fig = ict_chart(a, window=win, show={**show, "ob": False, "fvg": False, "levels": False}, title=f"{name} — trades rejoués")
            fig = add_mmm_layer(fig, m, win, show)
            fig = add_bt_trades(fig, trs, len(sub) - win, label=name.split("·")[0].strip().split(" ")[-1][:1])
            _fig(fig, "bt_replay")
            if show.get("mmpd", True):
                _fig(mmpd_chart(m, win), "bt_mmpd")
            eq = go.Figure(go.Scatter(y=np.cumsum(tr["R"].values), mode="lines", line=dict(color="#1F4E9A", width=2)))
            eq.update_layout(**LAYOUT, height=260, title=dict(text="Courbe en R (après coûts)", font=dict(color="#000")))
            eq.add_vline(x=int((tr["time"] < cut).sum()), line=dict(color="#B85C00", dash="dot"),
                         annotation_text="ancien | récent", annotation_font=dict(color="#000"))
            _fig(eq, "bt_eq")
            show_tr = tr[["time", "dir", "entry", "stop", "target", "risk", "pts", "R", "exit", "session"]].copy()
            show_tr["time"] = show_tr["time"].dt.strftime("%d/%m/%y %H:%M")
            show_tr["R"] = show_tr["R"].round(2)
            _df(show_tr, hide_index=True)
    # --------------------------------------------------------------- GRILLE
    with tabs[3]:
        st.markdown("Toutes les combinaisons **setup × stop × objectif × session × ½ sortie** (≈ 2 000 lignes). "
                    "Plus on teste de combos, plus la chance en fait gagner : un combo choisi dans la grille doit viser **t ≥ 3**.")
        if st.button("▶ Calculer la grille complète"):
            st.session_state.grid_go = True
        if st.session_state.get("grid_go"):
            with st.spinner("Calcul de la grille…"):
                g = _grid(df, sig, sigs, ctx, cost, int(max_bars))
            c = st.columns(4)
            mn = c[0].number_input("Trades min", 10, 1000, 30, 10)
            only = c[1].checkbox("PASS uniquement (positif ancien ET récent, t ≥ 2)")
            setf = c[2].multiselect("Setups", sorted(g["setup"].unique()) if not g.empty else [])
            gg = g[g["trades"] >= mn]
            if only:
                gg = gg[(gg["avg_RR_ancien"] > 0) & (gg["avg_RR_récent"] > 0) & (gg["t"] >= 2)]
            if setf:
                gg = gg[gg["setup"].isin(setf)]
            pos = (g["avg_RR"] > 0).mean() * 100 if len(g) else 0
            st.markdown(f"**{len(g)}** combos avec ≥ 10 trades · **{pos:.1f} %** ont un avg RR > 0 après coûts · "
                        f"**{len(g[(g.avg_RR_ancien > 0) & (g.avg_RR_récent > 0) & (g.t >= 3)])}** passent ancien + récent + t ≥ 3.")
            _df(gg.sort_values("t", ascending=False), hide_index=True, height=520)
    # -------------------------------------------------------- NIVEAUX & ODDS
    with tabs[4]:
        st.markdown("Méthode du PDF Max Maserati : après une bougie **BC+ / BC− / AFs+ / AFs−** clôturée, la cible (extrême de la bougie signal) "
                    "est-elle touchée avant l'invalidation dans les 2 bougies suivantes ? Calculé sur **tes** données.")
        od = bt.candle_odds(df)
        by = st.radio("Regrouper par", ["session", "heure", "jour"], horizontal=True)
        tb = bt.odds_table(od, by)
        _df(tb.rename(columns={"Win": "Win %", "Invalid": "Invalid %", "Les_deux": "Les deux %", "gain_pts": "gain médian (pts)",
                               "risque_pts": "risque médian (pts)"}), hide_index=True, height=420)
        st.caption("Heures en heure de New York. Compare « gain médian » et « risque médian » : un win % élevé avec un gain bien plus petit que le risque perd après coûts.")
        st.markdown("#### Mur du momentum (séries de BC dans le même sens)")
        _df(bt.momentum_wall(df).rename(columns={"continue_pct": "continue au suivant (%)"}), hide_index=True)
        al = alignment(df)
        st.markdown("#### Alignement multi-UT actuel (tempête parfaite)")
        st.markdown(" · ".join(f"**{k}** {v}" for k, v in al["tf"].items()) +
                    f" → {al['count']} UT alignée(s) {'haussières' if al['dir'] == 1 else 'baissières' if al['dir'] == -1 else ''} "
                    f"(probabilité annoncée par le PDF : {al['prob_doc']} — à vérifier ici dans les backtests).")
    # --------------------------------------------------------- PROP & TAILLE
    with tabs[5]:
        name = st.selectbox("Setup", list(res.keys()), key="prop_setup")
        r = res[name]["trades"]["R"].values if not res[name]["trades"].empty else np.array([])
        c = st.columns(4)
        acc = c[0].number_input("Objectif de profit ($)", 500.0, 20000.0, 3000.0, 250.0)
        dd = c[1].number_input("Drawdown suiveur ($)", 500.0, 10000.0, 2500.0, 250.0)
        risk = c[2].number_input("Risque par trade ($)", 25.0, 2000.0, 250.0, 25.0)
        c[3].markdown(f"<div class='card'>Risque moyen du setup : <b>{_f(res[name]['eval']['all']['avg_risk'], '{:.1f}')} pts</b> "
                      f"= {_f(res[name]['eval']['all']['avg_risk'] * 2 if res[name]['eval']['all']['n'] else np.nan, '{:.0f}')} $ par MNQ</div>",
                      unsafe_allow_html=True)
        if len(r) < 10:
            st.info("Moins de 10 trades : pas de simulation possible.")
        else:
            mc = bt.prop_montecarlo(r, risk, acc, dd)
            m = st.columns(4)
            m[0].metric("Taux de réussite de l'évaluation", f"{mc['pass_rate']:.0f} %")
            m[1].metric("Taux d'échec", f"{mc['fail_rate']:.0f} %")
            m[2].metric("Non décidé (300 trades)", f"{mc['undecided']:.0f} %")
            m[3].metric("Trades médians pour passer", _f(mc["trades_to_pass"], "{:.0f}"))
            sizes = [50, 100, 150, 200, 250, 300, 400, 500, 750, 1000]
            tbl = []
            for s in sizes:
                x = bt.prop_montecarlo(r, s, acc, dd, n_sims=1200)
                tbl.append(dict(risque_par_trade=f"{s} $", contrats_MNQ=max(1, int(s / max(res[name]['eval']['all']['avg_risk'] * 2, 1))),
                                réussite=round(x["pass_rate"], 1), échec=round(x["fail_rate"], 1), trades_médians=x["trades_to_pass"]))
            tdf = pd.DataFrame(tbl)
            _df(tdf, hide_index=True)
            best = tdf.loc[tdf["réussite"].idxmax()]
            surv = tdf[tdf["échec"] <= 10]
            st.markdown(f"**Meilleure taille** pour passer : {best['risque_par_trade']} ({best['réussite']} %). "
                        f"**Taille de survie** (échec ≤ 10 %) : {surv.iloc[-1]['risque_par_trade'] if not surv.empty else 'aucune'}.")
            st.caption("Monte Carlo : les trades du backtest sont tirés au hasard 3 000 fois ; le drawdown suit le plus haut et se bloque à +100 $ (règle type Apex).")
    # --------------------------------------------------------------- MOTS
    with tabs[6]:
        st.markdown(STAIRCASE_SVG, unsafe_allow_html=True)
        st.markdown("""
| Mot | Sens dans la plateforme |
|---|---|
| **BC+ / BC−** | Clôture au-delà du plus haut / plus bas précédent |
| **AFs+ / AFs−** | Mèche qui prend la liquidité puis clôture à l'intérieur, près de l'extrême opposé |
| **C2+ / C2− · CI** | Clôture au-delà de la clôture précédente sans casser l'extrême · bougie intérieure |
| **GMC** | c1 → c2 BC → c3 laisse un vide ; ligne à l'open de c2, supprimée sur clôture au-delà |
| **T# · CDL/CDS · LD/SD** | Marches de tendance : T1 = flip, T2+ = continuations ; ★ à partir de T3 (setup Z) |
| **P# · R#** | Niveau cassé · creux/sommet du pullback = niveau protégé (où va le stop) |
| **BZ · ZBrk** | Boîte de session 18h / 02h / 09h30 · 1re clôture hors de la boîte |
| **Contraction / Expansion** | Boîte étroite (énergie stockée) / large par rapport à l'ATR |
| **Balance control** | Lignes 2/3 (acheteurs) et 1/3 (vendeurs) ; ligne épaisse = camp en contrôle |
| **vPOC** | Prix au plus gros volume dans la boîte (information) |
| **P · MP · BAL · MD · D** | Niveaux 87,5 · 75 · 50 · 25 · 12,5 % de la bougie, dans son sens |
| **MMPD · XP · XD** | Position 0–100 dans le range (27 / 9) · ≥ 80 · ≤ 20 |
| **E1 / C** | Entrée à la clôture (la meilleure dans les tests) |
| **X1** | Sortie stop / objectif uniquement |
| **ICT : MSS, OB, breaker, FVG, OTE** | Voir l'onglet Figures ICT (cours Warren) |
""")
    # ---------------------------------------------------------- MÉTHODE
    with tabs[7]:
        st.markdown(f"""
- **Données** : celles chargées dans la plateforme ({src_label}). Unité de temps {step}. Plus il y a de bougies, plus le verdict est fiable
  (le site travaille sur 3 ans de NQ 1 min + 10 mois de MNQ récents : importe un export TradingView pour t'en approcher).
- **Signal** sur bougie clôturée ; **entrée** à la clôture (E1), à l'ouverture suivante (règles du PDF) ou par limite (expire après 20 bougies,
  annulée si l'invalidation clôture avant).
- **Coût** : {cost:g} point déduit à chaque trade (1 pt = 0,2 R sur un stop de 5 pts, 0,02 R sur 50 pts).
- **Stop et objectif dans la même bougie** : le stop gagne. **½ sortie** à +0,5 R puis stop à l'entrée. Sortie forcée après {int(max_bars)} bougies.
- **Une position à la fois par setup**.
- **Périodes** : ancienne = 70 % des dates (construction), récente = 30 % (vérification hors échantillon).
- **Hasard** : pour chaque trade, entrée au marché sur une bougie aléatoire de la même session, même sens, même stop, même objectif.
- **7 contrôles** : avg RR > 0 et PF ≥ 1,3 · bat le hasard · t ≥ 2 · positif ancien ET récent · plateau de voisins (objectif/stop proches) ·
  majorité d'années positives · positif sans les 5 meilleurs trades.
- **Verdict** : TRADE si positif dans les deux périodes, ≥ 30 trades anciens et ≥ 10 récents, t ancien ≥ 2 et récent ≥ 1,5, et meilleur que le hasard ;
  WATCH si positif partout sans ces preuves ; DON'T TRADE sinon. Les filtres sont USE AS FILTER s'ils améliorent ≥ 60 % des setups dans les deux périodes.
""")
    # ---------------------------------------------------------- LIRE
    with tabs[8]:
        _read_numbers()


def _static_tabs(df):
    with st.expander("📖 Comment lire les chiffres (à lire avant de lancer)"):
        _read_numbers()


def _read_numbers():
    for k, v in READ_NUMBERS:
        safe = v.replace("$", "\\$")
        st.markdown(f"**{k}** — {safe}")
    st.markdown("#### Calculateur")
    c = st.columns(4)
    w = c[0].number_input("Trades gagnants", 0, 10000, 4)
    lo = c[1].number_input("Trades perdants", 0, 10000, 6)
    rr = c[2].number_input("Gain par trade gagnant (R)", 0.1, 20.0, 2.0, 0.1)
    cst = c[3].number_input("Coût par trade (R)", 0.0, 1.0, 0.0, 0.01)
    n = w + lo
    if n:
        net = w * rr - lo - n * cst
        pf = (w * rr) / (lo + n * cst) if (lo + n * cst) > 0 else float("inf")
        be = 1 / (1 + rr) * 100
        st.markdown(f"Résultat net **{net:+.2f} R** · avg RR **{net / n:+.3f}** · PF **{pf:.2f}** · win rate {w / n * 100:.0f} % "
                    f"(équilibre à {be:.1f} % pour un 1:{rr:g}).")
    st.markdown("#### Pertes consécutives à prévoir")
    c2 = st.columns(3)
    wr = c2[0].number_input("Win rate (%)", 1.0, 99.0, 40.0, 1.0)
    nt = c2[1].number_input("Nombre de trades", 10, 100000, 100, 10)
    rk = c2[2].number_input("Risque par trade ($)", 10.0, 10000.0, 200.0, 10.0)
    import math
    q = 1 - wr / 100
    streak = math.log(nt) / -math.log(q) if 0 < q < 1 else float("nan")
    p_k = {k: (1 - (1 - q ** k) ** max(nt - k + 1, 1)) * 100 for k in (5, 8, 10, 12)}
    st.markdown(f"Série de pertes **la plus longue attendue** sur {nt} trades à {wr:.0f} % : ≈ **{streak:.0f} pertes d'affilée** "
                f"→ prévoir au moins **{streak * rk:,.0f} $** de drawdown rien que sur cette série. "
                + " · ".join(f"P(au moins {k} de suite) ≈ {v:.0f} %" for k, v in p_k.items()))
    st.caption("Formule : série max ≈ ln(N) / −ln(1 − WR). Exemple de tes notes : 100 trades à 40 % → ≈ 9 pertes de suite possibles.")


STAIRCASE_SVG = """
<div class="card"><h4>L'escalier de tendance (dessiné automatiquement sur le graphique)</h4>
<svg viewBox="0 0 640 230" width="100%" style="max-width:760px;background:#FFFFFF">
 <style>.t{font:12px monospace;fill:#000}.p{font:12px monospace;fill:#C2185B;font-weight:700}.g{font:12px monospace;fill:#00796B;font-weight:700}</style>
 <line x1="20" y1="190" x2="620" y2="190" stroke="#C2185B" stroke-dasharray="5 4"/>
 <line x1="150" y1="150" x2="620" y2="150" stroke="#C2185B" stroke-dasharray="5 4"/>
 <line x1="300" y1="110" x2="620" y2="110" stroke="#C2185B" stroke-dasharray="5 4"/>
 <rect x="165" y="108" width="80" height="34" fill="rgba(0,121,107,0.18)"/>
 <rect x="320" y="68" width="80" height="34" fill="rgba(0,121,107,0.18)"/>
 <polyline points="20,200 55,180 75,195 120,140 150,150 175,125 195,138 215,122 235,135 250,110 290,92 310,112 330,82 350,96 370,80 390,92 410,66 450,56 480,70 520,40 600,20" fill="none" stroke="#000" stroke-width="2"/>
 <circle cx="75" cy="195" r="5" fill="#FFF" stroke="#000"/><text class="p" x="78" y="214">CDLx</text>
 <circle cx="250" cy="110" r="5" fill="#FFF" stroke="#000"/><text class="g" x="232" y="128">P1</text>
 <text class="p" x="200" y="96">LDx1 → T2</text>
 <circle cx="410" cy="66" r="6" fill="#C2185B"/><text class="p" x="355" y="52">LDx2 ★ → T3 = Z</text>
 <circle cx="150" cy="150" r="5" fill="#FFF" stroke="#000"/><text class="t" x="118" y="170">R1 (stop protégé)</text>
 <circle cx="310" cy="112" r="5" fill="#FFF" stroke="#000"/><text class="t" x="285" y="132">R2</text>
 <text class="t" x="20" y="225">T1 = flip · chaque clôture au-delà du P# suivant ajoute une marche · le setup Z se déclenche à T3+</text>
</svg></div>
"""


# ====================================================================== SCRIPTS
def render_scripts(src_label: str):
    st.title("📜 Scripts TradingView (Pine Script v6)")
    st.markdown("Six scripts — dont **Edge 5 Desk**, le poste de pilotage identique à la page Edge Desk — qui reproduisent dans TradingView les **dessins** et les **règles** de la plateforme — ICT (cours Warren) "
                "et lecture order flow inspirée du Max Maserati Model — plus une **stratégie de backtest** avec les mêmes statistiques.")
    rows = st.session_state.get("bt_rows")
    if rows:
        st.success(f"Le Word inclura les verdicts de ton dernier backtest ({st.session_state.get('bt_label', '')}).")
    else:
        st.info("Astuce : lance d'abord les backtests (page Backtests & Verdicts) pour que le Word contienne tes verdicts.")
    doc = build_docx(rows, st.session_state.get("bt_label", src_label))
    st.download_button("⬇️ Télécharger le document Word (tous les scripts + mode d'emploi)", doc, "Scripts_TradingView_ICT_MMM_MNQ.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.caption("Pour coller sans risque d'erreur de mise en forme, préfère les fichiers .pine individuels ci-dessous (texte brut).")
    for name, fname, kind, code, desc in SCRIPTS:
        st.markdown(f'<div class="card"><h4>{name}</h4><span class="pill">{kind}</span><div style="margin-top:6px">{desc}</div></div>',
                    unsafe_allow_html=True)
        c1, c2 = st.columns([1, 3])
        c1.download_button(f"⬇️ {fname}", code.encode("utf-8"), fname, "text/plain", key=f"dl_{fname}")
        with c2.expander("Voir le code"):
            st.code(code, language="javascript")
    st.markdown("""
#### Installer dans TradingView
1. Ouvre **MNQ1!** en **15 min** → **Pine Editor** → *Ouvrir* → *Nouvel indicateur* (ou *Nouvelle stratégie* pour Edge Lab).
2. Remplace tout le contenu par le script, **Enregistrer**, puis **Ajouter au graphique**.
3. Réglages (roue dentée) : sensibilité des swings, sessions, filtres. Edge Lab : onglet **Strategy Tester** + tableau de stats sur le graphique.

Les scripts ont été écrits pour Pine v6 et relus ligne à ligne, mais ils n'ont pas pu être compilés dans TradingView depuis la plateforme :
si l'éditeur signale une erreur, copie le message et la ligne indiquée.
""")
