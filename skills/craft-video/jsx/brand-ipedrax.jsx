// Brand: Pedro's signature system (ipedrax.com, 2026 editorial rebuild): neutral near-black, ONE hot-pink accent,
// cyan reserved for data. Display = Big Shoulders Display, everything else = IBM Plex Mono. Both are OFL.
// To use another brand, copy this file, change the values, and pass it as: build.sh --brand mybrand.jsx scenes.jsx
var INK = [10, 10, 11], PANEL = [16, 16, 18], BONE = [242, 242, 240], TEXT = [214, 214, 216],
    MUTED = [168, 168, 174], DIM = [143, 143, 151], LINE2 = [46, 46, 51], LINE3 = [60, 60, 66],
    ACCENT = [255, 46, 136], DATA = [58, 215, 255], GRID = [20, 20, 23];
// PostScript names, which is how EffectCraft resolves fonts (see reference/effectcraft-scripting.md)
var DISP = "BigShouldersDisplay-Black", DISPB = "BigShouldersDisplay-Bold",
    MONO = "IBMPlexMono-Regular", MONOM = "IBMPlexMono-Medium", MONOB = "IBMPlexMono-Bold";
var M = 120;   // outer margin in px at 1920 wide
