"""Graphiques Plotly fond blanc / texte noir avec les annotations ICT."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .ict import Analysis, SESSIONS_BOXES

UP, DOWN = "#0B7A3E", "#B3261E"
LAYOUT = dict(
    template="plotly_white", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
    font=dict(color="#000000", size=12), margin=dict(l=10, r=70, t=40, b=30),
    hoverlabel=dict(bgcolor="#FFFFFF", font_color="#000000", bordercolor="#000000"),
    legend=dict(font=dict(color="#000000"), bgcolor="rgba(255,255,255,0.9)", orientation="h", y=1.04, x=0),
)


def _ticks(idx: pd.DatetimeIndex, start: int, n: int = 8):
    if len(idx) == 0:
        return [], []
    pos = np.linspace(0, len(idx) - 1, min(n, len(idx))).astype(int)
    fmt = "%d/%m %H:%M" if (idx[-1] - idx[0]) < pd.Timedelta(days=60) else "%d/%m/%y"
    return [int(p + start) for p in pos], [idx[p].strftime(fmt) for p in pos]


def ict_chart(a: Analysis, window: int = 250, show=None, trades=None, position=None,
              pending=None, title: str = "", height: int = 640) -> go.Figure:
    show = show or {}
    df = a.df
    N = len(df)
    start = max(0, N - window)
    view = df.iloc[start:]
    x = np.arange(start, N)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=x, open=view["open"], high=view["high"], low=view["low"], close=view["close"],
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
        decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN),
        name="MNQ", text=[t.strftime("%a %d/%m %H:%M NY") for t in view.index], hoverinfo="x+y+text",
        showlegend=False))
    x_end = N + 8

    # Sessions (heure NY)
    if show.get("sessions", True):
        hrs = view.index.hour * 60 + view.index.minute
        for name, h1, m1, h2, m2, col in SESSIONS_BOXES:
            mask = (hrs >= h1 * 60 + m1) & (hrs < h2 * 60 + m2)
            if not mask.any():
                continue
            runs, prev = [], None
            for k, v in zip(x, mask):
                if v and prev is None:
                    prev = k
                if not v and prev is not None:
                    runs.append((prev, k - 1)); prev = None
            if prev is not None:
                runs.append((prev, x[-1]))
            for r0, r1 in runs[-12:]:
                fig.add_vrect(x0=r0 - 0.5, x1=r1 + 0.5, fillcolor=col, line_width=0, layer="below")

    # Range / EQ / OTE
    if show.get("range", True) and a.rng:
        r = a.rng
        x0 = max(start, min(r["hi_i"], r["lo_i"]))
        for y, lab, dash in [(r["hi"], "Range High", "solid"), (r["lo"], "Range Low", "solid"), (r["eq"], "EQ 0.5", "dot")]:
            fig.add_shape(type="line", x0=x0, x1=x_end, y0=y, y1=y, line=dict(color="#1F4E9A", width=1.2, dash=dash))
            fig.add_annotation(x=x_end, y=y, text=lab, showarrow=False, xanchor="left", font=dict(color="#1F4E9A", size=10))
        fig.add_shape(type="rect", x0=x0, x1=x_end, y0=r["ote_bottom"], y1=r["ote_top"],
                      fillcolor="rgba(184,92,0,0.10)", line=dict(color="#B85C00", width=0.5), layer="below")
        fig.add_annotation(x=x_end, y=r["ote_705"], text="OTE 0.705", showarrow=False, xanchor="left",
                           font=dict(color="#B85C00", size=10))

    # Orderblocks & breakers
    if show.get("ob", True):
        for ob in [o for o in a.obs if o["formed_i"] >= start][-(3 if show.get("lite") else 6):]:
            if ob["breaker"]:
                if not show.get("breaker", True) or ob["breaker_status"] == "invalidé":
                    continue
                col = "rgba(179,38,30,0.16)" if ob["dir"] == 1 else "rgba(11,122,62,0.16)"
                lab = "Breaker ↓" if ob["dir"] == 1 else "Breaker ↑"
                line = DOWN if ob["dir"] == 1 else UP
            else:
                col = "rgba(11,122,62,0.14)" if ob["dir"] == 1 else "rgba(179,38,30,0.14)"
                lab = ("OB+ " if ob["dir"] == 1 else "OB− ") + ob["status"]
                line = UP if ob["dir"] == 1 else DOWN
            end = ob.get("breaker_invalid_i") or x_end
            fig.add_shape(type="rect", x0=ob["i"] - 0.4, x1=end, y0=ob["bottom"], y1=ob["top"],
                          fillcolor=col, line=dict(color=line, width=0.8), layer="below")
            fig.add_annotation(x=ob["i"], y=ob["top"], text=lab, showarrow=False, yanchor="bottom",
                               xanchor="left", font=dict(color=line, size=9))

    # FVG
    if show.get("fvg", True):
        open_g = [g for g in a.fvgs if g["i"] >= start and g["status"] != "comblé"][-(2 if show.get("lite") else 5):]
        for g in open_g:
            fig.add_shape(type="rect", x0=g["i"] - 0.4, x1=x_end, y0=g["bottom"], y1=g["top"],
                          fillcolor="rgba(31,78,154,0.10)", line=dict(color="#1F4E9A", width=0.5, dash="dot"),
                          layer="below")
            fig.add_annotation(x=g["i"], y=g["top"], text="FVG", showarrow=False, yanchor="bottom",
                               font=dict(color="#1F4E9A", size=9))

    # Structure
    if show.get("structure", True):
        for ev in [e for e in a.events if e["i"] >= start][-(4 if show.get("lite") else 8):]:
            col = UP if ev["dir"] == 1 else DOWN
            fig.add_shape(type="line", x0=max(ev["swing_i"], start), x1=ev["i"], y0=ev["level"], y1=ev["level"],
                          line=dict(color=col, width=1, dash="dash"))
            fig.add_annotation(x=(max(ev["swing_i"], start) + ev["i"]) / 2, y=ev["level"], text=ev["kind"],
                               showarrow=False, yanchor="bottom" if ev["dir"] == 1 else "top",
                               font=dict(color=col, size=10, family="Arial Black"))

    # Sweeps
    if show.get("sweeps", True):
        sw = [s for s in a.sweeps if s["i"] >= start][-(3 if show.get("lite") else 6):]
        if sw:
            fig.add_trace(go.Scatter(
                x=[s["i"] for s in sw],
                y=[df["low"].iloc[s["i"]] - 3 if s["dir"] == 1 else df["high"].iloc[s["i"]] + 3 for s in sw],
                mode="markers+text", marker=dict(symbol=["triangle-up" if s["dir"] == 1 else "triangle-down" for s in sw],
                                                 color=[UP if s["dir"] == 1 else DOWN for s in sw], size=10),
                text=["SSL pris" if s["dir"] == 1 else "BSL pris" for s in sw],
                textposition=["bottom center" if s["dir"] == 1 else "top center" for s in sw],
                textfont=dict(color="#000000", size=9), name="Sweeps (SFP)", hoverinfo="text"))

    # Niveaux clés
    if show.get("levels", True):
        palette = {"PDH": "#6A1B9A", "PDL": "#6A1B9A", "Monday High": "#B85C00", "Monday Low": "#B85C00",
                   "Midnight Open": "#000000", "Weekly Open": "#000000", "Asia High": "#5A5F6B",
                   "Asia Low": "#5A5F6B", "London High": "#1F4E9A", "London Low": "#1F4E9A",
                   "PWH": "#6A1B9A", "PWL": "#6A1B9A", "NY Open 9:30": "#B85C00"}
        lo_v, hi_v = view["low"].min(), view["high"].max()
        alt = {"PDL", "Monday Low", "Asia Low", "London Low", "PWL", "NY Open 9:30"}
        span = hi_v - lo_v
        for k, v in a.levels.items():
            if lo_v - span * 0.3 <= v <= hi_v + span * 0.3:
                fig.add_shape(type="line", x0=start, x1=x_end, y0=v, y1=v,
                              line=dict(color=palette.get(k, "#000"), width=0.8, dash="longdash"))
                fig.add_annotation(x=start + (len(view) * 0.18 if k in alt else 0), y=v, text=k, showarrow=False,
                                   xanchor="left", yanchor="bottom", font=dict(color=palette.get(k, "#000"), size=9),
                                   bgcolor="rgba(255,255,255,0.85)")
        if a.profile and show.get("poc", True):
            fig.add_shape(type="line", x0=start, x1=x_end, y0=a.profile["poc"], y1=a.profile["poc"],
                          line=dict(color="#B85C00", width=1.5))
            fig.add_annotation(x=x_end, y=a.profile["poc"], text="POC J-1", showarrow=False, xanchor="left",
                               font=dict(color="#B85C00", size=10))

    # Trades passés
    if trades:
        for t in trades:
            try:
                ei = df.index.get_indexer([t["entry_time"]], method="nearest")[0]
                xi = df.index.get_indexer([t["exit_time"]], method="nearest")[0]
            except Exception:
                continue
            if xi < start:
                continue
            col = UP if t["pnl"] >= 0 else DOWN
            fig.add_trace(go.Scatter(x=[ei, xi], y=[t["entry"], t["exit"]], mode="lines+markers",
                                     line=dict(color=col, width=2, dash="dot"),
                                     marker=dict(size=8, symbol=["circle", "x"], color=col),
                                     showlegend=False, hoverinfo="text",
                                     text=[f"{t['side']} @ {t['entry']}", f"Sortie {t['exit']} ({t['pnl']:+.0f}$)"]))

    # Position ouverte
    if position:
        for y, lab, col in [(position["entry"], f"Entrée {position['side']}", "#000000"),
                            (position.get("sl"), "SL", DOWN), (position.get("tp"), "TP", UP)]:
            if y:
                fig.add_shape(type="line", x0=start, x1=x_end, y0=y, y1=y, line=dict(color=col, width=2))
                fig.add_annotation(x=x_end, y=y, text=f"{lab} {y:.2f}", showarrow=False, xanchor="left",
                                   font=dict(color=col, size=11, family="Arial Black"))
    for p in pending or []:
        fig.add_shape(type="line", x0=start, x1=x_end, y0=p["price"], y1=p["price"],
                      line=dict(color="#1F4E9A", width=1.5, dash="dash"))
        fig.add_annotation(x=x_end, y=p["price"], text=f"Limite {p['side']} {p['price']:.2f}", showarrow=False,
                           xanchor="left", font=dict(color="#1F4E9A", size=10))

    tv, tt = _ticks(view.index, start)
    fig.update_layout(**LAYOUT, height=height, title=dict(text=title, font=dict(color="#000000", size=15)),
                      xaxis_rangeslider_visible=False, dragmode="pan")
    fig.update_xaxes(tickvals=tv, ticktext=tt, showgrid=True, gridcolor="#E6E8EE", color="#000000",
                     range=[start - 1, x_end + 12])
    fig.update_yaxes(side="right", showgrid=True, gridcolor="#E6E8EE", color="#000000", tickformat=".2f")
    return fig


def equity_chart(trades: list, start_balance: float) -> go.Figure:
    eq = [start_balance]
    for t in trades:
        eq.append(eq[-1] + t["pnl"])
    fig = go.Figure(go.Scatter(y=eq, mode="lines+markers", line=dict(color="#1F4E9A", width=2),
                               marker=dict(size=5, color="#1F4E9A"), name="Capital"))
    fig.add_hline(y=start_balance, line=dict(color="#5A5F6B", dash="dot"))
    fig.update_layout(**LAYOUT, height=300, title=dict(text="Courbe de capital (compte fictif)", font=dict(color="#000")))
    fig.update_xaxes(title="Trade n°", color="#000000", gridcolor="#E6E8EE")
    fig.update_yaxes(title="$", color="#000000", gridcolor="#E6E8EE")
    return fig


def bar_chart(labels, values, title, color="#1F4E9A") -> go.Figure:
    cols = [("#0B7A3E" if v >= 0 else "#B3261E") for v in values] if color == "pnl" else color
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=cols, text=[f"{v:,.0f}" for v in values],
                           textposition="outside", textfont=dict(color="#000000")))
    fig.update_layout(**LAYOUT, height=300, title=dict(text=title, font=dict(color="#000")))
    fig.update_xaxes(color="#000000"); fig.update_yaxes(color="#000000", gridcolor="#E6E8EE")
    return fig


# ======================================================================
# Couche MMM : dessins automatiques (boussole des bougies, escalier T#/P#/R#,
# GMC, boîtes de session + balance control + vPOC, zone de pullback, niveaux protégés)
PINK, TEAL = "#C2185B", "#00796B"


def add_mmm_layer(fig: go.Figure, m, window: int = 250, show=None) -> go.Figure:
    show = show or {}
    if m is None or m.types is None:
        return fig
    df = m.df
    N = len(df)
    start = max(0, N - window)
    x_end = N + 8
    h, l = df["high"].values, df["low"].values
    span = float(df["high"].iloc[start:].max() - df["low"].iloc[start:].min()) or 1.0
    off = span * 0.012

    # Boîtes de session (zone engine)
    if show.get("mmm_boxes", True):
        for bx in [b for b in m.boxes if b["s"] >= start][-(2 if show.get("lite") else 6):]:
            x1 = bx["brk_i"] if bx["brk_i"] is not None else x_end
            fig.add_shape(type="rect", x0=bx["s"] - 0.4, x1=x1, y0=bx["bot"], y1=bx["top"],
                          fillcolor="rgba(0,121,107,0.07)", line=dict(color=TEAL, width=1), layer="below")
            for y, col, side in [(bx["third_hi"], UP, 1), (bx["third_lo"], DOWN, -1)]:
                fig.add_shape(type="line", x0=bx["s"], x1=x1, y0=y, y1=y,
                              line=dict(color=col, width=2.5 if bx["control"] == side else 0.8))
            fig.add_shape(type="line", x0=bx["s"], x1=x1, y0=bx["vpoc"], y1=bx["vpoc"], line=dict(color="#5A5F6B", width=1.2))
            fig.add_annotation(x=bx["s"], y=bx["top"], text=f"BZ {bx['name']} · {bx['kind']}", showarrow=False,
                               xanchor="left", yanchor="bottom", font=dict(color=TEAL, size=9), bgcolor="rgba(255,255,255,0.85)")
            if bx["brk_i"] is not None:
                yb = h[bx["brk_i"]] + off if bx["brk_dir"] == 1 else l[bx["brk_i"]] - off
                fig.add_annotation(x=bx["brk_i"], y=yb, text="ZBrk▲" if bx["brk_dir"] == 1 else "ZBrk▼", showarrow=False,
                                   font=dict(color=UP if bx["brk_dir"] == 1 else DOWN, size=9, family="Arial Black"))

    # Escalier de tendance
    if show.get("mmm_stairs", True):
        st = [s for s in m.steps if s["i"] >= start][-(5 if show.get("lite") else 8):]
        for s in st:
            col = UP if s["dir"] == 1 else DOWN
            fig.add_shape(type="line", x0=max(s["p_i"], start), x1=s["i"], y0=s["p_level"], y1=s["p_level"],
                          line=dict(color=PINK, width=1, dash="dash"))
            yl = h[s["i"]] + 2.2 * off if s["dir"] == 1 else l[s["i"]] - 2.2 * off
            star = " ★" if s["T"] >= 3 else ""
            fig.add_annotation(x=s["i"], y=yl, text=f"<b>{s['label']}{star}</b> T{s['T']}", showarrow=False,
                               font=dict(color=PINK if s["T"] >= 3 else col, size=10), bgcolor="rgba(255,255,255,0.85)")
            if s["r_i"] >= start:
                fig.add_trace(go.Scatter(x=[s["r_i"]], y=[s["r_level"]], mode="markers+text",
                                         marker=dict(symbol="circle-open", size=9, color="#000", line=dict(width=1.5)),
                                         text=[f"R{s['T'] - 1}" if s["T"] > 1 else "T1"],
                                         textposition="bottom center" if s["dir"] == 1 else "top center",
                                         textfont=dict(color="#000", size=9), showlegend=False, hoverinfo="skip"))
        if st:
            s = st[-1]
            fig.add_shape(type="line", x0=s["r_i"], x1=x_end, y0=s["r_level"], y1=s["r_level"],
                          line=dict(color=PINK, width=1.5, dash="dot"))
            fig.add_annotation(x=x_end, y=s["r_level"], text=f"Niveau protégé {'SL s' if s['dir'] == 1 else 'SH s'}",
                               showarrow=False, xanchor="left", font=dict(color=PINK, size=10))

    # eBlock (derrière un flip T1) / iBlock (derrière une continuation T2+), supprimés à la clôture au-delà
    if show.get("mmm_stairs", True) and getattr(m, "blocks", None):
        vlo, vhi = float(df["low"].iloc[start:].min()), float(df["high"].iloc[start:].max())
        vis_b = [b for b in m.blocks if b["formed_i"] >= start and b["end_i"] is None
                 and b["bottom"] >= vlo - 0.1 * span and b["top"] <= vhi + 0.1 * span]
        for b in vis_b[-(2 if show.get("lite") else 5):]:
            col = "rgba(11,122,62,0.10)" if b["dir"] == 1 else "rgba(179,38,30,0.10)"
            fig.add_shape(type="rect", x0=b["i"] - 0.4, x1=x_end, y0=b["bottom"], y1=b["top"], fillcolor=col,
                          line=dict(color=PINK, width=0.6, dash="dot"), layer="below")
            fig.add_annotation(x=x_end, y=b["top"] if b["dir"] == -1 else b["bottom"], text=b["kind"], showarrow=False,
                               xanchor="left", font=dict(color=PINK, size=9))

    # GMC
    if show.get("mmm_gmc", True):
        for g in [g for g in m.gmc if g["i"] >= start][-(2 if show.get("lite") else 6):]:
            col = UP if g["dir"] == 1 else DOWN
            x1 = g["deleted_i"] if g["deleted_i"] is not None else x_end
            fig.add_shape(type="line", x0=g["i"] - 1, x1=x1, y0=g["open_line"], y1=g["open_line"],
                          line=dict(color=col, width=1.6, dash="dashdot"))
            fig.add_shape(type="rect", x0=g["i"] - 1.4, x1=g["i"] - 0.6, y0=g["void_bot"], y1=g["void_top"],
                          fillcolor="rgba(194,24,91,0.12)", line=dict(width=0))
            fig.add_annotation(x=g["i"], y=g["open_line"], text=f"GMC{'▲' if g['dir'] == 1 else '▼'} c3 {g['c3']}"
                               + (" · AFs contre" if g["afs_against"] else ""), showarrow=False, xanchor="left",
                               yanchor="top" if g["dir"] == 1 else "bottom", font=dict(color=col, size=9))

    # Zone de pullback
    if show.get("mmm_pb", True) and m.pb and m.pb["i"] >= start:
        p = m.pb
        fig.add_shape(type="rect", x0=p["i"] - 0.4, x1=x_end, y0=p["bot"], y1=p["top"],
                      fillcolor="rgba(184,92,0,0.13)", line=dict(color="#B85C00", width=0.6, dash="dot"), layer="below")
        fig.add_annotation(x=x_end, y=(p["top"] + p["bot"]) / 2, text=f"Pullback {p['label']}", showarrow=False,
                           xanchor="left", font=dict(color="#B85C00", size=9))

    # Boussole des bougies (dernières 40)
    if show.get("mmm_candles", True):
        idx = [i for i in range(max(start, N - 40), N) if m.types[i] in ("BC+", "BC−", "AFs+", "AFs−", "CI")]
        if idx:
            ys = [h[i] + off if m.types[i] in ("BC+", "AFs+", "CI") else l[i] - off for i in idx]
            cols = [UP if m.types[i].endswith("+") else (DOWN if m.types[i].endswith("−") else "#5A5F6B") for i in idx]
            fig.add_trace(go.Scatter(x=idx, y=ys, mode="text", text=[m.types[i] for i in idx],
                                     textfont=dict(color=cols, size=8), showlegend=False, hoverinfo="skip"))
    return fig


def mmpd_chart(m, window: int = 250, height: int = 170) -> go.Figure:
    df = m.df
    N = len(df)
    start = max(0, N - window)
    x = np.arange(start, N)
    lc, lo = m.mmpd27
    fc, fo = m.mmpd9
    fig = go.Figure()
    fig.add_hrect(y0=80, y1=100, fillcolor="rgba(11,122,62,0.10)", line_width=0)
    fig.add_hrect(y0=0, y1=20, fillcolor="rgba(179,38,30,0.10)", line_width=0)
    fig.add_trace(go.Scatter(x=x, y=lc[start:], name="MMPD 27 (c)", line=dict(color=TEAL, width=1.8)))
    fig.add_trace(go.Scatter(x=x, y=lo[start:], name="MMPD 27 (o)", line=dict(color=PINK, width=1.2, dash="dash")))
    fig.add_trace(go.Scatter(x=x, y=fc[start:], name="MMPD 9", line=dict(color="#5A5F6B", width=0.8)))
    for y, t in [(80, "XP 80 · longs"), (50, "50"), (20, "XD 20 · shorts")]:
        fig.add_hline(y=y, line=dict(color="#000", width=0.6, dash="dot"),
                      annotation_text=t, annotation_font=dict(color="#000", size=9), annotation_position="right")
    tv, tt = _ticks(df.index[start:], start)
    fig.update_layout(**{**LAYOUT, "margin": dict(l=10, r=150, t=10, b=25)}, height=height, showlegend=True)
    fig.update_xaxes(tickvals=tv, ticktext=tt, color="#000", range=[start - 1, N + 8 + 12], gridcolor="#E6E8EE")
    fig.update_yaxes(range=[0, 100], side="right", color="#000", gridcolor="#E6E8EE")
    return fig


def add_bt_trades(fig: go.Figure, trades: pd.DataFrame, start: int, label: str = "M") -> go.Figure:
    """Trace les trades d'un backtest : entrée, stop, objectif, sortie (étiquettes M1T1, M1T2…)."""
    if trades is None or trades.empty:
        return fig
    for k, t in enumerate(trades.itertuples(), 1):
        if t.exit_i < start:
            continue
        col = UP if t.R > 0 else DOWN
        x0, x1 = max(t.entry_i, start), t.exit_i
        fig.add_shape(type="line", x0=x0, x1=x1 + 0.5, y0=t.entry, y1=t.entry, line=dict(color="#000", width=1.2))
        fig.add_shape(type="line", x0=x0, x1=x1 + 0.5, y0=t.stop, y1=t.stop, line=dict(color=DOWN, width=1, dash="dot"))
        fig.add_shape(type="line", x0=x0, x1=x1 + 0.5, y0=t.target, y1=t.target, line=dict(color=UP, width=1, dash="dot"))
        fig.add_annotation(x=x0, y=t.entry, text=f"{label}T{k} {t.R:+.2f}R", showarrow=False, xanchor="right",
                           font=dict(color=col, size=9, family="Arial Black"), bgcolor="rgba(255,255,255,0.85)")
    return fig


