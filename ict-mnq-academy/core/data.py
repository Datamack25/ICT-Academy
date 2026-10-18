"""Données de marché : Yahoo Finance (MNQ=F / NQ=F), import CSV, données démo."""
from __future__ import annotations

import io
import re

import numpy as np
import pandas as pd
import streamlit as st

NY_TZ = "America/New_York"

# Spécifications contrat Micro E-mini Nasdaq-100 (CME)
MNQ_SPEC = {"symbol": "MNQ", "point_value": 2.0, "tick_size": 0.25, "tick_value": 0.50}
NQ_SPEC = {"symbol": "NQ", "point_value": 20.0, "tick_size": 0.25, "tick_value": 5.0}

# Limites Yahoo sur l'historique intraday
INTERVAL_MAX_PERIOD = {
    "1m": "7d", "2m": "60d", "5m": "60d", "15m": "60d", "30m": "60d",
    "60m": "730d", "1h": "730d", "1d": "10y", "1wk": "10y",
}
PERIOD_CHOICES = {
    "1m": ["1d", "5d", "7d"],
    "5m": ["5d", "1mo", "60d"],
    "15m": ["5d", "1mo", "60d"],
    "30m": ["1mo", "60d"],
    "1h": ["1mo", "3mo", "6mo", "1y", "2y"],
    "1d": ["6mo", "1y", "2y", "5y"],
}


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns=str.lower)
    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep].copy()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df.dropna(subset=["open", "high", "low", "close"])
    idx = pd.to_datetime(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert(NY_TZ)
    df.index.name = "time"
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.astype(float)


@st.cache_data(ttl=60, show_spinner=False)
def load_yahoo(ticker: str, interval: str, period: str) -> pd.DataFrame:
    """Télécharge les bougies Yahoo (différé ~10-15 min sur les futures)."""
    import yfinance as yf

    df = yf.download(ticker, interval=interval, period=period, progress=False,
                     auto_adjust=False, prepost=True, threads=False)
    return _clean(df)


def load_market(ticker: str, interval: str, period: str):
    """Essaie MNQ=F puis NQ=F (même prix) ; renvoie (df, source, message)."""
    tried = [ticker] + [t for t in ["MNQ=F", "NQ=F"] if t != ticker]
    last_err = ""
    for t in tried:
        try:
            df = load_yahoo(t, interval, period)
            if not df.empty:
                msg = "" if t == ticker else f"{ticker} indisponible, repli sur {t} (même cotation)."
                return df, t, msg
        except Exception as e:  # réseau, quota Yahoo...
            last_err = str(e)
    return pd.DataFrame(), "", (f"Yahoo Finance n'a renvoyé aucune donnée ({last_err or 'réponse vide'}). "
                           "Réessaie dans un instant, change d'unité de temps, ou utilise « Démo hors-ligne » / « Fichier CSV ».")


def demo_data(n_bars: int = 2000, interval_min: int = 15, seed: int = 7, start_price: float = 21000.0) -> pd.DataFrame:
    """Série synthétique réaliste (tendances + ranges + mèches) — mode hors-ligne / démo uniquement."""
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.now(tz=NY_TZ).floor(f"{interval_min}min")
    idx = pd.date_range(end=end, periods=n_bars * 2, freq=f"{interval_min}min")
    idx = idx[idx.dayofweek < 5][-n_bars:]
    regime = np.repeat(rng.choice([-1, 0, 0, 1], size=n_bars // 60 + 1), 60)[:n_bars]
    hours = idx.hour + idx.minute / 60
    vol = np.where((hours >= 9.5) & (hours < 11.5), 2.2, np.where((hours >= 2) & (hours < 5), 1.5, 0.8))
    ret = regime * 0.00012 + rng.standard_t(4, n_bars) * 0.0009 * vol
    close = start_price * np.exp(np.cumsum(ret))
    open_ = np.concatenate([[start_price], close[:-1]])
    wick = np.abs(rng.normal(0, 0.0008, n_bars)) * close * vol
    high = np.maximum(open_, close) + wick * rng.random(n_bars)
    low = np.minimum(open_, close) - wick * rng.random(n_bars)
    volume = (rng.gamma(2, 900, n_bars) * vol).round()
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)
    df.index.name = "time"
    return df.round(2)


# --------------------------------------------------------------------- CSV
COLUMN_ALIASES = {
    "time": ["time", "date", "datetime", "timestamp", "date/heure", "heure", "gmt time", "local time", "date_time"],
    "open": ["open", "ouverture", "o", "open price"],
    "high": ["high", "haut", "plus haut", "h", "high price", "max"],
    "low": ["low", "bas", "plus bas", "l", "low price", "min"],
    "close": ["close", "clôture", "cloture", "c", "last", "close price", "dernier", "adj close"],
    "volume": ["volume", "vol", "v", "volume total"],
}

TRADE_HINTS = ["pnl", "p&l", "profit", "entry", "exit", "entrée", "sortie", "side", "sens", "qty",
               "quantity", "buy price", "sell price", "boughttimestamp", "soldtimestamp", "résultat"]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower().replace("_", " "))


def read_csv_any(uploaded) -> pd.DataFrame:
    raw = uploaded.getvalue() if hasattr(uploaded, "getvalue") else uploaded
    text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    first = text.splitlines()[0] if text else ""
    sep = ";" if first.count(";") > first.count(",") else ("\t" if first.count("\t") > first.count(",") else ",")
    df = pd.read_csv(io.StringIO(text), sep=sep)
    # décimales françaises
    for c in df.columns:
        if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            s = df[c].astype(str).str.replace(" ", "").str.strip()
            if s.str.match(r"^-?[\d\s]+(,\d+)?$").mean() > 0.8 and s.str.contains(",").any():
                df[c] = pd.to_numeric(s.str.replace(" ", "").str.replace(",", "."), errors="coerce")
    return df


def detect_csv_kind(df: pd.DataFrame) -> str:
    cols = [_norm(c) for c in df.columns]
    found = {k: any(c in v for c in cols) for k, v in COLUMN_ALIASES.items()}
    if found["open"] and found["high"] and found["low"] and found["close"]:
        return "ohlc"
    if any(any(h in c for h in TRADE_HINTS) for c in cols):
        return "trades"
    return "generic"


def csv_to_ohlc(df: pd.DataFrame, assume_tz: str = NY_TZ) -> pd.DataFrame:
    mapping = {}
    for c in df.columns:
        n = _norm(c)
        for k, aliases in COLUMN_ALIASES.items():
            if n in aliases and k not in mapping.values():
                mapping[c] = k
                break
    out = df.rename(columns=mapping)
    if "time" in out.columns:
        t = out["time"]
        if pd.api.types.is_numeric_dtype(t) and t.median() > 1e9:  # epoch (TradingView)
            idx = pd.to_datetime(t, unit="s" if t.median() < 1e11 else "ms", utc=True)
        else:
            ts = t.astype(str)
            first = pd.to_numeric(ts.str.extract(r"^(\d{1,2})[/.]")[0], errors="coerce")
            second = pd.to_numeric(ts.str.extract(r"^\d{1,2}[/.](\d{1,2})[/.]")[0], errors="coerce")
            dayfirst = bool(first.notna().any() and (first.max() > 12 or second.max() <= 12))  # format FR par défaut
            idx = pd.to_datetime(ts, errors="coerce", dayfirst=dayfirst)
            if idx.isna().mean() > 0.5:
                idx = pd.to_datetime(ts, errors="coerce", dayfirst=not dayfirst, format="mixed")
        out.index = idx
        out = out[~out.index.isna()]
        if getattr(out.index, "tz", None) is None:
            out.index = out.index.tz_localize(assume_tz, ambiguous="NaT", nonexistent="shift_forward")
    else:
        out.index = pd.date_range(end=pd.Timestamp.now(tz=assume_tz), periods=len(out), freq="15min")
    for k in ["open", "high", "low", "close", "volume"]:
        if k in out.columns:
            out[k] = pd.to_numeric(out[k], errors="coerce")
    return _clean(out)


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty:
        return df
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
