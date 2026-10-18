"""Thème à fort contraste.
- Fond de page gris-bleu, contenus sur cartes BLANCHES bordées → la page n'est plus « toute blanche ».
- Zone principale : texte NOIR forcé partout (y compris si Streamlit est réglé en thème sombre dans le navigateur).
- Barre latérale bleu marine : texte BLANC, champs de saisie blancs à texte NOIR.
- Titres : bandeau bleu marine, texte blanc. Boutons : bleu, texte blanc.
Règle : jamais de texte clair sur fond clair, jamais de texte foncé sur fond foncé."""
import streamlit as st

NAVY = "#0E2A47"
NAVY2 = "#173B63"
BLUE = "#1F4E9A"
GREEN = "#0B7A3E"
RED = "#B3261E"
ORANGE = "#B85C00"
GREY = "#5A5F6B"
PAGE_BG = "#E6ECF3"
INK = "#0B1220"

CSS = f"""
<style>
/* ---------- fonds */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
    background-color: {PAGE_BG} !important;
}}
[data-testid="stHeader"] {{ background-color: {PAGE_BG} !important; }}
[data-testid="stHeader"] * {{ color: {INK} !important; }}
.block-container {{ padding-top: 3.6rem !important; }}

/* ---------- zone principale : texte noir partout */
[data-testid="stMain"] p, [data-testid="stMain"] li, [data-testid="stMain"] span, [data-testid="stMain"] label,
[data-testid="stMain"] div, [data-testid="stMain"] td, [data-testid="stMain"] th, [data-testid="stMain"] h2,
[data-testid="stMain"] h3, [data-testid="stMain"] h4, [data-testid="stMain"] h5, [data-testid="stMain"] h6,
[data-testid="stMain"] small, [data-testid="stMain"] strong, [data-testid="stMain"] em, [data-testid="stMain"] summary,
[data-testid="stMain"] code, [data-testid="stMain"] pre, [data-testid="stMain"] blockquote {{
    color: {INK} !important;
}}
[data-testid="stMain"] a, [data-testid="stMain"] a * {{ color: {BLUE} !important; text-decoration: underline; }}
[data-testid="stMain"] h2, [data-testid="stMain"] h3 {{ color: {NAVY} !important; }}

/* ---------- titre de page : bandeau marine, texte blanc */
[data-testid="stMain"] h1 {{
    background: {NAVY}; color: #FFFFFF !important; padding: 14px 20px !important; border-radius: 10px;
    border-left: 8px solid #E53935; font-size: 1.9rem !important;
}}
[data-testid="stMain"] h1 *, [data-testid="stMain"] h1 span {{ color: #FFFFFF !important; }}

/* ---------- cartes blanches pour les blocs */
[data-testid="stMetric"], [data-testid="stExpander"] details, [data-testid="stDataFrame"], [data-testid="stTable"],
[data-testid="stPlotlyChart"], [data-testid="stForm"], [data-testid="stChatMessage"], .card {{
    background-color: #FFFFFF !important; border: 1px solid #B7C3D3 !important; border-radius: 10px !important;
}}
[data-testid="stMetric"] {{ padding: 10px 14px !important; }}
[data-testid="stMetricValue"] {{ font-size: 1.45rem !important; color: {INK} !important; }}
[data-testid="stMetricValue"] * {{ color: {INK} !important; }}
[data-testid="stMetricDelta"] svg {{ display: inline; }}
[data-testid="stPlotlyChart"] {{ padding: 4px !important; }}
[data-testid="stExpander"] summary {{ background-color: #FFFFFF !important; }}
[data-testid="stExpander"] summary * {{ color: {NAVY} !important; font-weight: 600; }}
.stTabs [data-baseweb="tab-list"] {{ background: #FFFFFF; border: 1px solid #B7C3D3; border-radius: 10px; padding: 2px 8px; }}
.stTabs [data-baseweb="tab"] {{ background-color: #FFFFFF !important; }}
.stTabs [data-baseweb="tab"] * {{ color: {INK} !important; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ border-bottom: 3px solid #E53935 !important; }}
.stTabs [aria-selected="true"] * {{ color: {NAVY} !important; }}

/* ---------- champs de saisie : fond blanc, texte noir (partout, y compris barre latérale) */
input, textarea, select, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="base-input"] {{
    background-color: #FFFFFF !important; color: {INK} !important; -webkit-text-fill-color: {INK} !important;
}}
[data-baseweb="select"] > div {{ background-color: #FFFFFF !important; border: 1px solid #8A97AA !important; }}
[data-baseweb="select"] *, [data-baseweb="input"] *, [data-baseweb="base-input"] * {{ color: {INK} !important; }}
[data-baseweb="input"], [data-baseweb="textarea"] {{ border: 1px solid #8A97AA !important; border-radius: 6px !important; }}
[data-testid="stNumberInput"] button {{ background-color: #DCE4EF !important; }}
[data-testid="stNumberInput"] button * {{ color: {INK} !important; fill: {INK} !important; }}
[data-baseweb="popover"], [data-baseweb="popover"] *, [data-baseweb="menu"], [role="listbox"], [role="listbox"] li, [role="option"] {{
    background-color: #FFFFFF !important; color: {INK} !important;
}}
[role="option"]:hover, [aria-selected="true"][role="option"] {{ background-color: #DCE6F5 !important; }}
[data-testid="stTooltipContent"], [data-testid="stTooltipContent"] * {{ background-color: #FFFFFF !important; color: {INK} !important; }}
[data-testid="stFileUploaderDropzone"] {{ background-color: #FFFFFF !important; border: 1px dashed #8A97AA !important; }}
[data-testid="stFileUploaderDropzone"] * {{ color: {INK} !important; }}
[data-testid="stChatInput"], [data-testid="stChatInput"] textarea {{ background: #FFFFFF !important; color: {INK} !important; }}
[data-testid="stAlert"] {{ border: 1px solid #8A97AA; }}
[data-testid="stAlert"] * {{ color: {INK} !important; }}
[data-testid="stMain"] pre, [data-testid="stMain"] code {{ background-color: #F1F4F9 !important; }}

/* ---------- barre latérale marine, texte blanc */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div {{ background-color: {NAVY} !important; }}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] small, [data-testid="stSidebar"] li,
[data-testid="stSidebar"] summary, [data-testid="stSidebar"] [data-testid="stWidgetLabel"] *,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] *, [data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
[data-testid="stSidebar"] [data-testid="stSliderTickBarMin"], [data-testid="stSidebar"] [data-testid="stSliderTickBarMax"],
[data-testid="stSidebar"] [data-testid="stSliderThumbValue"] {{
    color: #FFFFFF !important;
}}
[data-testid="stSidebar"] hr {{ border-color: #3A5E86 !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] details {{ background-color: {NAVY2} !important; border: 1px solid #3A5E86 !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {{ background-color: {NAVY2} !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary * {{ color: #FFFFFF !important; }}
/* les champs dans la barre latérale restent blancs à texte noir */
[data-testid="stSidebar"] [data-baseweb="select"] *, [data-testid="stSidebar"] [data-baseweb="input"] *,
[data-testid="stSidebar"] input, [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {{
    color: {INK} !important; -webkit-text-fill-color: {INK} !important;
}}
/* navigation : chaque page sur une ligne bien lisible, page active surlignée */
[data-testid="stSidebar"] [role="radiogroup"] label {{
    padding: 5px 8px; border-radius: 6px; margin-bottom: 2px; width: 100%;
}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{ background-color: #E53935; }}
[data-testid="stSidebar"] [role="radiogroup"] label * {{ color: #FFFFFF !important; font-weight: 600; }}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label * {{ color: #FFFFFF !important; }}

/* ---------- boutons : bleu, texte blanc */
.stApp button[kind^="secondary"], .stApp button[kind^="primary"] {{
    background-color: {BLUE} !important; border: 1px solid {BLUE} !important; border-radius: 6px !important;
}}
.stApp button[kind^="secondary"] *, .stApp button[kind^="primary"] * {{ color: #FFFFFF !important; }}
.stApp button[kind^="secondary"]:hover, .stApp button[kind^="primary"]:hover {{ background-color: #163A73 !important; }}
.stApp button[kind^="secondary"]:disabled {{ background-color: #C9CED8 !important; border-color: #C9CED8 !important; }}
.stApp button[kind^="secondary"]:disabled * {{ color: {INK} !important; }}
.stApp button[kind="primary"] {{ background-color: #C62828 !important; border-color: #C62828 !important; }}

/* étiquettes de multiselect : bleu, texte blanc */
.stApp [data-baseweb="tag"] {{ background-color: {BLUE} !important; }}
.stApp [data-baseweb="tag"] span, .stApp [data-baseweb="tag"] div, .stApp [data-baseweb="tag"] svg {{ color: #FFFFFF !important; fill: #FFFFFF !important; }}

/* ---------- composants maison */
.card {{ padding: 14px 16px; margin-bottom: 10px; }}
.card h4 {{ margin: 0 0 6px 0; color: {NAVY} !important; }}
.pill {{ display: inline-block; padding: 2px 9px; border-radius: 12px; font-size: 0.8rem; font-weight: 700;
        border: 1px solid {INK}; background: #FFFFFF; color: {INK} !important; margin-right: 4px; }}
.pill-green {{ border-color: {GREEN}; color: {GREEN} !important; }}
.pill-red {{ border-color: {RED}; color: {RED} !important; }}
.pill-orange {{ border-color: {ORANGE}; color: {ORANGE} !important; }}
[data-testid="stMain"] .pill-green, [data-testid="stMain"] .pill-green * {{ color: {GREEN} !important; }}
[data-testid="stMain"] .pill-red, [data-testid="stMain"] .pill-red * {{ color: {RED} !important; }}
[data-testid="stMain"] .pill-orange, [data-testid="stMain"] .pill-orange * {{ color: {ORANGE} !important; }}
.live-bar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; background: #FFFFFF; border: 1px solid #B7C3D3;
            border-radius: 10px; padding: 8px 14px; margin-bottom: 12px; }}
.live-dot {{ display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; }}
[data-testid="stMain"] .live-ok, [data-testid="stMain"] .live-ok * {{ color: {GREEN} !important; font-weight: 700; }}
[data-testid="stMain"] .live-warn, [data-testid="stMain"] .live-warn * {{ color: {ORANGE} !important; font-weight: 700; }}
[data-testid="stMain"] .live-bad, [data-testid="stMain"] .live-bad * {{ color: {RED} !important; font-weight: 700; }}
.footer {{ text-align: center; font-size: 0.8rem; margin-top: 30px; padding-top: 10px; border-top: 1px solid #B7C3D3; }}
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def pill(text, kind=""):
    cls = f"pill pill-{kind}" if kind else "pill"
    return f'<span class="{cls}">{text}</span>'


def card(title, body_html):
    st.markdown(f'<div class="card"><h4>{title}</h4>{body_html}</div>', unsafe_allow_html=True)


def live_bar(items_html: str):
    st.markdown(f'<div class="live-bar">{items_html}</div>', unsafe_allow_html=True)
