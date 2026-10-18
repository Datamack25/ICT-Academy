"""Thème : texte NOIR sur fond BLANC partout (aucun blanc sur blanc).
Seule exception volontaire : les boutons bleus à texte blanc (contraste élevé)."""
import streamlit as st

BLUE = "#1F4E9A"
GREEN = "#0B7A3E"
RED = "#B3261E"
ORANGE = "#B85C00"
GREY = "#5A5F6B"

CSS = f"""
<style>
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
    background-color: #FFFFFF !important; color: #000000 !important;
}}
[data-testid="stSidebar"], [data-testid="stSidebar"] > div {{
    background-color: #F2F4F8 !important;
}}
/* Tout le texte en noir */
.stApp p, .stApp li, .stApp span, .stApp label, .stApp div, .stApp td, .stApp th,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp small, .stApp strong, .stApp em, .stApp code, .stApp summary,
[data-testid="stMarkdownContainer"] *, [data-testid="stMetricValue"],
[data-testid="stMetricLabel"] *, [data-testid="stWidgetLabel"] *,
[data-testid="stCaptionContainer"], [data-testid="stSidebar"] * {{
    color: #000000 !important;
}}
[data-testid="stMetricDelta"] svg {{ display: inline; }}
/* Champs de saisie : fond blanc, texte noir, bordure visible */
input, textarea, select, [data-baseweb="input"] input, [data-baseweb="textarea"] textarea,
[data-baseweb="select"] > div, [data-baseweb="base-input"] {{
    background-color: #FFFFFF !important; color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
}}
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] {{
    border: 1px solid #8A8F99 !important; border-radius: 6px !important;
}}
/* Menus déroulants */
[data-baseweb="popover"], [data-baseweb="popover"] *, [data-baseweb="menu"], [role="listbox"],
[role="listbox"] li, [role="option"] {{
    background-color: #FFFFFF !important; color: #000000 !important;
}}
[role="option"]:hover, [aria-selected="true"][role="option"] {{ background-color: #E3EAF6 !important; }}
/* Étiquettes des multiselect : fond bleu, texte blanc (comme les boutons) */
.stApp [data-baseweb="tag"] {{ background-color: #1F4E9A !important; }}
.stApp [data-baseweb="tag"] span, .stApp [data-baseweb="tag"] div, .stApp [data-baseweb="tag"] svg {{
    color: #FFFFFF !important; fill: #FFFFFF !important; }}
/* Chat */
[data-testid="stChatInput"] textarea {{ background:#FFFFFF !important; color:#000 !important; }}
[data-testid="stChatMessage"] {{ background-color: #F7F8FB !important; border:1px solid #E1E4EA; }}
/* Tooltips (bulles d'aide) — sans toucher aux boutons qu'elles entourent */
[data-testid="stTooltipContent"], [data-testid="stTooltipContent"] * {{
    background-color: #FFFFFF !important; color: #000000 !important;
}}
/* Boutons : bleu, texte blanc (lisible) */
.stApp button[kind^="secondary"], .stApp button[kind^="primary"] {{
    background-color: {BLUE} !important; border: 1px solid {BLUE} !important; border-radius: 6px !important;
}}
.stApp button[kind^="secondary"] *, .stApp button[kind^="primary"] * {{
    color: #FFFFFF !important;
}}
button[kind^="secondary"]:hover, button[kind^="primary"]:hover {{ background-color: #163A73 !important; }}
button[kind^="secondary"]:disabled {{ background-color: #C9CED8 !important; border-color:#C9CED8 !important; }}
button[kind^="secondary"]:disabled * {{ color: #000000 !important; }}
/* Onglets */
.stTabs [data-baseweb="tab"] {{ background-color: #FFFFFF !important; }}
.stTabs [data-baseweb="tab"] * {{ color: #000000 !important; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ border-bottom: 3px solid {BLUE} !important; }}
/* Expanders, uploader, alertes, code */
[data-testid="stExpander"] details, [data-testid="stExpander"] summary {{
    background-color: #FFFFFF !important; border-color: #C9CED8 !important;
}}
[data-testid="stFileUploaderDropzone"] {{ background-color: #F7F8FB !important; border: 1px dashed #8A8F99 !important; }}
[data-testid="stAlert"] {{ border: 1px solid #C9CED8; }}
[data-testid="stAlert"] * {{ color: #000000 !important; }}
pre, code {{ background-color: #F2F4F8 !important; color: #000000 !important; }}
/* Radio / checkbox labels */
[role="radiogroup"] label *, [data-testid="stCheckbox"] label * {{ color: #000000 !important; }}
/* Cartes maison */
.card {{ background:#FFFFFF; border:1px solid #C9CED8; border-radius:10px; padding:14px 16px; margin-bottom:10px; }}
.card h4 {{ margin:0 0 6px 0; }}
.pill {{ display:inline-block; padding:2px 9px; border-radius:12px; font-size:0.8rem; font-weight:600;
        border:1px solid #000; background:#FFFFFF; color:#000 !important; margin-right:4px; }}
.pill-green {{ border-color:{GREEN}; color:{GREEN} !important; }}
.pill-red {{ border-color:{RED}; color:{RED} !important; }}
.pill-orange {{ border-color:{ORANGE}; color:{ORANGE} !important; }}
.pill-green *, .pill-red *, .pill-orange * {{ color: inherit !important; }}
[data-testid="stMetricValue"] {{ font-size: 1.45rem !important; }}
.footer {{ text-align:center; font-size:0.8rem; margin-top:30px; padding-top:10px; border-top:1px solid #C9CED8; }}
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def pill(text, kind=""):
    cls = f"pill pill-{kind}" if kind else "pill"
    return f'<span class="{cls}">{text}</span>'


def card(title, body_html):
    st.markdown(f'<div class="card"><h4>{title}</h4>{body_html}</div>', unsafe_allow_html=True)
