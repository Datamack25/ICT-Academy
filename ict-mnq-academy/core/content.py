"""Contenu pédagogique : figures ICT, méthode d'étude (cours Warren), quiz, fiche HTML."""

FIGURES = [
    # catégorie, nom, définition, identification, exécution, source, auto-détecté
    ("Structure", "Swing High / Swing Low",
     "Point pivot : un plus haut (ou plus bas) entouré de bougies plus basses (ou plus hautes).",
     "Fractale : la bougie centrale dépasse les N bougies de chaque côté (paramètre « sensibilité des swings »).",
     "Ce sont les poches de liquidité : les stops sont placés juste au-delà.", "Cours Warren — Market Structure", True),
    ("Structure", "BOS — Break of Structure",
     "Cassure d'un swing dans le sens de la tendance : continuation (HH/HL ou LH/LL).",
     "Clôture au-delà du dernier swing high (tendance haussière) ou swing low (baissière).",
     "Chercher l'OB/FVG laissé par la jambe de cassure pour rejoindre la tendance.", "ICT / Cours Warren", True),
    ("Structure", "MSB / MSS (CHoCH) — Market Structure Shift",
     "Rupture de structure CONTRAIRE à la tendance précédente : premier signal de retournement.",
     "Clôture (pas une simple mèche) au-delà du swing qui a produit le dernier plus haut/plus bas.",
     "Le cours : pas d'orderblock valide sans MSB. Après le MSB, on cherche le S/D formé.", "Cours Warren p.2, 12-13", True),
    ("Liquidité", "BSL / SSL — Buy-side & Sell-side Liquidity",
     "Ordres stops au-dessus des hauts (BSL) et sous les bas (SSL).",
     "Swing highs/lows évidents, PDH/PDL, Monday High/Low, highs/lows de session.",
     "Le prix va de poche de liquidité en poche de liquidité : ce sont les cibles (TP).", "Cours Warren — Ranges", True),
    ("Liquidité", "Equal Highs / Equal Lows (EQH/EQL)",
     "Deux sommets (ou creux) quasi égaux : liquidité « relative » très attirante.",
     "Swings dans une tolérance de quelques points.", "Cible prioritaire ; ne pas placer son stop juste derrière.", "ICT", True),
    ("Liquidité", "Sweep / SFP / Turtle Soup",
     "La mèche prend la liquidité d'un swing puis le prix réintègre (fausse cassure).",
     "Mèche au-delà du swing + clôture de retour en deçà.",
     "Méthode C du cours : sweep → MSS → retour dans l'OB = setup A+.", "Cours Warren p.5, 14, 41", True),
    ("Liquidité", "Déviation de range",
     "Trade au-dessus/au-dessous du range défini (fausse rupture) avant de revenir dedans.",
     "Sortie du range high/low suivie d'une clôture de retour dans le range.",
     "Viser l'autre extrémité du range après MSB (Range/MSB + S/D Strategy).", "Cours Warren p.28, 46-50", True),
    ("PD Arrays", "Orderblock haussier / baissier",
     "Dernière bougie opposée avant le mouvement impulsif qui a cassé la structure.",
     "OB haussier : dernière bougie baissière avant la hausse qui fait le MSB (inverse pour l'OB baissier).",
     "Entrée au début de l'OB (méthode A) ou à l'OTE 0.705 dans l'OB (B/C), stop au-delà.", "Cours Warren p.1-10", True),
    ("PD Arrays", "Breaker Block",
     "Orderblock échoué : le prix casse l'OB qui change de polarité (support → résistance).",
     "OB haussier cassé à la clôture → breaker baissier (et inversement), idéalement après un sweep.",
     "Entrée au retest du breaker, stop de l'autre côté, cible les swings opposés. « Un de mes setups préférés ».", "Cours Warren p.16-27, 38-45", True),
    ("PD Arrays", "Mitigation Block",
     "Comme un breaker mais SANS prise de liquidité (le swing n'a pas été dépassé).",
     "Échec à faire un nouveau plus haut/plus bas, puis cassure du dernier swing.",
     "Retest du bloc dans le sens du nouveau flux.", "ICT", False),
    ("PD Arrays", "Rejection Block",
     "Zone formée par les longues mèches à un extrême.",
     "Corps des bougies jusqu'à l'extrême de la mèche.", "Entrée au retour sur les corps, stop au-delà de la mèche.", "ICT", False),
    ("PD Arrays", "FVG — Fair Value Gap (BISI / SIBI)",
     "Inefficience sur 3 bougies : la mèche de la 1re et celle de la 3e ne se chevauchent pas.",
     "FVG haussier : bas de la bougie 3 > haut de la bougie 1 (inverse pour baissier).",
     "Le prix tend à revenir combler l'écart : zone d'entrée ou cible.", "Cours Warren p.31-37", True),
    ("PD Arrays", "Inverse FVG (IFVG)",
     "FVG traversé et clôturé de l'autre côté : il change de rôle.", "FVG comblé avec clôture au-delà.",
     "Retest de l'IFVG dans la nouvelle direction.", "ICT", False),
    ("PD Arrays", "BPR — Balanced Price Range",
     "Chevauchement d'un FVG haussier et d'un FVG baissier.", "Zone commune entre deux FVG opposés.",
     "Zone très réactive.", "ICT", False),
    ("PD Arrays", "Volume Imbalance / Liquidity Void",
     "Écart entre corps (volume imbalance) ou longue bougie unidirectionnelle (void).",
     "Corps qui ne se touchent pas / bougie de grande amplitude sans retracement.", "Le prix revient souvent la rééquilibrer.", "ICT", False),
    ("Fibonacci", "Premium / Discount / EQ",
     "Moitié haute du range = premium (vendre), moitié basse = discount (acheter), 0.5 = EQ.",
     "Tracer le range swing high → swing low.", "Ne jamais trader à l'EQ : « zone où vous ne voulez pas trader ».", "Cours Warren p.28-31, 64", True),
    ("Fibonacci", "OTE — Optimal Trade Entry (0.62–0.79, 0.705)",
     "Retracement optimal de la jambe impulsive ; 0.705 = niveau clé du cours.",
     "Fibo du swing high au swing low (short) ou du low au high (long).",
     "Entrée quand l'OTE est À L'INTÉRIEUR d'un OB/breaker (confluence).", "Cours Warren p.4-10", True),
    ("Temps", "Kill Zones (Asie, Londres, NY AM, NY PM)",
     "Fenêtres horaires où l'algorithme délivre les mouvements.",
     "Heure NY : Asie 20h-00h, London 2h-5h, NY AM 7h-10h, NY PM 13h30-16h.",
     "MNQ : privilégier London et surtout NY AM (9h30-11h).", "Cours Warren p.69-72 + ICT", True),
    ("Temps", "Silver Bullet",
     "Fenêtre 10h-11h NY (et 14h-15h) : un FVG se forme vers une liquidité.",
     "Dans la fenêtre : sweep puis FVG dans le sens du déplacement.", "Entrée sur le FVG, cible la liquidité la plus proche.", "ICT", True),
    ("Temps", "Power of 3 (AMD)",
     "Accumulation → Manipulation (Judas swing) → Distribution.",
     "Range asiatique, faux mouvement à Londres/NY open, puis vrai mouvement.",
     "Le cours : utiliser le Power of 3 pour atteindre les niveaux du lundi laissés intacts.", "Cours Warren p.55-59", False),
    ("Temps", "Judas Swing",
     "Faux départ en début de session qui piège les traders de breakout.", "Mouvement contre le biais après l'ouverture (souvent au-delà du midnight open).",
     "Entrer dans le sens du biais après le sweep.", "ICT", False),
    ("Temps", "Monday Range",
     "Le plus haut et le plus bas du lundi = liquidité initiale de la semaine.",
     "Attendre la clôture du lundi, marquer High/Low + Weekly Open.",
     "Sweep d'un côté tôt dans la semaine → probabilité d'aller chercher l'autre côté.", "Cours Warren p.54-59", True),
    ("Niveaux", "Midnight Open / NY Open / Weekly Open",
     "Ouvertures de référence de l'algorithme.", "00h00 NY, 9h30 NY, ouverture du dimanche 18h.",
     "Acheter sous l'ouverture en biais haussier, vendre au-dessus en biais baissier.", "ICT / Cours Warren p.13", True),
    ("Niveaux", "PDH / PDL, PWH / PWL",
     "Plus haut/bas de la veille et de la semaine précédente.", "Calculés sur la journée de trading CME (18h → 17h NY).",
     "Cibles de liquidité classiques.", "ICT", True),
    ("Niveaux", "POC / VAH / VAL (Market Profile)",
     "POC = prix le plus échangé ; zone de valeur ≈ 70 % des échanges.",
     "Profil de volume de la journée précédente (proxy du TPO du cours).",
     "En range, le prix revient au POC de la veille ; les naked POC servent d'aimants.", "Cours Warren p.59-69", True),
    ("Modèles", "ICT 2022 Model",
     "Prise de liquidité → MSS avec déplacement → FVG → entrée sur le FVG.", "Sweep + MSS + FVG dans la jambe de cassure.",
     "Stop au-delà du swing, cible la liquidité opposée.", "ICT", True),
    ("Modèles", "Unicorn",
     "Breaker + FVG qui se chevauchent.", "FVG dans la zone d'un breaker.", "Entrée dans la zone commune.", "ICT", False),
    ("Modèles", "Market Maker Buy/Sell Model (MMBM/MMSM)",
     "Courbe complète : consolidation, prise de liquidité, smart money reversal, retour au point d'origine.",
     "Série de LH/LL puis SMR à une PD array HTF.", "Achats au retournement, cibles sur l'origine du mouvement.", "ICT", False),
    ("Corrélation", "SMT Divergence (NQ vs ES)",
     "Un indice fait un nouveau plus bas, l'autre non : signe de force cachée.",
     "Comparer MNQ et MES sur les mêmes swings.", "Confirmation d'un retournement à une PD array.", "ICT", False),
    # ---------------- Couche order flow inspirée du Max Maserati Model (MMM)
    ("MMM order flow", "BC+ / BC− (body close)",
     "Bougie qui CLÔTURE au-dessus du plus haut précédent (BC+) ou sous le plus bas précédent (BC−) : le camp acheteur/vendeur a franchi l'autre.",
     "Clôture > haut de la bougie précédente (BC+) ; clôture < bas précédent (BC−).",
     "Le document MMM vise l'extrême de la bougie signal, stop à l'extrême opposé, entrée à l'ouverture suivante — à juger APRÈS coûts dans les backtests.", "PDF Max Maserati Model + site", True),
    ("MMM order flow", "AFs+ / AFs− (affinity sweep)",
     "Nouveau plus bas (ou plus haut) qui balaie la liquidité puis clôture à l'intérieur, près de l'extrême opposé : vendeurs (ou acheteurs) piégés.",
     "Bas < bas précédent, clôture > bas précédent dans le haut de la bougie (AFs+) ; inverse pour AFs−.",
     "Équivalent « bougie » du SFP ICT. Combo validé côté site : limite au pullback de 12,5 %, stop sous la bougie.", "PDF + site", True),
    ("MMM order flow", "C2+ / C2− · CI (inside)",
     "C2 : clôture au-delà de la clôture précédente sans casser l'extrême ; CI : bougie à l'intérieur de la précédente (compression).",
     "Comparer clôture et extrêmes avec la bougie précédente.", "Bougies d'information : pas de trade seul.", "Inspiré MMM", True),
    ("MMM order flow", "GMC — gap-confirmed momentum",
     "c1 → c2 (BC) → c3 laisse un vide entre c1 et c3 : momentum confirmé par le gap (proche d'un FVG avec bougie BC au centre).",
     "BC+ en c2 et bas de c3 > haut de c1 (inverse en baissier) ; ligne à l'open de c2 supprimée sur clôture au-delà.",
     "Setups G (GMC long) et B (GMC dont c3 fait un « AFs contre ») : entrée clôture c3, stop 1 ATR.", "Site maxmaserati.com", True),
    ("MMM order flow", "Escalier T# · CDL/CDS · LD/SD · P# · R#",
     "T1 = flip (CDL haussier / CDS baissier), chaque continuation ajoute une marche (LD1 → T2, LD2 → T3…). P# = niveau cassé, R# = pullback = stop protégé.",
     "Clôtures au-delà des swings successifs dans le même sens.",
     "Setup Z : à partir de T3 (« la tendance a battu l'autre côté trois fois »), entrée à la clôture, stop 1,5 ATR, ½ à +0,5 R.", "Site maxmaserati.com", True),
    ("MMM order flow", "Boîte de session BZ · contraction / expansion",
     "Range des premières minutes des ouvertures 18h00, 02h00 et 09h30 (NY), prolongé jusqu'à la 1re clôture dehors (ZBrk).",
     "Contraction si la boîte est étroite par rapport à l'ATR ; expansion sinon.",
     "Contraction = énergie stockée (setup C) ; 1re cassure de la boîte 09h30 = candidat suivi.", "Site maxmaserati.com", True),
    ("MMM order flow", "Balance control (1/3 – 2/3) · vPOC",
     "Ligne verte aux 2/3 de la boîte (acheteurs), rouge au 1/3 (vendeurs) ; le camp en contrôle a la ligne épaisse. vPOC = prix au plus gros volume.",
     "Où se situe la dernière clôture dans la boîte.",
     "Filtre : clôture dans le tiers haut → cassure haussière plus probable (et inversement). Le vPOC est une information, pas une entrée.", "Site maxmaserati.com", True),
    ("MMM order flow", "Zones de pullback P–MP / BAL–MD",
     "Après une bougie + : bande 87,5–75 % de la bougie ; après une bougie − : bande 50–25 %.",
     "Niveaux P 87,5 % · MP 75 % · BAL 50 % · MD 25 % · D 12,5 % mesurés dans le sens de la bougie.",
     "Zones de limite peu profondes ; les limites profondes (D, 50 % de jambe) sont les pires entrées testées.", "Site maxmaserati.com", True),
    ("MMM order flow", "MMPD (premium / discount 0–100)",
     "Position du prix dans son range récent : lignes 27 (lente) et 9 (rapide). XP ≥ 80, XD ≤ 20.",
     "Oscillateur sous le graphique.", "Gate de momentum : long seulement en XP, short seulement en XD. Ne jamais jouer le retournement des extrêmes.", "Site maxmaserati.com", True),
    ("MMM order flow", "Tempête parfaite (alignement multi-UT)",
     "Daily, 4H, 1H et 15m clôturent dans le même sens (BC+ ou BC−).",
     "Tableau d'alignement dans le simulateur et script TradingView dédié.",
     "Le document entre sur l'UT 4H et utilise 1H/15m comme confirmation ; taille max 1,5 % même avec 4 UT alignées.", "PDF Max Maserati Model", True),
    ("MMM order flow", "Cycle de vie du momentum · mur du momentum",
     "Construction (le prix avance sans retester l'entrée) → Touche (retest sans clôture au-delà) → Échec (clôture au-delà).",
     "Compter les bougies de construction et les touches depuis l'entrée.",
     "Le document sort l'essentiel au compte 4 (haussier) / 3 (baissier). La plateforme mesure ce mur sur tes données (onglet Niveaux & odds).", "PDF Max Maserati Model", True),
]

