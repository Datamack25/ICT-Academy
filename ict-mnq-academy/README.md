# 📈 ICT MNQ Academy

Plateforme d'entraînement au trading **ICT / Smart Money** sur le **Micro E-mini Nasdaq-100 (MNQ)**.
Streamlit + HTML · données **Yahoo Finance** · **compte fictif** · coach d'analyse des trades · **agent expert** technique & macro.
Méthodologie alignée sur le cours *Warren — Stratégie de trade (ESLSCA)* : orderblocks (méthodes A/B/C), breakers, market structure,
ranges & déviations, FVG, Monday range, TPO/POC, sessions et gestion du risque.

> Outil pédagogique : aucune analyse produite n'est un conseil en investissement.

## Fonctionnalités

| Page | Contenu |
|---|---|
| 🏠 Accueil | Capital fictif, biais du moment, aperçu du graphique annoté |
| 🖥️ Edge Desk (live) | Poste de pilotage identique au script TradingView « Edge 5 Desk » : 5 setups (M1 Z, M2 G, M3 B, M4 C, M5 M), lignes de trades M#T#, tableau EDGE DESK (NOW, WINDOW, DAILY, 1H, escalier, MMPD, positions), edges testés (WR, avg RR ancien → récent, verdict), PROP HELPER (pass % à ta taille, jours, meilleure taille, ½ vs FULL), ticket d'ordre du signal du moment envoyable au compte fictif, rafraîchissement auto |
| 🎯 Simulateur MNQ | **Replay** bougie par bougie (futur masqué) ou **live différé** ; ordres marché/limite, SL obligatoire, TP, break-even ; P&L en MNQ (2 $/pt, tick 0,25) ; drawdown suiveur type Apex ; **coach en direct** (6 conditions) ; setups détectés |
| 📒 Journal & Coach | Note A–D de chaque trade, points forts / erreurs / conseils, contexte détecté vs plan déclaré, courbe de capital, P&L par setup et kill zone, rejeu du trade, export CSV |
| 📊 Backtests & Verdicts | 17 setups rejoués après coûts (ICT : méthode C, méthode A, breaker, ICT 2022, SFP · MMM : Z T3+, G, B, GMC short, M, C, 09h30, AFs+ P 12,5 % · règles bougie du PDF), période ancienne 70 % vs récente 30 %, tirage aléatoire, t-score, 7 contrôles de preuve, verdicts **TRADE / USE AS FILTER / WATCH / DON'T TRADE**, test des filtres (sessions, MMPD, bougie journalière), grille ≈ 2 000 combos, rejeu des trades sur le graphique, odds par heure/session (méthode du PDF), mur du momentum, Monte Carlo prop (Apex 50K) |
| 📜 Scripts TradingView | Document **Word** téléchargeable + fichiers `.pine` : ICT MNQ Suite, MMM Order-Flow Map, MMPD, Tempête parfaite (MTF), stratégie Edge Lab avec tableau de stats et verdict |
| 🤖 Agent expert | Rapport technique ICT, régime macro (VIX, DXY, taux 10 ans/3 mois, pétrole, or, SOX, BTC, USD/JPY, ES vs NQ), actualités classées **économique / financier / politique / géopolitique**, agenda, chat, **analyse de CSV** (bougies ou journal de trades) |
| 📚 Figures ICT | ~30 figures (structure, liquidité, PD arrays, Fibonacci/OTE, temps, niveaux, modèles, SMT) + fiche HTML |
| 🧭 Méthode d'étude | 10 étapes du cours, exercice guidé sur graphique « nu », quiz |
| ⚙️ Mode d'emploi | Utilisation, déploiement, mise à jour |

### Couche MMM dessinée automatiquement
Boussole des bougies (BC+/BC−, AFs+/AFs−, C2, CI) · GMC avec ligne au GMC open (supprimée à la clôture au-delà) · escalier T# (CDL/CDS = T1,
LD/SD = continuations, ★ à T3+, niveau protégé R#) · boîtes de session 18h/02h/09h30 (contraction/expansion, balance control 1/3–2/3, vPOC, ZBrk) ·
zones de pullback P–MP / BAL–MD · oscillateur MMPD 27/9 (XP/XD) · alignement multi-UT · cycle de vie du momentum sur la position ouverte.
Sélecteur « Lecture du graphique » : ICT, MMM ou ICT + MMM (allégé).