# ======================================================================
# Edge 5 Desk : graphique des trades (lignes M#T# comme sur TradingView)
def edge_chart(res, window: int = 220, title: str = "", height: int = 640, mmm=None, show=None) -> go.Figure:
    df = res.df
    N = len(df)
    start = max(0, N - window)
    view = df.iloc[start:]
    x = np.arange(start, N)
    x_end = N + 8
    fig = go.Figure(go.Candlestick(
        x=x, open=view["open"], high=view["high"], low=view["low"], close=view["close"],
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP), decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN),
        text=[t.strftime("%a %d/%m %H:%M NY") for t in view.index], hoverinfo="x+y+text", showlegend=False))
    if mmm is not None:
        add_mmm_layer(fig, mmm, window, {**(show or {}), "lite": True, "mmm_candles": False})
    tr = res.trades
    items = []
    if tr is not None and not tr.empty:
        items += [dict(r, live=False) for r in tr[tr["exit_i"] >= start].tail(14).to_dict("records")]
    items += [dict(t, exit_i=N - 1, live=True) for t in res.open_trades]
    for t in items:
        x0, x1 = t["entry_i"], (x_end if t["live"] else t["exit_i"])
        stop0 = t.get("init_stop", t["stop"])
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=t["entry"], y1=stop0, fillcolor="rgba(179,38,30,0.10)", line=dict(width=0), layer="below")
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=t["entry"], y1=t["tp"], fillcolor="rgba(11,122,62,0.08)", line=dict(width=0), layer="below")
        for y, col, dash, w in [(t["entry"], "#000000", "solid", 1.2), (stop0, DOWN, "solid", 1.2),
                                (t.get("half_px"), "#1F4E9A", "dot", 1.0), (t["tp"], UP, "solid", 1.4)]:
            if y is not None and not (isinstance(y, float) and np.isnan(y)):
                fig.add_shape(type="line", x0=x0, x1=x1, y0=y, y1=y, line=dict(color=col, width=w, dash=dash))
        if t.get("half_done") and t["live"]:
            fig.add_shape(type="line", x0=x0, x1=x1, y0=t["entry"], y1=t["entry"], line=dict(color=DOWN, width=2, dash="dash"))
        if t["live"]:
            txt = f"<b>{t['label']}</b> {'LONG' if t['dir'] == 1 else 'SHORT'} ouvert · SL {t['stop']:.2f} · ½ {t['half_px'] or 0:.2f} · TP {t['tp']:.2f}"
            col = "#1F4E9A"
        else:
            txt = f"<b>{t['label']}</b> {t['reason']} | {t['usd']:+,.0f} $ ({t['pts']:+.1f} pts)"
            col = UP if t["R"] > 0 else DOWN
        fig.add_annotation(x=x1, y=t["tp"], text=txt, showarrow=False, xanchor="right" if not t["live"] else "left",
                           yanchor="bottom" if t["dir"] == 1 else "top", font=dict(color=col, size=10), bgcolor="rgba(255,255,255,0.9)")
        fig.add_trace(go.Scatter(x=[x0], y=[t["entry"]], mode="markers", marker=dict(size=9, color=UP if t["dir"] == 1 else DOWN,
                                 symbol="triangle-up" if t["dir"] == 1 else "triangle-down"), showlegend=False, hoverinfo="skip"))
    for p in res.pending:
        if p["i"] >= start:
            fig.add_shape(type="line", x0=p["i"], x1=x_end, y0=p["limit"], y1=p["limit"], line=dict(color="#1F4E9A", width=1.5, dash="dash"))
            fig.add_annotation(x=x_end, y=p["limit"], text=f"M4 limite {p['limit']:.2f}", showarrow=False, xanchor="left",
                               font=dict(color="#1F4E9A", size=10))
    tv, tt = _ticks(view.index, start)
    fig.update_layout(**LAYOUT, height=height, title=dict(text=title, font=dict(color="#000000", size=15)),
                      xaxis_rangeslider_visible=False, dragmode="pan")
    fig.update_xaxes(tickvals=tv, ticktext=tt, showgrid=True, gridcolor="#E6E8EE", color="#000000", range=[start - 1, x_end + 30])
    fig.update_yaxes(side="right", showgrid=True, gridcolor="#E6E8EE", color="#000000", tickformat=".2f")
    return fig