STUDY_STEPS = [
    ("1. Contexte HTF (Daily / H4)",
     "Quelle est la structure ? Série de HH/HL ou LH/LL ? Où sont les liquidités évidentes (PDH/PDL, PWH/PWL, EQH/EQL) ? "
     "Le prix est-il en premium ou en discount du range HTF ?",
     "« La structure du marché vous offre un dialogue lorsque vous analysez le marché. »"),
    ("2. Tendance ou range ?",
     "Si le marché sort d'une tendance et alterne entre un haut et un bas communs : c'est un range. "
     "Marque le range high, le range low et l'EQ (0.5). En range on adopte un biais égal et on joue les extrêmes.",
     "« Ne vous attendez pas à une rupture immédiate à chaque petite phase d'épuisement. »"),
    ("3. Niveaux de la semaine et du jour",
     "Monday High/Low, Weekly Open, Midnight Open, range asiatique, high/low de Londres, POC de la veille.",
     "« Travailler un lundi n'est jamais recommandé : attendez la clôture du lundi pour bâtir le gameplan. »"),
    ("4. Attendre la prise de liquidité",
     "Le prix doit d'abord balayer un swing (sweep / SFP / déviation de range). Pas de sweep = pas de carburant.",
     "« Avant que le smart money puisse manipuler la liquidité, il doit d'abord y avoir de la liquidité à collecter. »"),
    ("5. Confirmer le MSB / MSS (UT d'exécution 15 min, affinage 5/1 min)",
     "Clôture au-delà du swing qui a mené au sweep. Une mèche ne suffit pas.",
     "« Ne prenez pas de position sur un breaker sans avoir d'abord validé un nouveau plus haut. »"),
    ("6. Repérer la zone d'entrée",
     "OB qui a provoqué la cassure, breaker si un OB a échoué, FVG dans la jambe de déplacement. Tracer le Fibo : l'OTE 0.705 doit être DANS la zone.",
     "« Ce niveau, situé à l'intérieur de l'orderblock, fournit des entrées précises lorsqu'il est utilisé correctement. »"),
    ("7. Construire le trade",
     "Entrée : début de zone ou 0.705. Stop : au-delà de l'OB / du sweep (invalidation). Cible : liquidité opposée non exploitée. R:R ≥ 2.",
     "« Target : ciblez les plus bas non exploités. »"),
    ("8. Timing",
     "Exécuter en kill zone : London (2h-5h NY) ou NY AM (9h30-11h NY). Éviter le lunch et les annonces (CPI, NFP, FOMC) sans plan.",
     "« Savoir quand trader est tout aussi important que savoir comment trader. »"),
    ("9. Gestion",
     "Risque 1–1,5 % intraday (2 % swing). Prendre 1/3 à 1R, stop à break-even, laisser courir le reste vers la cible.",
     "« Plus souvent qu'autrement, quelques trades atteignent 1R+ avant de revenir à mon point d'entrée. »"),
    ("10. Journal et revue",
     "Chaque trade est noté par le coach. Relis tes erreurs récurrentes chaque semaine et ne trade que les setups A/B.",
     "Discipline > nombre de trades."),
]

