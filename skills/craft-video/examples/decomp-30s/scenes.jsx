// Worked example: "AI decompilation boom", 30 s, 1920x1080 @ 30. Cue times come from timeline.json (sentence starts in the
// tightened narration). Brand: brand-ipedrax.jsx. Build:  build.sh scenes.jsx out.ecproj
begin({ name: "Main", w: 1920, h: 1080, dur: 30, fps: 30 });
background();
scanbar(0, 30);
footer("AI + GAME DECOMPILATION  /  2026", 0.6, 26.3);

// ---------- S1 hook 0 - 2.1 ----------
var S1b = 2.1;
txt("AI IS TAKING", { x: M, y: 520, size: 330, font: DISP, color: BONE, a: 0.0, b: S1b, dy: 70, dur: 0.5, name: "hook 1" });
var h2 = txt("GAMES APART", { x: M, y: 790, size: 330, font: DISP, color: BONE, a: 0.16, b: S1b, dy: 70, dur: 0.5, name: "hook 2" });
underscore(h2, 330, 0.62, S1b);
rect(M, 888, 1680, 4, { fill: LINE3, a: 0.7, b: S1b, grow: 0.7, name: "hook rule" });

// ---------- S2 reveal 2.1 - 7.05 ----------
var A2 = 2.15, B2 = 7.05;
kicker("01 / DECOMPILATION", A2, B2);
var s2t = txt("BACK TO SOURCE", { x: M, y: 330, size: 190, font: DISP, color: BONE, a: A2 + 0.1, b: B2, name: "s2 title" });
underscore(s2t, 190, A2 + 0.45, B2);
panel(M, 420, 800, 500, "COMPILED  /  MIPS  (EXAMPLE)", 2.45, B2);
txt("27BDFFE8\nAFBF0014\n0C0123A4\n00000000\n8FBF0014\n03E00008\n27BD0018",
    { x: M + 36, y: 540, size: 32, font: MONOM, color: DATA, leading: 50, a: 2.8, b: B2, dy: 24, name: "hex" });
txt("addiu sp,sp,-0x18\nsw    ra,0x14(sp)\njal   func_80048E90\nnop\nlw    ra,0x14(sp)\njr    ra\naddiu sp,sp,0x18",
    { x: M + 36 + 8 * 19.2 + 44, y: 540, size: 32, font: MONO, color: TEXT, leading: 50, a: 2.95, b: B2, dy: 24, name: "asm" });
// link between the panels
rect(M + 800, 668, 84, 4, { fill: ACCENT, a: 3.9, b: B2, grow: 0.35, name: "link" });
panel(M + 880, 420, 800, 500, "DECOMPILED  /  C  (EXAMPLE)", 4.05, B2);
txt("void func_80048E88(void) {\n    func_80048E90();\n}",
    { x: M + 880 + 36, y: 600, size: 38, font: MONOM, color: BONE, leading: 62, a: 4.4, b: B2, dy: 24, name: "c code" });
rect(M + 880 + 36, 770, 560, 56, { fill: DATA, a: 5.2, b: B2, dy: 16, name: "badge bg" });
txt("COMPILES TO IDENTICAL BYTES", { x: M + 880 + 52, y: 807, size: 26, font: MONOB, color: INK, tracking: 120, a: 5.3, b: B2, dy: 16, name: "badge" });

// ---------- S3 the clock 7.05 - 14.7 ----------
var A3 = 7.1, B3 = 14.7;
kicker("02 / THE CLOCK", A3, B3);
txt("0", { x: M, y: 640, size: 560, font: DISP, color: ACCENT, a: 7.15, b: B3, dy: 60, name: "84",
           expr: "Math.round(linear(time, 7.3, 8.6, 0, 84)).toString()" });
txt("DAYS", { x: M + 6, y: 702, size: 34, font: MONOB, color: BONE, tracking: 240, a: 7.5, b: B3, dy: 20, name: "days84 label" });
txt("SNOWBOARD KIDS (N64)", { x: M + 6, y: 748, size: 26, font: MONO, color: MUTED, tracking: 120, a: 7.6, b: B3, dy: 20, name: "sk1" });
txt("0", { x: 1000, y: 640, size: 560, font: DISP, color: BONE, a: 9.9, b: B3, dy: 60, name: "596",
           expr: "Math.round(linear(time, 10.1, 11.5, 0, 596)).toString()" });
txt("DAYS", { x: 1006, y: 702, size: 34, font: MONOB, color: BONE, tracking: 240, a: 10.4, b: B3, dy: 20, name: "days596 label" });
txt("ITS SEQUEL, SNOWBOARD KIDS 2", { x: 1006, y: 748, size: 26, font: MONO, color: MUTED, tracking: 120, a: 10.5, b: B3, dy: 20, name: "sk2" });
// bars drawn to scale: 84 vs 596
rect(M, 800, 1680 * 84 / 596, 22, { fill: ACCENT, a: 7.4, b: B3, grow: 0.8, name: "bar 84" });
rect(M, 840, 1680, 22, { fill: DIM, a: 10.1, b: B3, grow: 1.4, name: "bar 596" });
// who and what helped
chip("AI AGENTS", M, 290, 12.15, B3);
chip("COMMUNITY EXPERTS", M + 314, 470, 13.3, B3);
chip("TOOLING", M + 314 + 494, 220, 13.95, B3);
txt("SOURCE: CHRIS LEWIS BLOG, 26 AUG 2026", { x: M, y: 1000, size: 18, font: MONO, color: DIM, tracking: 160, a: 8.2, b: B3, dy: 0, name: "src3" });

