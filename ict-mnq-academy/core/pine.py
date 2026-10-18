"""Scripts Pine Script v6 pour TradingView, générés à partir des mêmes règles que la plateforme."""

ICT_SUITE = r'''//@version=6
indicator("ICT MNQ Suite — structure, OB, breakers, FVG, liquidité, OTE, kill zones", shorttitle="ICT MNQ Suite", overlay=true, max_boxes_count=300, max_lines_count=300, max_labels_count=300, max_bars_back=500)

// ───────── Réglages
tz = "America/New_York"
grpS = "Structure"
swLen      = input.int(2, "Sensibilité des swings (bougies de chaque côté)", minval=1, maxval=10, group=grpS)
showStruct = input.bool(true, "Afficher BOS / MSS (clôture)", group=grpS)
grpZ = "Zones (PD arrays)"
showOB   = input.bool(true, "Orderblocks", group=grpZ)
showBrk  = input.bool(true, "Breakers (OB cassés)", group=grpZ)
showFVG  = input.bool(true, "Fair Value Gaps", group=grpZ)
fvgMin   = input.float(4.0, "Taille mini d'un FVG (points)", minval=0.0, group=grpZ)
maxZones = input.int(6, "Zones conservées par type", minval=1, maxval=40, group=grpZ)
grpL = "Liquidité & niveaux"
showSweep  = input.bool(true, "Sweeps / SFP (BSL – SSL pris)", group=grpL)
showLevels = input.bool(true, "PDH / PDL · Monday High/Low · Midnight Open · Weekly Open", group=grpL)
showOTE    = input.bool(true, "Range de travail · EQ · OTE 0,62–0,79 (0,705)", group=grpL)
grpK = "Kill zones (heure de New York)"
showKZ  = input.bool(true, "Colorer les kill zones", group=grpK)
kzLon   = input.session("0200-0500", "London KZ", group=grpK)
kzNYAM  = input.session("0700-1000", "NY AM KZ", group=grpK)
kzSB    = input.session("1000-1100", "Silver Bullet", group=grpK)
kzNYPM  = input.session("1330-1600", "NY PM KZ", group=grpK)

inSess(string s) => not na(time(timeframe.period, s, tz))

bgcolor(showKZ and inSess(kzSB) ? color.new(color.orange, 88) : showKZ and inSess(kzNYAM) ? color.new(color.orange, 93) : showKZ and inSess(kzLon) ? color.new(color.blue, 93) : showKZ and inSess(kzNYPM) ? color.new(color.gray, 94) : na, title="Kill zones")

// ───────── Swings & structure (cassure validée à la CLÔTURE)
ph = ta.pivothigh(high, swLen, swLen)
pl = ta.pivotlow(low, swLen, swLen)
var float lastSH = na
var int   lastSHbar = na
var bool  shUsed = true
var float lastSL = na
var int   lastSLbar = na
var bool  slUsed = true
var int   trend = 0
if not na(ph)
    lastSH    := ph
    lastSHbar := bar_index - swLen
    shUsed    := false
if not na(pl)
    lastSL    := pl
    lastSLbar := bar_index - swLen
    slUsed    := false

var array<box> bullOB = array.new<box>()
var array<box> bearOB = array.new<box>()
var array<box> bullBrk = array.new<box>()
var array<box> bearBrk = array.new<box>()
var array<box> fvgUp = array.new<box>()
var array<box> fvgDn = array.new<box>()

pushBox(array<box> arr, box b) =>
    array.push(arr, b)
    if array.size(arr) > maxZones
        box.delete(array.shift(arr))

bullBreak = not shUsed and not na(lastSH) and close > lastSH
bearBreak = not slUsed and not na(lastSL) and close < lastSL

if bullBreak
    string kind = trend == -1 ? "MSS" : "BOS"
    if showStruct
        line.new(lastSHbar, lastSH, bar_index, lastSH, color=color.new(color.green, 0), style=line.style_dashed)
        label.new(int((lastSHbar + bar_index) / 2), lastSH, kind, style=label.style_label_down, color=color.new(color.white, 100), textcolor=color.green, size=size.small)
    // OB haussier : dernière bougie baissière avant la jambe qui a cassé
    int span = math.min(bar_index - lastSHbar + 3, 150)
    int extOff = 0
    float extLow = low
    for k = 0 to span
        if low[k] < extLow
            extLow := low[k]
            extOff := k
    int obOff = -1
    for k = extOff to math.min(extOff + 30, 200)
        if close[k] < open[k]
            obOff := k
            break
    if showOB and obOff >= 0
        pushBox(bullOB, box.new(bar_index - obOff, high[obOff], bar_index, low[obOff], border_color=color.green, bgcolor=color.new(color.green, 85), extend=extend.right, text="OB+ " + kind, text_color=color.green, text_size=size.tiny, text_halign=text.align_left))
    shUsed := true
    trend := 1

if bearBreak
    string kind = trend == 1 ? "MSS" : "BOS"
    if showStruct
        line.new(lastSLbar, lastSL, bar_index, lastSL, color=color.new(color.red, 0), style=line.style_dashed)
        label.new(int((lastSLbar + bar_index) / 2), lastSL, kind, style=label.style_label_up, color=color.new(color.white, 100), textcolor=color.red, size=size.small)
    int span = math.min(bar_index - lastSLbar + 3, 150)
    int extOff = 0
    float extHigh = high
    for k = 0 to span
        if high[k] > extHigh
            extHigh := high[k]
            extOff := k
    int obOff = -1
    for k = extOff to math.min(extOff + 30, 200)
        if close[k] > open[k]
            obOff := k
            break
    if showOB and obOff >= 0
        pushBox(bearOB, box.new(bar_index - obOff, high[obOff], bar_index, low[obOff], border_color=color.red, bgcolor=color.new(color.red, 85), extend=extend.right, text="OB− " + kind, text_color=color.red, text_size=size.tiny, text_halign=text.align_left))
    slUsed := true
    trend := -1

// OB cassé à la clôture -> breaker de polarité inverse
if array.size(bullOB) > 0
    for k = array.size(bullOB) - 1 to 0
        b = array.get(bullOB, k)
        if close < box.get_bottom(b)
            array.remove(bullOB, k)
            if showBrk
                box.set_bgcolor(b, color.new(color.red, 80))
                box.set_border_color(b, color.red)
                box.set_text(b, "Breaker ↓")
                box.set_text_color(b, color.red)
                pushBox(bearBrk, b)
            else
                box.delete(b)
        else if low <= box.get_top(b)
            box.set_text(b, "OB+ mitigé")
if array.size(bearOB) > 0
    for k = array.size(bearOB) - 1 to 0
        b = array.get(bearOB, k)
        if close > box.get_top(b)
            array.remove(bearOB, k)
            if showBrk
                box.set_bgcolor(b, color.new(color.green, 80))
                box.set_border_color(b, color.green)
                box.set_text(b, "Breaker ↑")
                box.set_text_color(b, color.green)
                pushBox(bullBrk, b)
            else
                box.delete(b)
        else if high >= box.get_bottom(b)
            box.set_text(b, "OB− mitigé")
// Breaker invalidé : clôture de l'autre côté
if array.size(bearBrk) > 0
    for k = array.size(bearBrk) - 1 to 0
        b = array.get(bearBrk, k)
        if close > box.get_top(b)
            box.set_extend(b, extend.none)
            box.set_right(b, bar_index)
            box.set_text(b, "Breaker invalidé")
            array.remove(bearBrk, k)
if array.size(bullBrk) > 0
    for k = array.size(bullBrk) - 1 to 0
        b = array.get(bullBrk, k)
        if close < box.get_bottom(b)
            box.set_extend(b, extend.none)
            box.set_right(b, bar_index)
            box.set_text(b, "Breaker invalidé")
            array.remove(bullBrk, k)

// ───────── FVG (3 bougies)
if showFVG and low > high[2] and low - high[2] >= fvgMin
    pushBox(fvgUp, box.new(bar_index - 2, low, bar_index, high[2], border_color=color.new(color.blue, 40), bgcolor=color.new(color.blue, 88), extend=extend.right, text="FVG", text_color=color.blue, text_size=size.tiny))
if showFVG and high < low[2] and low[2] - high >= fvgMin
    pushBox(fvgDn, box.new(bar_index - 2, low[2], bar_index, high, border_color=color.new(color.blue, 40), bgcolor=color.new(color.blue, 88), extend=extend.right, text="FVG", text_color=color.blue, text_size=size.tiny))
if array.size(fvgUp) > 0
    for k = array.size(fvgUp) - 1 to 0
        b = array.get(fvgUp, k)
        if low <= box.get_bottom(b)
            box.delete(b)
            array.remove(fvgUp, k)
if array.size(fvgDn) > 0
    for k = array.size(fvgDn) - 1 to 0
        b = array.get(fvgDn, k)
        if high >= box.get_top(b)
            box.delete(b)
            array.remove(fvgDn, k)

// ───────── Sweeps / SFP : mèche au-delà du swing, clôture de retour
var float sweptH = na
var float sweptL = na
bslSweep = not na(lastSH) and high > lastSH and close < lastSH and (na(sweptH) or lastSH != sweptH)
sslSweep = not na(lastSL) and low < lastSL and close > lastSL and (na(sweptL) or lastSL != sweptL)
if bslSweep
    sweptH := lastSH
if sslSweep
    sweptL := lastSL
plotshape(showSweep and bslSweep, "BSL pris", shape.triangledown, location.abovebar, color.red, text="BSL", textcolor=color.red, size=size.tiny)
plotshape(showSweep and sslSweep, "SSL pris", shape.triangleup, location.belowbar, color.green, text="SSL", textcolor=color.green, size=size.tiny)

// ───────── Niveaux clés
[pdh, pdl] = request.security(syminfo.tickerid, "D", [high[1], low[1]], lookahead=barmerge.lookahead_on)
wOpen = request.security(syminfo.tickerid, "W", open, lookahead=barmerge.lookahead_on)
var float midOpen = na
if dayofmonth(time, tz) != dayofmonth(time[1], tz)
    midOpen := open
var float monH = na
var float monL = na
newWeek = timeframe.change("W")
if newWeek
    monH := na
    monL := na
isMonday = dayofweek(time_tradingday, "UTC") == dayofweek.monday
if isMonday
    monH := na(monH) ? high : math.max(monH, high)
    monL := na(monL) ? low : math.min(monL, low)
plot(showLevels ? pdh : na, "PDH", color.new(color.purple, 0), 1, plot.style_linebr)
plot(showLevels ? pdl : na, "PDL", color.new(color.purple, 0), 1, plot.style_linebr)
plot(showLevels ? monH : na, "Monday High", color.new(color.orange, 0), 1, plot.style_linebr)
plot(showLevels ? monL : na, "Monday Low", color.new(color.orange, 0), 1, plot.style_linebr)
plot(showLevels ? midOpen : na, "Midnight Open", color.new(color.black, 0), 1, plot.style_linebr)
plot(showLevels ? wOpen : na, "Weekly Open", color.new(color.gray, 0), 1, plot.style_linebr)

// ───────── Range de travail (swings majeurs) · EQ · OTE
bigLen = swLen * 3
bph = ta.pivothigh(high, bigLen, bigLen)
bpl = ta.pivotlow(low, bigLen, bigLen)
var float rHi = na
var int   rHiBar = na
var float rLo = na
var int   rLoBar = na
if not na(bph)
    rHi := bph
    rHiBar := bar_index - bigLen
if not na(bpl)
    rLo := bpl
    rLoBar := bar_index - bigLen
var line lHi = na
var line lLo = na
var line lEq = na
var box  bOte = na
if showOTE and barstate.islast and not na(rHi) and not na(rLo) and rHi > rLo
    line.delete(lHi)
    line.delete(lLo)
    line.delete(lEq)
    box.delete(bOte)
    float rg = rHi - rLo
    int x0 = math.min(rHiBar, rLoBar)
    lHi := line.new(x0, rHi, bar_index + 10, rHi, color=color.navy, width=1)
    lLo := line.new(x0, rLo, bar_index + 10, rLo, color=color.navy, width=1)
    lEq := line.new(x0, rLo + rg / 2, bar_index + 10, rLo + rg / 2, color=color.navy, style=line.style_dotted)
    bool legUp = rLoBar < rHiBar
    float o1 = legUp ? rHi - 0.79 * rg : rLo + 0.62 * rg
    float o2 = legUp ? rHi - 0.62 * rg : rLo + 0.79 * rg
    bOte := box.new(x0, o2, bar_index + 10, o1, border_color=color.orange, bgcolor=color.new(color.orange, 88), text="OTE 0,705 · " + (legUp ? "discount (achats)" : "premium (ventes)"), text_color=color.orange, text_size=size.tiny)

// ───────── Alertes
alertcondition(bullBreak and trend == 1, "Rupture haussière", "MNQ : clôture au-dessus du dernier swing high")
alertcondition(bearBreak and trend == -1, "Rupture baissière", "MNQ : clôture sous le dernier swing low")
alertcondition(sslSweep, "SSL balayé", "MNQ : sell-side liquidity prise (SFP haussier)")
alertcondition(bslSweep, "BSL balayé", "MNQ : buy-side liquidity prise (SFP baissier)")
'''