QUIZ = [
    ("Qu'est-ce qui valide un orderblock selon le cours ?",
     ["Un gros volume", "Une rupture de structure (MSB)", "Un croisement de moyennes", "Un RSI en survente"], 1),
    ("Un orderblock haussier cassé à la clôture devient…",
     ["Un FVG", "Un breaker baissier", "Un breaker haussier", "Un POC"], 1),
    ("Quel niveau Fibonacci le cours appelle-t-il l'entrée optimale (OTE) ?",
     ["0.382", "0.5", "0.705", "1.272"], 2),
    ("Où le cours conseille-t-il de NE PAS trader dans un range ?",
     ["Au range high", "Au range low", "À l'EQ (0.5)", "Après un sweep"], 2),
    ("Quelle condition la méthode personnelle (C) ajoute-t-elle avant le MSB ?",
     ["Un gap d'ouverture", "Un swing « couru » (liquidité prise)", "Une divergence RSI", "Une news macro"], 1),
    ("Le Monday range sert surtout à…",
     ["Entrer le lundi matin", "Repérer la liquidité initiale de la semaine", "Calculer le levier", "Mesurer la volatilité implicite"], 1),
    ("Risque conseillé par trade pour un setup intraday dans le cours ?",
     ["0,1 %", "1–1,5 %", "5 %", "10 %"], 1),
    ("MNQ : valeur d'un point par contrat ?", ["0,50 $", "2 $", "5 $", "20 $"], 1),
]