// ---------- S4 melee 14.7 - 21.2 ----------
var A4 = 14.75, B4 = 21.2;
kicker("03 / THE LAST STRETCH", A4, B4);
txt("SUPER SMASH BROS. MELEE", { x: M, y: 300, size: 120, font: DISP, color: BONE, a: A4 + 0.1, b: B4, name: "melee title" });
txt("0%", { x: M, y: 800, size: 600, font: DISP, color: ACCENT, a: 15.1, b: B4, dy: 60, name: "100",
           expr: "Math.round(linear(time, 15.3, 17.5, 0, 100)).toString() + '%'" });
rect(M, 850, 1680, 8, { fill: LINE2, a: 15.1, b: B4, dy: 0, name: "track" });
rect(M, 850, 1680, 8, { fill: ACCENT, a: 15.3, b: B4, grow: 2.2, linear: true, name: "fill" });
txt("STARTED 2020   /   100% DECOMPILED SEPT 2026", { x: M, y: 925, size: 28, font: MONOM, color: MUTED, tracking: 120, a: 17.7, b: B4, dy: 20, name: "melee stats" });
rect(M, 950, 6, 44, { fill: ACCENT, a: 18.8, b: B4, dy: 0, name: "ai edge" });
txt("AI MODELS HELPED CLOSE THE LAST STRETCH  (REPORTED)", { x: M + 24, y: 984, size: 28, font: MONOM, color: BONE, tracking: 80, a: 18.8, b: B4, dy: 20, name: "ai line" });
txt("SOURCE: DECOMP.DEV  /  ANDROID AUTHORITY", { x: 1100, y: 1032, size: 18, font: MONO, color: DIM, tracking: 160, a: 15.4, b: B4, dy: 0, name: "src4" });

// ---------- S5 split 21.2 - 26.35 ----------
var A5 = 21.25, B5 = 26.35;
kicker("04 / THE SPLIT", A5, B5);
panel(M, 300, 780, 580, "AI-ASSISTED RECOMPS", 21.4, B5);
txt("MARIO KART WII", { x: M + 36, y: 520, size: 108, font: DISP, color: BONE, a: 21.75, b: B5, name: "mkwii" });
txt("BANJO-TOOIE", { x: M + 36, y: 650, size: 108, font: DISP, color: BONE, a: 22.05, b: B5, name: "bt" });
txt("AI-ASSISTED PC PORTS, PER PRESS REPORTS", { x: M + 36, y: 760, size: 24, font: MONO, color: MUTED, tracking: 120, a: 22.3, b: B5, dy: 16, name: "ports note" });
rect(960, 300, 3, 580, { fill: ACCENT, a: 21.5, b: B5, dy: 0, name: "split line" });
panel(1020, 300, 780, 580, "A PORT DEVELOPER SAYS", 22.7, B5);
txt("A RACE TO", { x: 1056, y: 560, size: 140, font: DISP, color: BONE, a: 24.2, b: B5, name: "q1" });
txt("THE BOTTOM", { x: 1056, y: 700, size: 140, font: DISP, color: ACCENT, a: 24.85, b: B5, name: "q2" });
txt("BANJO-KAZOOIE PC PORT DEVELOPER, VIA VGC", { x: 1056, y: 790, size: 22, font: MONO, color: MUTED, tracking: 100, a: 25.3, b: B5, dy: 12, name: "q src" });

// ---------- S6 punchline 26.35 - 30 ----------
var A6 = 26.4;
txt("THE TOOLS", { x: M, y: 470, size: 330, font: DISP, color: BONE, a: A6, b: DUR, dy: 70, dur: 0.5, out: 0, name: "p1" });
var p2 = txt("ARE HERE", { x: M, y: 740, size: 330, font: DISP, color: BONE, a: A6 + 0.14, b: DUR, dy: 70, dur: 0.5, out: 0, name: "p2" });
underscore(p2, 330, A6 + 0.6, DUR);
txt("THE FIGHT IS OVER HOW TO USE THEM.", { x: M, y: 850, size: 44, font: MONOM, color: BONE, tracking: 60, a: 27.6, b: DUR, dy: 24, out: 0, name: "p3" });
txt("SOURCES: CHRIS LEWIS BLOG (26 AUG 2026)  /  DECOMP.DEV  /  VGC  /  TIME EXTENSION  /  ANDROID AUTHORITY",
    { x: M, y: 985, size: 18, font: MONO, color: DIM, tracking: 100, a: 28.0, b: DUR, dy: 0, out: 0, name: "sources" });
txt("MADE WITH EFFECTCRAFT + FILMCRAFT + VOICESTUDIO  /  TEST RENDER", { x: M, y: 1020, size: 18, font: MONO, color: DIM, tracking: 100, a: 28.2, b: DUR, dy: 0, out: 0, name: "madewith" });

finish();