MMM_MAP = r'''//@version=6
indicator("MMM Order-Flow Map — boussole, GMC, escalier T#, boîtes BZ, pullbacks", shorttitle="MMM Map", overlay=true, max_boxes_count=200, max_lines_count=300, max_labels_count=400, max_bars_back=500)

tz = "America/New_York"
grpC = "Boussole des bougies"
showTags = input.bool(true, "Étiquettes BC+ / BC− / AFs+ / AFs− / CI", group=grpC)
grpG = "GMC (gap-confirmed momentum)"
showGMC = input.bool(true, "Lignes GMC open", group=grpG)
maxGMC  = input.int(6, "GMC conservés", minval=1, maxval=30, group=grpG)
grpT = "Escalier de tendance"
showStair = input.bool(true, "T# · CDL/CDS · LD/SD · niveau protégé", group=grpT)
swLen     = input.int(2, "Sensibilité des swings", minval=1, maxval=10, group=grpT)
grpB = "Boîtes de session (BZ)"
showBZ   = input.bool(true, "Boîtes 18h00 / 02h00 / 09h30 (NY)", group=grpB)
openMins = input.int(30, "Durée de construction (minutes)", minval=1, maxval=240, group=grpB)
grpP = "Zones de pullback"
showPB = input.bool(true, "P–MP 87,5–75 % (bougie +) · BAL–MD 50–25 % (bougie −)", group=grpP)

// ───────── Types de bougies (lecture à la clôture)
rngC = high - low
posC = rngC > 0 ? (close - low) / rngC : 0.5
bcUp = close > high[1]
bcDn = close < low[1]
afUp = not bcUp and not bcDn and low < low[1] and close > low[1] and close <= high[1] and posC > 0.5
afDn = not bcUp and not bcDn and not afUp and high > high[1] and close < high[1] and close >= low[1] and posC < 0.5
ci   = not bcUp and not bcDn and not afUp and not afDn and high <= high[1] and low >= low[1]
plotshape(showTags and bcUp, "BC+", shape.labeldown, location.abovebar, color.new(color.white, 100), text="BC+", textcolor=color.green, size=size.tiny)
plotshape(showTags and bcDn, "BC−", shape.labelup, location.belowbar, color.new(color.white, 100), text="BC−", textcolor=color.red, size=size.tiny)
plotshape(showTags and afUp, "AFs+", shape.labeldown, location.abovebar, color.new(color.white, 100), text="AFs+", textcolor=color.teal, size=size.tiny)
plotshape(showTags and afDn, "AFs−", shape.labelup, location.belowbar, color.new(color.white, 100), text="AFs−", textcolor=color.maroon, size=size.tiny)
plotshape(showTags and ci, "CI", shape.labeldown, location.abovebar, color.new(color.white, 100), text="CI", textcolor=color.gray, size=size.tiny)

// ───────── GMC : c2 = BC, c3 laisse un vide avec c1 ; ligne à l'open de c2, supprimée sur clôture au-delà
gmcUp = bcUp[1] and low > high[2]
afsAgainst = high > high[1] and close <= high[1]
gmcDn = bcDn[1] and high < low[2]
var array<line> gL = array.new<line>()
var array<int>  gD = array.new<int>()
if showGMC and (gmcUp or gmcDn)
    int d = gmcUp ? 1 : -1
    array.push(gL, line.new(bar_index - 1, open[1], bar_index + 1, open[1], color=d == 1 ? color.green : color.red, style=line.style_dashed, width=2, extend=extend.right))
    array.push(gD, d)
    label.new(bar_index, open[1], d == 1 ? "GMC▲" : "GMC▼", style=d == 1 ? label.style_label_up : label.style_label_down, color=color.new(color.white, 100), textcolor=d == 1 ? color.green : color.red, size=size.tiny)
    if array.size(gL) > maxGMC
        line.delete(array.shift(gL))
        array.shift(gD)
if array.size(gL) > 0
    for k = array.size(gL) - 1 to 0
        ln = array.get(gL, k)
        float lv = line.get_y1(ln)
        int d = array.get(gD, k)
        if (d == 1 and close < lv) or (d == -1 and close > lv)
            line.set_extend(ln, extend.none)
            line.set_x2(ln, bar_index)
            array.remove(gL, k)
            array.remove(gD, k)

// ───────── Escalier T# (même moteur que la plateforme)
// Haussier : T1 = origine après un flip (CDL). P# = sommet avant le pullback ; clôture > P# → LD# et le creux
// du pullback (R#) devient la nouvelle marche. Clôture sous l'origine T → flip baissier (CDS). Z = T3+.
ph = ta.pivothigh(high, swLen, swLen)
pl = ta.pivotlow(low, swLen, swLen)
var int   zDir = 0
var int   zT = 0
var float tLvl = na
var int   tBar = na
var float pLvl = na
var int   pBar = na
var float zSH = na
var int   zSHb = na
var float zSL = na
var int   zSLb = na
if not na(ph)
    zSH := ph
    zSHb := bar_index - swLen
    if zDir == 1 and zSHb > tBar and (na(pLvl) or ph > pLvl)
        pLvl := ph
        pBar := zSHb
if not na(pl)
    zSL := pl
    zSLb := bar_index - swLen
    if zDir == -1 and zSLb > tBar and (na(pLvl) or pl < pLvl)
        pLvl := pl
        pBar := zSLb
// événement : 1 = flip (CDL/CDS, nouvelle T1), 2 = continuation (LD/SD, marche suivante)
int evKind = 0
int evDir = 0
float evLvl = na
int evLvlBar = na
int startBar = na
if zDir == 0
    if not na(zSH) and close > zSH
        evKind := 1
        evDir := 1
        evLvl := zSH
        evLvlBar := zSHb
        startBar := zSHb - 20
    else if not na(zSL) and close < zSL
        evKind := 1
        evDir := -1
        evLvl := zSL
        evLvlBar := zSLb
        startBar := zSLb - 20
else if zDir == 1
    if close < tLvl
        evKind := 1
        evDir := -1
        evLvl := tLvl
        evLvlBar := tBar
        startBar := tBar
    else if not na(pLvl) and close > pLvl
        evKind := 2
        evDir := 1
        evLvl := pLvl
        evLvlBar := pBar
        startBar := pBar
else
    if close > tLvl
        evKind := 1
        evDir := 1
        evLvl := tLvl
        evLvlBar := tBar
        startBar := tBar
    else if not na(pLvl) and close < pLvl
        evKind := 2
        evDir := -1
        evLvl := pLvl
        evLvlBar := pBar
        startBar := pBar
float ext = na
int extBar = na
if evKind != 0
    // origine de la nouvelle marche = extrême opposé depuis le niveau cassé (R# pour une continuation)
    int back = math.max(0, math.min(bar_index - startBar, 300))
    ext := evDir == 1 ? low : high
    extBar := bar_index
    for k = 0 to back
        if evDir == 1 and low[k] < ext
            ext := low[k]
            extBar := bar_index - k
        if evDir == -1 and high[k] > ext
            ext := high[k]
            extBar := bar_index - k
    zT := evKind == 1 ? 1 : zT + 1
    zDir := evDir
    tLvl := ext
    tBar := extBar
    pLvl := na
    pBar := na
var line protLine = na
if evKind != 0 and showStair
    string nm = evKind == 1 ? (evDir == 1 ? "CDLs" : "CDSs") : (evDir == 1 ? "LDs" : "SDs") + str.tostring(zT - 1)
    line.new(evLvlBar, evLvl, bar_index, evLvl, color=color.fuchsia, style=line.style_dashed)
    label.new(bar_index, evDir == 1 ? high : low, nm + (zT >= 3 ? " ★" : "") + " · T" + str.tostring(zT), style=evDir == 1 ? label.style_label_down : label.style_label_up, color=color.new(color.white, 100), textcolor=zT >= 3 ? color.fuchsia : (evDir == 1 ? color.green : color.red), size=size.small)
    label.new(extBar, ext, evKind == 1 ? "T1" : "R" + str.tostring(zT - 1), style=evDir == 1 ? label.style_label_up : label.style_label_down, color=color.new(color.white, 100), textcolor=color.black, size=size.tiny)
    line.delete(protLine)
    protLine := line.new(extBar, ext, bar_index + 5, ext, color=color.fuchsia, style=line.style_dotted, width=2, extend=extend.right)
alertcondition(evKind == 2 and zT >= 3, "Marche T3+ (setup Z)", "MNQ : marche T3+ — la tendance a battu l'autre côté trois fois")

// ───────── Boîtes de session BZ + balance control (1/3 – 2/3) + vPOC approximatif
mDay = hour(time, tz) * 60 + minute(time, tz)
isOpen = mDay == 18 * 60 or mDay == 2 * 60 or mDay == 9 * 60 + 30
tfMin = timeframe.in_seconds() / 60
nBars = math.max(1, int(math.round(openMins / tfMin)))
var box   bz = na
var line  l23 = na
var line  l13 = na
var line  lPoc = na
var float bzT = na
var float bzB = na
var int   built = 0
var bool  bzLive = false
var float pocV = 0.0
var float pocP = na
if showBZ and timeframe.isintraday and tfMin < 60 and isOpen
    bzT := high
    bzB := low
    built := 1
    bzLive := true
    pocV := volume
    pocP := hl2
    bz := box.new(bar_index, bzT, bar_index, bzB, border_color=color.teal, bgcolor=color.new(color.teal, 92), text="BZ", text_color=color.teal, text_size=size.tiny, text_halign=text.align_left, text_valign=text.align_top)
    l23 := line.new(bar_index, bzB, bar_index, bzB, color=color.green)
    l13 := line.new(bar_index, bzB, bar_index, bzB, color=color.red)
    lPoc := line.new(bar_index, hl2, bar_index, hl2, color=color.gray)
else if bzLive
    if built < nBars
        bzT := math.max(bzT, high)
        bzB := math.min(bzB, low)
        built += 1
        if volume > pocV
            pocV := volume
            pocP := hl2
    else if close > bzT or close < bzB
        bzLive := false
        label.new(bar_index, close > bzT ? high : low, close > bzT ? "ZBrk▲" : "ZBrk▼", style=close > bzT ? label.style_label_down : label.style_label_up, color=color.new(color.white, 100), textcolor=close > bzT ? color.green : color.red, size=size.tiny)
    float g = bzT - bzB
    float t23 = bzB + g * 2 / 3
    float t13 = bzB + g / 3
    box.set_top(bz, bzT)
    box.set_bottom(bz, bzB)
    box.set_right(bz, bar_index)
    line.set_xy1(l23, box.get_left(bz), t23)
    line.set_xy2(l23, bar_index, t23)
    line.set_xy1(l13, box.get_left(bz), t13)
    line.set_xy2(l13, bar_index, t13)
    line.set_xy1(lPoc, box.get_left(bz), pocP)
    line.set_xy2(lPoc, bar_index, pocP)
    line.set_width(l23, close >= t23 ? 3 : 1)
    line.set_width(l13, close <= t13 ? 3 : 1)

// ───────── Zone de pullback de la dernière bougie directionnelle
var box pb = na
if showPB and (bcUp or afUp or bcDn or afDn)
    box.delete(pb)
    float r = high - low
    if bcUp or afUp
        pb := box.new(bar_index, low + 0.875 * r, bar_index + 12, low + 0.75 * r, border_color=color.orange, bgcolor=color.new(color.orange, 85), text="P–MP", text_color=color.orange, text_size=size.tiny)
    else
        pb := box.new(bar_index, high - 0.25 * r, bar_index + 12, high - 0.5 * r, border_color=color.orange, bgcolor=color.new(color.orange, 85), text="BAL–MD", text_color=color.orange, text_size=size.tiny)
'''