CHEATSHEET_HTML = """
<div style="font-family:Arial,Helvetica,sans-serif;background:#FFFFFF;color:#000000;padding:6px;">
<style>
 .g{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
 .b{border:1px solid #C9CED8;border-radius:10px;padding:10px;background:#FFFFFF;color:#000}
 .b h4{margin:0 0 6px 0;font-size:15px;color:#000}
 .b p,.b li{font-size:13px;margin:2px 0;color:#000}
 .t{display:inline-block;border:1px solid #1F4E9A;color:#1F4E9A;border-radius:10px;padding:0 6px;font-size:11px}
 svg text{fill:#000;font-size:11px}
</style>
<div class="g">
 <div class="b"><h4>Modèle « Méthode C » (haussier)</h4>
  <svg viewBox="0 0 240 110" width="100%" height="110">
   <polyline points="5,30 40,60 70,45 100,85 120,100 140,70 165,40 185,62 205,58 235,15" fill="none" stroke="#000" stroke-width="2"/>
   <line x1="95" y1="87" x2="235" y2="87" stroke="#B3261E" stroke-dasharray="4"/>
   <text x="122" y="108">1. Sweep SSL</text>
   <line x1="70" y1="45" x2="200" y2="45" stroke="#0B7A3E" stroke-dasharray="4"/>
   <text x="150" y="38">2. MSS</text>
   <rect x="105" y="78" width="130" height="12" fill="rgba(11,122,62,0.18)"/>
   <text x="172" y="75">3. OB / OTE</text>
   <text x="205" y="12">4. TP</text>
  </svg>
  <p><span class="t">Entrée</span> retour dans l'OB / 0.705 — <span class="t">Stop</span> sous le sweep — <span class="t">TP</span> liquidité opposée</p></div>
 <div class="b"><h4>Checklist avant d'appuyer</h4><ul>
  <li>Biais HTF clair (H4 / H1)</li><li>Liquidité prise (sweep / déviation)</li><li>MSS validé à la clôture</li>
  <li>Entrée OB / breaker / FVG + OTE</li><li>Discount pour acheter / premium pour vendre</li>
  <li>Kill zone London ou NY AM</li><li>Risque ≤ 1,5 % et R:R ≥ 2</li></ul></div>
 <div class="b"><h4>MNQ — spécifications</h4><ul>
  <li>Micro E-mini Nasdaq-100 (CME)</li><li>1 point = 2 $ / contrat</li><li>Tick 0,25 = 0,50 $</li>
  <li>Session : dim.–ven. 18h–17h NY</li><li>Équivalent NQ : ×10</li></ul></div>
 <div class="b"><h4>Horaires (heure de Paris, hors décalage DST)</h4><ul>
  <li>Asie : 02h–06h</li><li>London KZ : 08h–11h</li><li>NY Open cash : 15h30</li>
  <li>NY AM KZ : 13h–16h · Silver Bullet : 16h–17h</li><li>NY PM : 19h30–22h</li></ul></div>
</div></div>
"""
