// ec_lib.jsx: scene helpers for EffectCraft's After Effects-style scripting. build.sh concatenates
//   brand file + this file + your scenes file, so the brand globals (INK, ACCENT, DISP, MONO, M ...) exist here.
// API (all times in seconds, all coordinates in px, text is baseline-left anchored):
//   begin({name,w,h,dur,fps})  background()  scanbar(a,b)  footer(text,a,b)  finish()
//   txt(str,{x,y,size,font,color,a,b,[dx,dy,dur,out,tracking,leading,just,expr,name]})  -> layer
//   rect(x,y,w,h,{fill,stroke,sw,a,b,[grow,linear,dx,dy,dur,name]})  -> layer (left-top anchored; grow = seconds to grow from the left)
//   kicker(label,a,b)  panel(x,y,w,h,label,a,b)  chip(label,x,w,at,b)  underscore(textLayer,size,a,b)
function c(a) { return [a[0] / 255, a[1] / 255, a[2] / 255]; }
function c4(a) { return [a[0] / 255, a[1] / 255, a[2] / 255, 1]; }
var comp, W, H, DUR;
function begin(o) {
  W = o.w || 1920; H = o.h || 1080; DUR = o.dur || 30;
  comp = app.project.items.addComp(o.name || "Main", W, H, 1, DUR, o.fps || 30);
}
// ---------- helpers ----------
function tr(l, n) { return l.property("ADBE Transform Group").property(n); }
function easeOut(f) { return 1 - Math.pow(1 - f, 4); }
function animIn(l, at, dx, dy, dur) {
  var pos = tr(l, "ADBE Position"), op = tr(l, "ADBE Opacity"), p = pos.value, N = 8;
  for (var i = 0; i <= N; i++) {
    var f = i / N, e = easeOut(f);
    pos.setValueAtTime(at + dur * f, [p[0] + dx * (1 - e), p[1] + dy * (1 - e)]);
  }
  op.setValueAtTime(at, 0); op.setValueAtTime(at + Math.min(dur, 0.22), 100);
}
function animOut(l, b, dur) {
  var op = tr(l, "ADBE Opacity");
  op.setValueAtTime(b - dur, 100); op.setValueAtTime(b, 0);
}
function setIO(l, a, b) { l.inPoint = a; l.outPoint = b; }
function solid(col, name) { return comp.layers.addSolid(c(col), name, W, H, 1); }

function txt(str, o) {
  var l = comp.layers.addText(str);
  var p = l.property("ADBE Text Properties").property("ADBE Text Document");
  var d = p.value;
  d.fontSize = o.size; d.font = o.font; d.fillColor = c(o.color); d.applyFill = true;
  d.justification = o.just || ParagraphJustification.LEFT_JUSTIFY;
  if (o.tracking !== undefined) d.tracking = o.tracking;
  if (o.leading) { d.autoLeading = false; d.leading = o.leading; }
  p.setValue(d);
  tr(l, "ADBE Position").setValue([o.x, o.y]);
  l.name = o.name || str.substring(0, 24);
  if (o.expr) p.expression = o.expr;
  var a = o.a, b = o.b, dur = o.dur || 0.45;
  setIO(l, a, b);
  animIn(l, a, o.dx || 0, o.dy === undefined ? 40 : o.dy, dur);
  if (o.out !== 0) animOut(l, b, o.out === undefined ? 0.15 : o.out);
  return l;
}