MMPD = r'''//@version=6
indicator("MMPD — oscillateur Premium / Discount (gate de momentum)", shorttitle="MMPD", overlay=false)

lenSlow = input.int(27, "Longueur lente", minval=2)
lenFast = input.int(9, "Longueur rapide", minval=2)
smooth  = input.int(1, "Lissage (1 = brut, comme la plateforme)", minval=1)
xp      = input.float(80, "Seuil XP (extrême premium)")
xd      = input.float(20, "Seuil XD (extrême discount)")

pos(float src, int len) =>
    float hh = ta.highest(high, len)
    float ll = ta.lowest(low, len)
    hh - ll > 0 ? (src - ll) / (hh - ll) * 100 : 50.0

cLine  = ta.sma(pos(close, lenSlow), smooth)
oLine  = ta.sma(pos(open, lenSlow), smooth)
fast   = ta.sma(pos(close, lenFast), smooth)
upper  = math.max(cLine, oLine)
lower  = math.min(cLine, oLine)
inXP   = upper >= xp
inXD   = lower <= xd

plot(cLine, "MMPD 27 (c)", color.teal, 2)
plot(oLine, "MMPD 27 (o)", color.fuchsia, 1)
plot(fast, "MMPD 9", color.new(color.gray, 30), 1)
hline(xp, "XP", color.green, hline.style_dashed)
hline(50, "50", color.gray, hline.style_dotted)
hline(xd, "XD", color.red, hline.style_dashed)
bgcolor(inXP ? color.new(color.green, 88) : inXD ? color.new(color.red, 88) : na)
alertcondition(inXP and not inXP[1], "Entrée en XP", "MMPD : longs autorisés (momentum)")
alertcondition(inXD and not inXD[1], "Entrée en XD", "MMPD : shorts autorisés (momentum)")
'''