### Détections automatiques (sans regarder le futur)
Swings (fractales) · BOS / MSS validés à la clôture · orderblocks + statut (actif / mitigé / cassé) · breakers (retesté / invalidé) ·
FVG (ouvert / partiel / comblé) · sweeps / SFP (BSL / SSL) · equal highs/lows · range de travail, EQ, premium/discount, OTE 0.62–0.79 (0.705) ·
PDH/PDL, PWH/PWL, Monday High/Low, Weekly Open, Midnight Open, NY Open 9:30, Asia/London high-low · POC/VAH/VAL J-1 · kill zones (heure NY) ·
biais multi-UT (TF + H1 + H4) · setups « Méthode C / Breaker strategy » avec entrée, stop, cible, R:R et score.

## Structure du dépôt
```
ict-mnq-academy/
├── main.py                 # application Streamlit (pages)
├── core/
│   ├── data.py             # Yahoo (MNQ=F → repli NQ=F), import CSV, données démo
│   ├── ict.py              # moteur ICT
│   ├── charts.py           # graphiques Plotly (fond blanc, texte noir)
│   ├── paper.py            # compte fictif / exécution
│   ├── coach.py            # notation des trades
│   ├── edge.py             # moteur Edge 5 (mêmes règles que le script Edge 5 Desk)
│   ├── pages_desk.py       # page Edge Desk
│   ├── mmm.py              # couche order flow inspirée du Max Maserati Model
│   ├── backtest.py         # banc de backtests, verdicts, odds, Monte Carlo prop
│   ├── pages_bt.py         # pages Backtests & Verdicts / Scripts TradingView
│   ├── pine.py             # scripts Pine v6
│   ├── word_export.py      # génération du Word (python-docx)
│   ├── agent.py            # agent expert (technique, macro, news, CSV, LLM optionnel)
│   ├── content.py          # figures, méthode, quiz, fiche HTML
│   └── style.py            # thème noir sur blanc
├── requirements.txt
├── .streamlit/config.toml
├── .gitignore
└── README.md
```

## Lancer en local
```bash
pip install -r requirements.txt
streamlit run main.py
```
Astuce test hors connexion : `http://localhost:8501/?source=demo`. Liens directs : `?page=backtests`, `?page=scripts`, `?page=simulateur`.

## Déployer (GitHub + Streamlit Community Cloud)
```bash
git init && git add . && git commit -m "ICT MNQ Academy v1"
git branch -M main
git remote add origin https://github.com/<ton-compte>/ict-mnq-academy.git
git push -u origin main
```
share.streamlit.io → *New app* → dépôt → fichier principal **`main.py`**.

### IA optionnelle pour l'agent
- **Claude** : *Settings → Secrets* de l'app Streamlit :
  ```toml
  ANTHROPIC_API_KEY = "sk-ant-..."
  ANTHROPIC_MODEL = "claude-sonnet-5-5"   # facultatif
  ```
- **Ollama** (local uniquement) : `ollama run mistral`, puis choisir « Ollama (local) » dans l'agent.
Sans clé, le **moteur expert intégré** répond à partir des calculs.

## Mettre à jour
```bash
git add . && git commit -m "maj" && git push
```
Streamlit Cloud redéploie automatiquement. Les sessions ne sont pas conservées côté serveur :
utilise **Sauvegarder ma session (JSON)** dans la barre latérale et recharge-la à la visite suivante.

## Limites connues
- Yahoo : 1 min = 7 jours, 5/15/30 min = 60 jours, 1 h = 2 ans d'historique ; cotations futures différées (~10-15 min).
- Exécution simulée prudente : si SL et TP sont touchés dans la même bougie, le SL est retenu ; pas de slippage modélisé hors gaps.
- Les actualités proviennent du flux Yahoo (anglais) et sont classées par mots-clés ; vérifier le calendrier économique officiel.