// the brand's trailing underscore: sits on the baseline, right after the last glyph
function underscore(l, size, a, b, out0) {
  var r = l.sourceRectAtTime(0, false), p = tr(l, "ADBE Position").value;
  var w = size * 0.42, h = Math.round(size * 0.085);
  var x = p[0] + r.left + r.width + size * 0.07;
  var s = rect(x, p[1] - h - Math.round(size * 0.012), w, h, { fill: ACCENT, a: a, b: b, grow: 0.3, name: "underscore" });
  return s;
}
// rect with left-top corner at (x,y); fill and/or stroke
function rect(x, y, w, h, o) {
  var s = comp.layers.addShape();
  var g = s.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
  var r = g.property("ADBE Vectors Group").addProperty("ADBE Vector Shape - Rect");
  r.property("ADBE Vector Rect Size").setValue([w, h]);
  r.property("ADBE Vector Rect Position").setValue([w / 2, h / 2]);
  if (o.stroke) {
    var st = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Stroke");
    st.property("ADBE Vector Stroke Color").setValue(c4(o.stroke));
    st.property("ADBE Vector Stroke Width").setValue(o.sw || 2);
  }
  if (o.fill) {
    var f = g.property("ADBE Vectors Group").addProperty("ADBE Vector Graphic - Fill");
    f.property("ADBE Vector Fill Color").setValue(c4(o.fill));
  }
  s.name = o.name || "rect";
  tr(s, "ADBE Position").setValue([x, y]);
  setIO(s, o.a, o.b);
  if (o.grow) {                       // grows from the left edge (anchor sits at the rect's left-top corner)
    var sc = tr(s, "ADBE Scale"), N = 10;
    for (var i = 0; i <= N; i++) {
      var f2 = i / N, e = o.linear ? f2 : easeOut(f2);
      sc.setValueAtTime(o.a + o.grow * f2, [Math.max(0.01, 100 * e), 100]);
    }
    var op = tr(s, "ADBE Opacity"); op.setValueAtTime(o.b - 0.15, 100); op.setValueAtTime(o.b, 0);
  } else {
    animIn(s, o.a, o.dx || 0, o.dy === undefined ? 0 : o.dy, o.dur || 0.4);
    animOut(s, o.b, 0.15);
  }
  return s;
}
function kicker(label, a, b) {
  var w = label.length * 21.8 + 28;
  rect(M, 108, w, 46, { fill: BONE, a: a, b: b, dy: 14, name: "kicker bg" });
  txt(label, { x: M + 14, y: 141, size: 26, font: MONOM, color: INK, tracking: 240, a: a + 0.05, b: b, dy: 14, name: "kicker" });
}
function panel(x, y, w, h, label, a, b) {
  rect(x, y, w, h, { fill: PANEL, stroke: LINE2, sw: 2, a: a, b: b, dy: 30, name: "panel " + label });
  rect(x, y, w, 4, { fill: ACCENT, a: a, b: b, dy: 30, name: "panel edge " + label });
  txt(label, { x: x + 36, y: y + 58, size: 24, font: MONOM, color: DIM, tracking: 240, a: a + 0.1, b: b, dy: 20, name: "label " + label });
}

// the 40 px hairline grid over the ink ground (brand body background)
function background() {
  var bg = solid(INK, "BG ink");
  var gfx = bg.property("ADBE Effect Parade").addProperty("ADBE Grid");
  gfx.property("Size From").setValue(3);
  gfx.property("Width").setValue(40); gfx.property("Height").setValue(40);
  gfx.property("Border").setValue(1);
  gfx.property("Color").setValue(c4(GRID));
}
function scanbar(a, b) {   // 6 px accent bar that fills across the top for the whole video
  rect(0, 0, W, 6, { fill: ACCENT, a: a || 0, b: b || DUR, grow: (b || DUR) - (a || 0), linear: true, name: "scanbar" });
}
function footer(text, a, b) {
  txt(text, { x: M, y: H - 48, size: 18, font: MONOM, color: DIM, tracking: 200, a: a, b: b, dy: 0, name: "footer" });
}
function chip(label, x, w, at, b) {
  rect(x, 905, w, 56, { stroke: LINE3, sw: 2, fill: PANEL, a: at, b: b, dy: 16, name: "chip " + label });
  txt(label, { x: x + 22, y: 942, size: 26, font: MONOM, color: BONE, tracking: 160, a: at + 0.05, b: b, dy: 16, name: "chip text " + label });
}
// OUT_PROJECT is prepended by build.sh
function finish() {
  app.project.save(new File(OUT_PROJECT));
  writeLn("layers: " + comp.numLayers + " | saved " + OUT_PROJECT);
}