ALIGN = r'''//@version=6
indicator("Tempête parfaite — alignement multi-UT (Daily · 4H · 1H · 15m)", shorttitle="Alignement MTF", overlay=true)

// Type de la dernière bougie CLÔTURÉE : 2 = BC+, 1 = AFs+, -1 = AFs−, -2 = BC−, 0 = autre
ctype() =>
    float r = high - low
    float p = r > 0 ? (close - low) / r : 0.5
    int t = 0
    if close > high[1]
        t := 2
    else if close < low[1]
        t := -2
    else if low < low[1] and close > low[1] and p > 0.5
        t := 1
    else if high > high[1] and close < high[1] and p < 0.5
        t := -1
    t

tD  = request.security(syminfo.tickerid, "D", ctype()[1], lookahead=barmerge.lookahead_on)
t4  = request.security(syminfo.tickerid, "240", ctype()[1], lookahead=barmerge.lookahead_on)
t1  = request.security(syminfo.tickerid, "60", ctype()[1], lookahead=barmerge.lookahead_on)
t15 = request.security(syminfo.tickerid, "15", ctype()[1], lookahead=barmerge.lookahead_on)

txt(int t) => t == 2 ? "BC+" : t == -2 ? "BC−" : t == 1 ? "AFs+" : t == -1 ? "AFs−" : "—"
col(int t) => t > 0 ? color.green : t < 0 ? color.red : color.gray

var table tb = table.new(position.top_right, 2, 6, bgcolor=color.white, border_color=color.gray, border_width=1)
if barstate.islast
    int bull = (tD == 2 ? 1 : 0) + (t4 == 2 ? 1 : 0) + (t1 == 2 ? 1 : 0) + (t15 == 2 ? 1 : 0)
    int bear = (tD == -2 ? 1 : 0) + (t4 == -2 ? 1 : 0) + (t1 == -2 ? 1 : 0) + (t15 == -2 ? 1 : 0)
    int n = math.max(bull, bear)
    table.cell(tb, 0, 0, "UT", text_color=color.black)
    table.cell(tb, 1, 0, "Dernière bougie", text_color=color.black)
    table.cell(tb, 0, 1, "Daily", text_color=color.black)
    table.cell(tb, 1, 1, txt(tD), text_color=col(tD))
    table.cell(tb, 0, 2, "4H", text_color=color.black)
    table.cell(tb, 1, 2, txt(t4), text_color=col(t4))
    table.cell(tb, 0, 3, "1H", text_color=color.black)
    table.cell(tb, 1, 3, txt(t1), text_color=col(t1))
    table.cell(tb, 0, 4, "15m", text_color=color.black)
    table.cell(tb, 1, 4, txt(t15), text_color=col(t15))
    table.cell(tb, 0, 5, "Alignement", text_color=color.black)
    table.cell(tb, 1, 5, str.tostring(n) + "/4 " + (bull > bear ? "haussier" : bear > bull ? "baissier" : "neutre"), text_color=bull > bear ? color.green : bear > bull ? color.red : color.black)
'''

STRATEGY = r'''//@version=6
strategy("ICT × MMM Edge Lab — MNQ (backtest)", shorttitle="Edge Lab", overlay=true, process_orders_on_close=true, default_qty_type=strategy.fixed, default_qty_value=2, commission_type=strategy.commission.cash_per_contract, commission_value=0.52, slippage=1, max_labels_count=300, max_bars_back=500)

tz = "America/New_York"
grpS = "Setups"
useZ   = input.bool(true, "Z · marche T3+ (LD2+/SD2+) à la clôture", group=grpS)
useG   = input.bool(true, "G · GMC long (clôture c3)", group=grpS)
useB   = input.bool(true, "B · GMC long dont c3 fait un nouveau haut et réintègre c2 (AFs contre)", group=grpS)
useM   = input.bool(false, "M · BC+ long (sans plus bas inférieur, clôture moitié haute)", group=grpS)
useICT = input.bool(true, "ICT · sweep de liquidité puis MSS (méthode C, entrée clôture)", group=grpS)
swLen  = input.int(2, "Sensibilité des swings", minval=1, maxval=10, group=grpS)
grpR = "Risque & sorties"
qtyC     = input.int(2, "Contrats MNQ (≥ 2 pour la ½ sortie)", minval=1, group=grpR)
stopMode = input.string("ATR", "Stop", options=["ATR", "Fixe (points)"], group=grpR)
atrMult  = input.float(1.5, "Multiple d'ATR(14)", minval=0.1, step=0.1, group=grpR)
fixPts   = input.float(50, "Stop fixe (points)", minval=1, group=grpR)
useHalf  = input.bool(true, "½ sortie puis stop à l'entrée", group=grpR)
halfR    = input.float(0.5, "½ sortie à + (R)", minval=0.1, step=0.1, group=grpR)
runR     = input.float(3.0, "Objectif runner (R)", minval=0.5, step=0.5, group=grpR)
maxBars  = input.int(64, "Sortie forcée après (bougies)", minval=1, group=grpR)
grpF = "Filtres"
fSess  = input.string("Asie + NY AM", "Sessions", options=["Toutes", "Asie + NY AM", "NY AM"], group=grpF)
skip02 = input.bool(true, "Ignorer 00h00–02h00 (fin d'Asie)", group=grpF)
fGate  = input.bool(true, "Gate MMPD 27 momentum (long XP / short XD)", group=grpF)
fDaily = input.bool(true, "Bougie journalière d'hier dans le sens", group=grpF)
grpP = "Compte prop (aide au sizing)"
propDD   = input.float(2500, "Drawdown autorisé ($)", group=grpP)
splitPct = input.float(70, "Période ancienne (%) / récente", minval=10, maxval=90, group=grpP)

// ───────── Filtres
inS(string s) => not na(time(timeframe.period, s, tz))
okSess = fSess == "Toutes" ? true : fSess == "NY AM" ? inS("0930-1330") : (inS("0930-1330") or inS("1800-0200"))
okSess := okSess and not (skip02 and inS("0000-0200"))
pos27(float src) =>
    float hh = ta.highest(high, 27)
    float ll = ta.lowest(low, 27)
    hh - ll > 0 ? (src - ll) / (hh - ll) * 100 : 50.0
mc = pos27(close)
mo = pos27(open)
xpOk = math.max(mc, mo) >= 80
xdOk = math.min(mc, mo) <= 20
[dO, dC] = request.security(syminfo.tickerid, "D", [open[1], close[1]], lookahead=barmerge.lookahead_on)
dUp = dC > dO
dDn = dC < dO

// ───────── Bougies & GMC
bcUp = close > high[1]
gmcUp = bcUp[1] and low > high[2]
afsAgainst = high > high[1] and close <= high[1]
rngC = high - low
mLong = bcUp and low >= low[1] and rngC > 0 and (close - low) / rngC >= 0.5

// ───────── Escalier (setup Z) — même moteur que la plateforme
ph = ta.pivothigh(high, swLen, swLen)
pl = ta.pivotlow(low, swLen, swLen)
var int   zDir = 0
var int   zT = 0
var float tLvl = na
var int   tBar = na
var float pLvl = na
var int   pBar = na
var float zSH = na
var int   zSHb = na
var float zSL = na
var int   zSLb = na
if not na(ph)
    zSH := ph
    zSHb := bar_index - swLen
    if zDir == 1 and zSHb > tBar and (na(pLvl) or ph > pLvl)
        pLvl := ph
        pBar := zSHb
if not na(pl)
    zSL := pl
    zSLb := bar_index - swLen
    if zDir == -1 and zSLb > tBar and (na(pLvl) or pl < pLvl)
        pLvl := pl
        pBar := zSLb
// événement : 1 = flip (CDL/CDS, nouvelle T1), 2 = continuation (LD/SD, marche suivante)
int evKind = 0
int evDir = 0
float evLvl = na
int evLvlBar = na
int startBar = na
if zDir == 0
    if not na(zSH) and close > zSH
        evKind := 1
        evDir := 1
        evLvl := zSH
        evLvlBar := zSHb
        startBar := zSHb - 20
    else if not na(zSL) and close < zSL
        evKind := 1
        evDir := -1
        evLvl := zSL
        evLvlBar := zSLb
        startBar := zSLb - 20
else if zDir == 1
    if close < tLvl
        evKind := 1
        evDir := -1
        evLvl := tLvl
        evLvlBar := tBar
        startBar := tBar
    else if not na(pLvl) and close > pLvl
        evKind := 2
        evDir := 1
        evLvl := pLvl
        evLvlBar := pBar
        startBar := pBar
else
    if close > tLvl
        evKind := 1
        evDir := 1
        evLvl := tLvl
        evLvlBar := tBar
        startBar := tBar
    else if not na(pLvl) and close < pLvl
        evKind := 2
        evDir := -1
        evLvl := pLvl
        evLvlBar := pBar
        startBar := pBar
float ext = na
int extBar = na
if evKind != 0
    // origine de la nouvelle marche = extrême opposé depuis le niveau cassé (R# pour une continuation)
    int back = math.max(0, math.min(bar_index - startBar, 300))
    ext := evDir == 1 ? low : high
    extBar := bar_index
    for k = 0 to back
        if evDir == 1 and low[k] < ext
            ext := low[k]
            extBar := bar_index - k
        if evDir == -1 and high[k] > ext
            ext := high[k]
            extBar := bar_index - k
    zT := evKind == 1 ? 1 : zT + 1
    zDir := evDir
    tLvl := ext
    tBar := extBar
    pLvl := na
    pBar := na
zLong  = useZ and evKind == 2 and evDir == 1 and zT >= 3
zShort = useZ and evKind == 2 and evDir == -1 and zT >= 3

// ───────── ICT méthode C simplifiée : sweep de liquidité puis rupture de structure opposée (MSS) à la clôture
var float sH = na
var bool  sHu = true
var float sL = na
var bool  sLu = true
var int   iDir = 0
var int   lastSSL = -1000
var int   lastBSL = -1000
if not na(ph)
    sH := ph
    sHu := false
if not na(pl)
    sL := pl
    sLu := false
if not na(sL) and low < sL and close > sL
    lastSSL := bar_index
if not na(sH) and high > sH and close < sH
    lastBSL := bar_index
upBrk = not sHu and not na(sH) and close > sH
dnBrk = not sLu and not na(sL) and close < sL
bool mssUp = false
bool mssDn = false
if upBrk
    mssUp := iDir == -1
    iDir := 1
    sHu := true
if dnBrk
    mssDn := iDir == 1
    iDir := -1
    sLu := true
ictLong  = useICT and mssUp and bar_index - lastSSL <= 40
ictShort = useICT and mssDn and bar_index - lastBSL <= 40
gLong = useG and gmcUp
bLong = useB and gmcUp and afsAgainst
mL    = useM and mLong

longSig  = (zLong or gLong or bLong or mL or ictLong) and okSess and (not fGate or xpOk) and (not fDaily or dUp)
shortSig = (zShort or ictShort) and okSess and (not fGate or xdOk) and (not fDaily or dDn)

// ───────── Gestion
atr14 = ta.atr(14)
var float ePx = na
var float slPx = na
var float t1Px = na
var float t2Px = na
var bool  halfHit = false
var int   eBar = na
var map<int, float> riskMap = map.new<int, float>()
stopDist = stopMode == "ATR" ? atrMult * atr14 : fixPts
bool newL = false
bool newS = false
if strategy.position_size == 0
    halfHit := false
    if longSig
        ePx := close
        slPx := close - stopDist
        t1Px := close + stopDist * halfR
        t2Px := close + stopDist * runR
        eBar := bar_index
        map.put(riskMap, time, stopDist * syminfo.pointvalue * qtyC)
        strategy.entry("L", strategy.long, qty=qtyC, comment=zLong ? "Z" : ictLong ? "ICT" : bLong ? "B" : gLong ? "G" : "M")
        newL := true
    else if shortSig
        ePx := close
        slPx := close + stopDist
        t1Px := close - stopDist * halfR
        t2Px := close - stopDist * runR
        eBar := bar_index
        map.put(riskMap, time, stopDist * syminfo.pointvalue * qtyC)
        strategy.entry("S", strategy.short, qty=qtyC, comment=zShort ? "Z" : "ICT")
        newS := true
if strategy.position_size > 0 or newL
    if not newL and high >= t1Px
        halfHit := true
    if useHalf
        strategy.exit("L½", "L", qty_percent=50, limit=t1Px, stop=slPx)
        strategy.exit("LR", "L", limit=t2Px, stop=halfHit ? ePx : slPx)
    else
        strategy.exit("LX", "L", limit=t2Px, stop=slPx)
if strategy.position_size < 0 or newS
    if not newS and low <= t1Px
        halfHit := true
    if useHalf
        strategy.exit("S½", "S", qty_percent=50, limit=t1Px, stop=slPx)
        strategy.exit("SR", "S", limit=t2Px, stop=halfHit ? ePx : slPx)
    else
        strategy.exit("SX", "S", limit=t2Px, stop=slPx)
if strategy.position_size != 0 and not na(eBar) and bar_index - eBar >= maxBars
    strategy.close_all(comment="Temps")

plot(strategy.position_size != 0 ? slPx : na, "Stop", color.red, 1, plot.style_linebr)
plot(strategy.position_size != 0 ? t2Px : na, "Objectif", color.green, 1, plot.style_linebr)

// ───────── Statistiques (même lecture que la plateforme) : WR, avg RR, PF, t-score, DD en R, pertes de suite
var table st = table.new(position.bottom_right, 2, 11, bgcolor=color.white, border_color=color.gray, border_width=1)
if barstate.islastconfirmedhistory or barstate.islast
    map<int, float> pnl = map.new<int, float>()
    if strategy.closedtrades > 0
        for i = 0 to strategy.closedtrades - 1
            int k = strategy.closedtrades.entry_time(i)
            float prev = map.contains(pnl, k) ? map.get(pnl, k) : 0.0
            map.put(pnl, k, prev + strategy.closedtrades.profit(i))
    array<int> keys = map.keys(pnl)
    array.sort(keys)
    int n = array.size(keys)
    float sumR = 0.0
    float sumR2 = 0.0
    float gw = 0.0
    float gl = 0.0
    int wins = 0
    float eq = 0.0
    float peak = 0.0
    float mdd = 0.0
    int run = 0
    int streak = 0
    int nOld = int(n * splitPct / 100)
    float sOld = 0.0
    float sNew = 0.0
    if n > 0
        for j = 0 to n - 1
            int k = array.get(keys, j)
            float rk = map.contains(riskMap, k) ? map.get(riskMap, k) : na
            float r = na(rk) or rk == 0 ? 0.0 : map.get(pnl, k) / rk
            sumR += r
            sumR2 += r * r
            if r > 0
                wins += 1
                gw += r
                run := 0
            else
                gl -= r
                run += 1
                streak := math.max(streak, run)
            eq += r
            peak := math.max(peak, eq)
            mdd := math.max(mdd, peak - eq)
            if j < nOld
                sOld += r
            else
                sNew += r
    float avg = n > 0 ? sumR / n : na
    float sd = n > 1 ? math.sqrt(math.max((sumR2 - n * avg * avg) / (n - 1), 0)) : na
    float tsc = n > 1 and sd > 0 ? avg / (sd / math.sqrt(n)) : na
    float pf = gl > 0 ? gw / gl : na
    float aOld = nOld > 0 ? sOld / nOld : na
    float aNew = n - nOld > 0 ? sNew / (n - nOld) : na
    string verdict = n < 30 ? "WATCH (trop peu de trades)" : (aOld > 0 and aNew > 0 and tsc >= 2) ? "TRADE" : (aOld > 0 and aNew > 0) ? "WATCH" : "DON'T TRADE"
    float riskSugg = mdd > 0 ? propDD / (mdd * 1.5) : na
    table.cell(st, 0, 0, "Trades", text_color=color.black)
    table.cell(st, 1, 0, str.tostring(n), text_color=color.black)
    table.cell(st, 0, 1, "Win rate", text_color=color.black)
    table.cell(st, 1, 1, n > 0 ? str.tostring(wins * 100.0 / n, "#.0") + " %" : "—", text_color=color.black)
    table.cell(st, 0, 2, "avg RR (après coûts)", text_color=color.black)
    table.cell(st, 1, 2, str.tostring(avg, "+#.000;-#.000"), text_color=avg > 0 ? color.green : color.red)
    table.cell(st, 0, 3, "Profit factor (en R)", text_color=color.black)
    table.cell(st, 1, 3, str.tostring(pf, "#.00"), text_color=color.black)
    table.cell(st, 0, 4, "t-score", text_color=color.black)
    table.cell(st, 1, 4, str.tostring(tsc, "#.00"), text_color=tsc >= 2 ? color.green : color.black)
    table.cell(st, 0, 5, "Max DD (R)", text_color=color.black)
    table.cell(st, 1, 5, str.tostring(mdd, "#.0"), text_color=color.black)
    table.cell(st, 0, 6, "Pertes de suite (max)", text_color=color.black)
    table.cell(st, 1, 6, str.tostring(streak), text_color=color.black)
    table.cell(st, 0, 7, "avg RR ancien → récent", text_color=color.black)
    table.cell(st, 1, 7, str.tostring(aOld, "+#.00;-#.00") + " → " + str.tostring(aNew, "+#.00;-#.00"), text_color=color.black)
    table.cell(st, 0, 8, "Verdict", text_color=color.black)
    table.cell(st, 1, 8, verdict, text_color=verdict == "TRADE" ? color.green : verdict == "DON'T TRADE" ? color.red : color.orange)
    table.cell(st, 0, 9, "Risque max / trade (prop)", text_color=color.black)
    table.cell(st, 1, 9, na(riskSugg) ? "—" : str.tostring(riskSugg, "#") + " $", text_color=color.black)
    table.cell(st, 0, 10, "Lecture", text_color=color.black)
    table.cell(st, 1, 10, "t ≥ 2 = edge probable · t ≥ 3 = preuve forte", text_color=color.black)
'''

EDGE_DESK = r'''//@version=6
indicator("Edge 5 Desk — MNQ (ICT × MMM)", shorttitle="Edge 5 Desk", overlay=true, max_lines_count=500, max_labels_count=500, max_boxes_count=100, max_bars_back=1000)

// Mêmes règles que la page « Edge Desk » de la plateforme ICT MNQ Academy (core/edge.py).
// Unité de décision : 15 minutes. Tout est calculé à la CLÔTURE des bougies (aucun repaint).
tz = "America/New_York"

// ───────── Réglages
grpS = "Setups"
useZ  = input.bool(true, "M1 · Z marche T3+ (long + short)", group=grpS)
useG  = input.bool(true, "M2 · G GMC long", group=grpS)
useB  = input.bool(true, "M3 · B GMC AFs contre", group=grpS)
useC  = input.bool(true, "M4 · C contraction limite 75 % (remplie en Asie)", group=grpS)
useM  = input.bool(true, "M5 · M BC+ long", group=grpS)
swLen = input.int(2, "Sensibilité des swings (escalier)", minval=1, maxval=10, group=grpS)
grpF = "Filtres & gestion"
halfOut = input.bool(true, "½ sortie puis stop à l'entrée", group=grpF)
fGate   = input.bool(true, "Gate MMPD 27 momentum (long XP · short XD)", group=grpF)
fDaily  = input.bool(true, "Filtre bougie journalière d'hier", group=grpF)
fH1     = input.bool(true, "Filtre tendance 1H (escalier)", group=grpF)
fSess   = input.bool(true, "Asie 18h–02h + NY AM 09h30–13h30 (00h–02h exclu sauf C)", group=grpF)
maxOpen = input.int(2, "Positions max", minval=1, maxval=5, group=grpF)
costPts = input.float(1.0, "Coût par trade (points)", minval=0, step=0.25, group=grpF)
maxBars = input.int(96, "Sortie forcée après (bougies)", minval=1, group=grpF)
grpP = "Compte prop"
qty        = input.int(2, "Contrats (instrument du graphique)", minval=1, group=grpP)
propTarget = input.float(3000, "Objectif de profit ($)", group=grpP)
propDD     = input.float(2500, "Drawdown suiveur ($)", group=grpP)
propN      = input.int(300, "Trades récents utilisés pour le prop helper", minval=20, maxval=1000, group=grpP)
grpV = "Affichage"
showLines = input.bool(true, "Lignes de trades M#T#", group=grpV)
showDesk  = input.bool(true, "Tableau EDGE DESK", group=grpV)
showProp  = input.bool(true, "Tableau PROP HELPER", group=grpV)

// ───────── Paramètres des 5 setups (index 0..4 = M1..M5)
var array<float>  stopK   = array.from(1.5, 1.0, 1.0, 50.0, 50.0)
var array<bool>   stopAtr = array.from(true, true, true, false, false)
var array<float>  halfK   = array.from(0.5, 0.75, 0.5, 0.5, 0.5)
var array<float>  tpK     = array.from(6.0, 3.0, 6.0, 2.0, 2.0)
var array<string> sName   = array.from("M1 · Z T3+ BREAK", "M2 · G GMC LONG", "M3 · B GMC AFs", "M4 · C CONTR LIMIT", "M5 · M BC+ LONG")
var array<string> sHTF    = array.from("D · 15m · 15m", "D · 15m · 15m", "D+1H · 15m · 15m", "— · 15m · 15m lmt", "D+1H · 15m · 15m")

// ───────── Escalier de tendance (moteur swing) : flip = T1, continuation = marche suivante, Z = T3+
f_stair(int n) =>
    float ph = ta.pivothigh(high, n, n)
    float pl = ta.pivotlow(low, n, n)
    var int   zDir = 0
    var int   zT = 0
    var float tLvl = na
    var int   tBar = na
    var float pLvl = na
    var int   pBar = na
    var float zSH = na
    var int   zSHb = na
    var float zSL = na
    var int   zSLb = na
    if not na(ph)
        zSH := ph
        zSHb := bar_index - n
        if zDir == 1 and zSHb > tBar and (na(pLvl) or ph > pLvl)
            pLvl := ph
            pBar := zSHb
    if not na(pl)
        zSL := pl
        zSLb := bar_index - n
        if zDir == -1 and zSLb > tBar and (na(pLvl) or pl < pLvl)
            pLvl := pl
            pBar := zSLb
    int evKind = 0
    int evDir = 0
    int startBar = na
    if zDir == 0
        if not na(zSH) and close > zSH
            evKind := 1
            evDir := 1
            startBar := zSHb - 20
        else if not na(zSL) and close < zSL
            evKind := 1
            evDir := -1
            startBar := zSLb - 20
    else if zDir == 1
        if close < tLvl
            evKind := 1
            evDir := -1
            startBar := tBar
        else if not na(pLvl) and close > pLvl
            evKind := 2
            evDir := 1
            startBar := pBar
    else
        if close > tLvl
            evKind := 1
            evDir := 1
            startBar := tBar
        else if not na(pLvl) and close < pLvl
            evKind := 2
            evDir := -1
            startBar := pBar
    if evKind != 0
        int back = math.max(0, math.min(bar_index - startBar, 300))
        float ext = evDir == 1 ? low : high
        int extBar = bar_index
        for k = 0 to back
            if evDir == 1 and low[k] < ext
                ext := low[k]
                extBar := bar_index - k
            if evDir == -1 and high[k] > ext
                ext := high[k]
                extBar := bar_index - k
        zT := evKind == 1 ? 1 : zT + 1
        zDir := evDir
        tLvl := ext
        tBar := extBar
        pLvl := na
        pBar := na
    [zDir, zT, evKind, evDir, pLvl, tLvl]

f_h1dir(int n) =>
    [d, t, e, ed, p, tl] = f_stair(n)
    d[1]

[sDir, sT, sEv, sEvDir, sP, sTL] = f_stair(swLen)
h1Dir = request.security(syminfo.tickerid, "60", f_h1dir(swLen), lookahead=barmerge.lookahead_on)
[dO, dC] = request.security(syminfo.tickerid, "D", [open[1], close[1]], lookahead=barmerge.lookahead_on)
dDir = dC > dO ? 1 : dC < dO ? -1 : 0

// ───────── MMPD 27 (position du prix dans son range, ligne c = clôture, ligne o = ouverture)
hh27 = ta.highest(high, 27)
ll27 = ta.lowest(low, 27)
mC = hh27 - ll27 > 0 ? (close - ll27) / (hh27 - ll27) * 100 : 50.0
mO = hh27 - ll27 > 0 ? (open - ll27) / (hh27 - ll27) * 100 : 50.0
xpOk = math.max(mC, mO) >= 80
xdOk = math.min(mC, mO) <= 20

// ───────── Bougies, GMC, contraction
atr14  = ta.atr(14)
bcUp   = close > high[1]
gmcUp  = bcUp[1] and low > high[2]
afsAg  = high > high[1] and close <= high[1]
mLong  = bcUp and low >= low[1] and high - low > 0 and close - low >= 0.5 * (high - low)
boxHi  = ta.highest(high, 5)[1]
boxLo  = ta.lowest(low, 5)[1]
cBreak = boxHi - boxLo <= 1.6 * atr14[1] and close > boxHi

// ───────── Sessions (heure de New York)
inAsia = not na(time(timeframe.period, "1800-0200", tz))
inNY   = not na(time(timeframe.period, "0930-1330", tz))
inDead = not na(time(timeframe.period, "0000-0200", tz))

f_reason(int sid, int d) =>
    string r = ""
    if fSess and sid != 3 and (not (inAsia or inNY) or inDead)
        r := "time"
    else if fGate and not ((d == 1 and xpOk) or (d == -1 and xdOk))
        r := "gate"
    else if fDaily and sid != 3 and dDir != d
        r := "daily"
    else if fH1 and (sid == 2 or sid == 4) and h1Dir != d
        r := "1h"
    r

// ───────── Trades simulés
type Trade
    int   sid
    int   num
    int   dir
    float entry
    float stop
    float risk
    float halfPx
    float tp
    bool  halfDone
    int   ebar
    int   etime
    line  lE
    line  lS
    line  lH
    line  lT
    label lb

var array<Trade> openT  = array.new<Trade>()
var array<int>   cnt    = array.from(0, 0, 0, 0, 0)
var array<float> allR   = array.new<float>()
var array<float> allPts = array.new<float>()
var array<int>   allSid = array.new<int>()
var array<int>   allT0  = array.new<int>()
var array<int>   allT1  = array.new<int>()

f_hasSid(int sid) =>
    bool f = false
    if array.size(openT) > 0
        for t in openT
            if t.sid == sid
                f := true
    f

f_open(int sid, int d, float px, float risk) =>
    int n = array.get(cnt, sid) + 1
    array.set(cnt, sid, n)
    float hp = px + d * risk * array.get(halfK, sid)
    float tpx = px + d * risk * array.get(tpK, sid)
    float sl = px - d * risk
    line le = na
    line ls = na
    line lh = na
    line lt = na
    label lbl = na
    string tag = "M" + str.tostring(sid + 1) + "T" + str.tostring(n)
    if showLines
        le := line.new(bar_index, px, bar_index + 1, px, color=color.black, width=1)
        ls := line.new(bar_index, sl, bar_index + 1, sl, color=color.red, width=1)
        if halfOut
            lh := line.new(bar_index, hp, bar_index + 1, hp, color=color.blue, style=line.style_dotted)
        lt := line.new(bar_index, tpx, bar_index + 1, tpx, color=color.green, width=2)
        lbl := label.new(bar_index, tpx, tag + (d == 1 ? " LONG" : " SHORT"), style=d == 1 ? label.style_label_down : label.style_label_up, color=color.new(color.white, 100), textcolor=color.blue, size=size.small)
    array.push(openT, Trade.new(sid, n, d, px, sl, risk, hp, tpx, false, bar_index, time, le, ls, lh, lt, lbl))
    alert(tag + " " + array.get(sName, sid) + (d == 1 ? " LONG" : " SHORT") + " | entrée " + str.tostring(px, format.mintick) + " | SL " + str.tostring(sl, format.mintick) + " | ½ " + str.tostring(hp, format.mintick) + " | TP " + str.tostring(tpx, format.mintick), alert.freq_once_per_bar_close)

f_close(Trade t, float px, string why) =>
    float rg = t.halfDone ? 0.5 * array.get(halfK, t.sid) + 0.5 * (px - t.entry) * t.dir / t.risk : (px - t.entry) * t.dir / t.risk
    float r = rg - costPts / t.risk
    float pts = r * t.risk
    float usd = pts * syminfo.pointvalue * qty
    array.push(allR, r)
    array.push(allPts, pts)
    array.push(allSid, t.sid)
    array.push(allT0, t.etime)
    array.push(allT1, time)
    if showLines
        line.set_x2(t.lE, bar_index)
        line.set_x2(t.lS, bar_index)
        line.set_x2(t.lT, bar_index)
        if not na(t.lH)
            line.set_x2(t.lH, bar_index)
        label.delete(t.lb)
        label.new(bar_index, t.tp, "M" + str.tostring(t.sid + 1) + "T" + str.tostring(t.num) + " " + why + " | " + (usd >= 0 ? "+" : "") + str.tostring(usd, "#,##0") + " $ (" + str.tostring(pts, "+0.0;-0.0") + " pts)", style=label.style_label_left, color=color.new(color.white, 100), textcolor=r > 0 ? color.green : color.red, size=size.small)
    r

f_try(int sid, int d, bool sig) =>
    bool ok = false
    if sig and f_reason(sid, d) == "" and array.size(openT) < maxOpen and not f_hasSid(sid)
        float risk = array.get(stopAtr, sid) ? array.get(stopK, sid) * atr14 : array.get(stopK, sid)
        if not na(risk) and risk >= 4 * syminfo.mintick
            f_open(sid, d, close, risk)
            ok := true
    ok

var float pLim = na
var int   pBarC = na
var bool  pOn = false
bool firedZ = false
bool firedG = false
bool firedB = false
bool firedC = false
bool firedM = false

if barstate.isconfirmed
    // 1) gestion des positions ouvertes (stop prioritaire, ½ puis stop à l'entrée, objectif, flip, temps)
    if array.size(openT) > 0
        for k = array.size(openT) - 1 to 0
            Trade t = array.get(openT, k)
            if t.ebar < bar_index
                bool done = false
                bool hitStop = t.dir == 1 ? low <= t.stop : high >= t.stop
                if hitStop
                    float px = t.dir == 1 ? math.min(open, t.stop) : math.max(open, t.stop)
                    f_close(t, px, t.halfDone ? "trail stop, profit kept" : "stop")
                    done := true
                else
                    if halfOut and not t.halfDone and (t.dir == 1 ? high >= t.halfPx : low <= t.halfPx)
                        t.halfDone := true
                        t.stop := t.entry
                    if t.dir == 1 ? high >= t.tp : low <= t.tp
                        f_close(t, t.tp, "TP")
                        done := true
                    else if t.sid == 0 and sEv == 1 and sEvDir == -t.dir
                        f_close(t, close, "flip")
                        done := true
                    else if bar_index - t.ebar >= maxBars
                        f_close(t, close, "temps")
                        done := true
                if done
                    array.remove(openT, k)
                else if showLines
                    line.set_x2(t.lE, bar_index + 1)
                    line.set_x2(t.lS, bar_index + 1)
                    line.set_x2(t.lT, bar_index + 1)
                    if not na(t.lH)
                        line.set_x2(t.lH, bar_index + 1)
    // 2) limite M4 : remplie 1 tick au travers, en Asie
    if pOn and bar_index > pBarC
        if bar_index - pBarC > 20 or high >= pLim + 2 * 50.0
            pOn := false
        else if low <= pLim - syminfo.mintick and (inAsia or not fSess)
            if array.size(openT) < maxOpen and not f_hasSid(3)
                f_open(3, 1, pLim, 50.0)
                firedC := true
            pOn := false
    // 3) nouveaux signaux à la clôture
    if useZ
        firedZ := f_try(0, 1, sEv == 2 and sEvDir == 1 and sT >= 3)
        firedZ := f_try(0, -1, sEv == 2 and sEvDir == -1 and sT >= 3) or firedZ
    if useG
        firedG := f_try(1, 1, gmcUp)
    if useB
        firedB := f_try(2, 1, gmcUp and afsAg)
    if useC and cBreak and not pOn and (not fGate or xpOk)
        pLim := low + 0.75 * (high - low)
        pBarC := bar_index
        pOn := true
    if useM
        firedM := f_try(4, 1, mLong)

alertcondition(firedZ or firedG or firedB or firedC or firedM, "Edge 5 : nouveau trade", "Edge 5 Desk : un setup vient de se déclencher sur MNQ (voir le graphique)")
plot(pOn ? pLim : na, "Limite M4", color.blue, 1, plot.style_linebr)

// ───────── Statistiques par setup (index 5 = ALL 5)
f_stats(int sid) =>
    int sz = array.size(allR)
    int n = 0
    float s = 0.0
    float s2 = 0.0
    int w = 0
    float eq = 0.0
    float pk = 0.0
    float dd = 0.0
    if sz > 0
        for i = 0 to sz - 1
            if sid == 5 or array.get(allSid, i) == sid
                float r = array.get(allR, i)
                n += 1
                s += r
                s2 += r * r
                w += r > 0 ? 1 : 0
                eq += r
                pk := math.max(pk, eq)
                dd := math.max(dd, pk - eq)
    int nOld = int(n * 0.7)
    float so = 0.0
    float sn = 0.0
    int j = 0
    if sz > 0
        for i = 0 to sz - 1
            if sid == 5 or array.get(allSid, i) == sid
                if j < nOld
                    so += array.get(allR, i)
                else
                    sn += array.get(allR, i)
                j += 1
    float avg = n > 0 ? s / n : na
    float sd = n > 1 ? math.sqrt(math.max((s2 - n * avg * avg) / (n - 1), 0)) : na
    float tsc = n > 1 and sd > 0 ? avg / (sd / math.sqrt(n)) : na
    float wr = n > 0 ? w * 100.0 / n : na
    float aOld = nOld > 0 ? so / nOld : na
    float aNew = n - nOld > 0 ? sn / (n - nOld) : na
    [n, wr, aOld, aNew, tsc, dd]

f_verdict(int n, float aOld, float aNew, float tsc) =>
    n == 0 ? "—" : (n >= 30 and aOld > 0 and aNew > 0 and tsc >= 2.5) ? "TRADE" : (aOld > 0 and aNew > 0) ? "WATCH" : "DON'T TRADE"

// Évaluation prop rejouée sur l'historique : départ à chaque trade (échantillonné), jusqu'à l'objectif ou au drawdown suiveur
f_prop(int sid, int size) =>
    int sz = array.size(allR)
    int first = math.max(0, sz - propN)
    int passes = 0
    int fails = 0
    array<float> days = array.new<float>()
    int nS = 0
    if sz > 0
        for i = first to sz - 1
            if sid == 5 or array.get(allSid, i) == sid
                nS += 1
    int step = math.max(1, int(nS / 60))
    int seen = 0
    if sz > 0
        for j = first to sz - 1
            if sid == 5 or array.get(allSid, j) == sid
                seen += 1
                if seen % step == 0
                    float eq = 0.0
                    float pk = 0.0
                    for k = j to sz - 1
                        if sid == 5 or array.get(allSid, k) == sid
                            eq += array.get(allPts, k) * syminfo.pointvalue * size
                            pk := math.max(pk, eq)
                            float fl = math.min(pk - propDD, 100.0)
                            if eq >= propTarget
                                passes += 1
                                array.push(days, (array.get(allT1, k) - array.get(allT0, j)) / 86400000.0)
                                break
                            if eq <= fl
                                fails += 1
                                break
    int dec = passes + fails
    float pr = dec > 0 ? passes * 100.0 / dec : na
    float md = array.size(days) > 0 ? array.median(days) : na
    [pr, passes, fails, md]

f_now(int sid) =>
    string st = ""
    if sid == 0
        bool sigL = sEv == 2 and sEvDir == 1 and sT >= 3
        bool sigS = sEv == 2 and sEvDir == -1 and sT >= 3
        string rl = f_reason(0, 1)
        string rs = f_reason(0, -1)
        st := (sigL and rl == "") or (sigS and rs == "") ? "FIRE" : (rl != "" and rs != "") ? "OFF · " + rl : "ON · wait"
    else if sid == 3
        st := pOn ? "LIMIT " + str.tostring(pLim, format.mintick) : (inAsia or not fSess) ? "ON · wait" : "OFF · time"
    else
        bool sig = sid == 1 ? gmcUp : sid == 2 ? gmcUp and afsAg : mLong
        string r = f_reason(sid, 1)
        st := r != "" ? "OFF · " + r : sig ? "FIRE" : "ON · wait"
    st

colTxt(string v) => v == "TRADE" ? color.green : v == "DON'T TRADE" ? color.red : v == "WATCH" ? color.orange : color.black

var table desk = table.new(position.top_right, 7, 16, bgcolor=color.white, border_color=color.new(color.gray, 40), border_width=1, frame_color=color.black, frame_width=1)
var table prop = table.new(position.bottom_right, 5, 9, bgcolor=color.white, border_color=color.new(color.gray, 40), border_width=1, frame_color=color.black, frame_width=1)

if barstate.islast
    if showDesk
        table.clear(desk, 0, 0, 6, 15)
        table.cell(desk, 0, 0, "EDGE 5 DESK · " + syminfo.ticker + " · " + timeframe.period + " · " + (halfOut ? "½ OUT" : "FULL") + " · max " + str.tostring(maxOpen), text_color=color.black, text_size=size.small)
        bool winOpen = (inAsia or inNY) and not inDead
        string openTxt = ""
        if array.size(openT) > 0
            for t in openT
                openTxt += "M" + str.tostring(t.sid + 1) + "T" + str.tostring(t.num) + (t.dir == 1 ? " L @ " : " S @ ") + str.tostring(t.entry, format.mintick) + "  "
        array<string> keys = array.from("NOW", "WINDOW", "DAILY", "1H TREND", "15m stair", "MMPD 27", "OPEN")
        array<string> vals = array.from(str.format_time(time, "EEE HH:mm", tz) + " NY", winOpen ? "OPEN · " + (inNY ? "NY AM" : "Asie") : "CLOSED · opens " + (hour(time, tz) < 9 or (hour(time, tz) == 9 and minute(time, tz) < 30) ? "09:30" : "18:00"), dDir == 1 ? "▲ BULL · last session" : dDir == -1 ? "▼ BEAR · last session" : "neutre", h1Dir == 1 ? "▲ BULL · stair" : h1Dir == -1 ? "▼ BEAR · stair" : "neutre", (sDir == 1 ? "▲ T" : sDir == -1 ? "▼ T" : "T") + str.tostring(sT) + (math.abs(sT) >= 2 and not na(sP) ? " · M1 fires " + (sDir == 1 ? "> " : "< ") + str.tostring(sP, format.mintick) : ""), str.tostring(mC, "#") + " · " + (xpOk ? "XP · longs OK" : xdOk ? "XD · shorts OK" : "MID · longs & shorts wait"), openTxt == "" ? "flat" : openTxt)
        for r = 0 to 6
            table.cell(desk, 0, r + 1, array.get(keys, r), text_color=color.black, text_size=size.small, text_halign=text.align_left)
            table.cell(desk, 1, r + 1, array.get(vals, r), text_color=color.black, text_size=size.small, text_halign=text.align_left)
        array<string> hdr = array.from("TESTED EDGES", "NOW", "HTF·CTF·ETF", "N", "WR", "AVG RR anc→réc", "VERDICT")
        for c = 0 to 6
            table.cell(desk, c, 8, array.get(hdr, c), text_color=color.black, text_size=size.small, bgcolor=color.new(color.gray, 85))
        for sid = 0 to 5
            [n, wr, aOld, aNew, tsc, dd] = f_stats(sid)
            string v = f_verdict(n, aOld, aNew, tsc)
            int row = 9 + sid
            table.cell(desk, 0, row, sid == 5 ? "ALL 5" : array.get(sName, sid), text_color=color.black, text_size=size.small, text_halign=text.align_left)
            table.cell(desk, 1, row, sid == 5 ? str.tostring(array.size(openT)) + " open" : f_now(sid), text_color=color.black, text_size=size.small)
            table.cell(desk, 2, row, sid == 5 ? "worst run " + str.tostring(dd, "#.0") + "R" : array.get(sHTF, sid), text_color=color.black, text_size=size.small)
            table.cell(desk, 3, row, str.tostring(n), text_color=color.black, text_size=size.small)
            table.cell(desk, 4, row, na(wr) ? "—" : str.tostring(wr, "#") + " %", text_color=color.black, text_size=size.small)
            table.cell(desk, 5, row, na(aOld) ? "—" : str.tostring(aOld, "+0.00;-0.00") + " → " + str.tostring(aNew, "+0.00;-0.00"), text_color=color.black, text_size=size.small)
            table.cell(desk, 6, row, v + (na(tsc) ? "" : " · t " + str.tostring(tsc, "0.0")), text_color=colTxt(v), text_size=size.small)
        table.cell(desk, 0, 15, "WR = trades gagnants · avg RR après coûts (" + str.tostring(costPts) + " pt) · TRADE = ≥30 trades, positif ancien ET récent, t ≥ 2,5", text_color=color.black, text_size=size.tiny)
    if showProp
        table.clear(prop, 0, 0, 4, 8)
        table.cell(prop, 0, 0, "PROP HELPER · objectif " + str.tostring(propTarget, "#") + " $ · DD suiveur " + str.tostring(propDD, "#") + " $", text_color=color.black, text_size=size.small)
        array<string> ph = array.from("SETUP", "PASS @ " + str.tostring(qty), "JOURS", "MEILLEURE TAILLE", "PASS @ MEILLEURE")
        for c = 0 to 4
            table.cell(prop, c, 1, array.get(ph, c), text_color=color.black, text_size=size.small, bgcolor=color.new(color.gray, 85))
        array<int> sizes = array.from(1, 2, 3, 4, 6, 8, 10)
        for sid = 0 to 5
            [pr, ps, fl, md] = f_prop(sid, qty)
            float bestPr = -1.0
            int bestSz = 0
            for s in sizes
                [p2, a2, b2, m2] = f_prop(sid, s)
                if not na(p2) and p2 > bestPr
                    bestPr := p2
                    bestSz := s
            int row = 2 + sid
            table.cell(prop, 0, row, sid == 5 ? "ALL 5" : "M" + str.tostring(sid + 1), text_color=color.black, text_size=size.small)
            table.cell(prop, 1, row, na(pr) ? "aucune décidée" : str.tostring(pr, "#") + " % (" + str.tostring(ps) + "✓ " + str.tostring(fl) + "✗)", text_color=na(pr) ? color.black : pr >= 50 ? color.green : color.red, text_size=size.small)
            table.cell(prop, 2, row, na(md) ? "—" : str.tostring(md, "#.0"), text_color=color.black, text_size=size.small)
            table.cell(prop, 3, row, bestSz == 0 ? "—" : str.tostring(bestSz) + " contrats", text_color=color.black, text_size=size.small)
            table.cell(prop, 4, row, bestSz == 0 ? "—" : str.tostring(bestPr, "#") + " %", text_color=color.black, text_size=size.small)
        table.cell(prop, 0, 8, "Rejoue tes règles sur les " + str.tostring(propN) + " derniers trades · seuil bloqué à +100 $", text_color=color.black, text_size=size.tiny)
'''

SCRIPTS = [
    ("Edge 5 Desk", "edge5_desk.pine", "indicateur (graphique + tableaux)", EDGE_DESK,
     "Le poste de pilotage : 5 setups simulés à la clôture (M1 Z T3+, M2 G GMC, M3 B GMC AFs, M4 C contraction limite, M5 M BC+), "
     "lignes de trades M#T# (entrée, SL, ½ TP, TP) et résultat en $ et points, ½ sortie puis stop à l'entrée, gate MMPD 27, "
     "journalière d'hier, tendance 1H, sessions Asie + NY AM, 2 positions max. Tableau EDGE DESK (NOW, WINDOW, DAILY, 1H, escalier, "
     "MMPD, positions, edges testés avec WR / avg RR ancien → récent / verdict) et PROP HELPER (pass % à ta taille, jours, meilleure taille). "
     "Alertes : « Any alert() function call » donne entrée / SL / ½ / TP de chaque trade. Mêmes règles que la page Edge Desk."),
    ("ICT MNQ Suite", "ict_mnq_suite.pine", "indicateur (graphique)", ICT_SUITE,
     "Structure BOS/MSS validée à la clôture, orderblocks (statut mitigé), breakers (OB cassés puis invalidés), FVG, "
     "sweeps BSL/SSL, PDH/PDL, Monday High/Low, Midnight Open, Weekly Open, range de travail avec EQ et OTE 0,705, kill zones NY, alertes."),
    ("MMM Order-Flow Map", "mmm_order_flow_map.pine", "indicateur (graphique)", MMM_MAP,
     "Boussole des bougies (BC+, BC−, AFs+, AFs−, CI), lignes GMC open supprimées à la clôture au-delà, escalier de tendance "
     "(CDL/CDS = T1, LD/SD = continuations, ★ à partir de T3, niveau protégé = stop), boîtes de session 18h/02h/09h30 avec "
     "balance control 1/3–2/3 (ligne épaisse = camp en contrôle) et vPOC approximatif, zones de pullback P–MP / BAL–MD."),
    ("MMPD", "mmpd_oscillator.pine", "indicateur (panneau séparé)", MMPD,
     "Position du prix dans son range récent (27 lente, 9 rapide), zones XP ≥ 80 (longs autorisés) et XD ≤ 20 (shorts autorisés) : "
     "à utiliser comme gate de momentum, jamais pour jouer le retournement."),
    ("Tempête parfaite (alignement MTF)", "alignement_mtf.pine", "indicateur (tableau)", ALIGN,
     "Tableau du type de la dernière bougie clôturée en Daily, 4H, 1H et 15m, et nombre d'unités de temps alignées."),
    ("ICT × MMM Edge Lab", "edge_lab_strategy.pine", "stratégie (Strategy Tester)", STRATEGY,
     "Stratégie de backtest : setups Z (T3+), G (GMC long), B (GMC AFs contre), M (BC+ long) et ICT (sweep puis MSS), stop ATR ou fixe, ½ sortie à +0,5 R "
     "puis stop à l'entrée, runner, sortie au temps, filtres sessions Asie + NY AM / MMPD / bougie journalière, coûts (0,52 $ + 1 tick). "
     "Tableau de stats : win rate, avg RR, PF, t-score, DD en R, pertes de suite, ancien → récent, verdict et risque max conseillé pour un compte prop."),
]
