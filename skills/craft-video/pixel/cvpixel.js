// cvpixel.js: helpers for pixel-art scenes of the html render provider (served at /__cv/pixel/cvpixel.js by the renderer).
//   import { screen, tick, loadSheet, frameAt, drawFrame, shake, ditherV, paintIndexed, palette } from "/__cv/pixel/cvpixel.js";
// Rules this file keeps for you (reference/pixel-art.md has the reasons, all of them measured):
//   * the picture is drawn at a LOGICAL size (frame size / scale) and shown at an integer scale with nearest neighbour, so every pixel is an exact scale x scale block;
//   * a scale must divide the frame exactly, and should be even (2, 4, 6, 8): 4:2:0 chroma covers 2 x 2 pixels, so an odd scale smears colour into the next pixel;
//   * positions are whole logical pixels (round them), time is held on whole animation frames (tick), nothing is blended, rotated or scaled by a fraction;
//   * every function is a pure function of its arguments, so seek(t) stays a pure function of t.

// The canvas: spec is window.__CV_SPEC. Returns drawing helpers in logical pixels. With spec.alpha the background stays transparent (an overlay).
export function screen(spec, scale = spec.look?.pixel?.scale || 6, parent = document.body) {
  const w = spec.width / scale, h = spec.height / scale;
  if (!Number.isInteger(w) || !Number.isInteger(h) || scale < 1) throw new Error(`cvpixel: ${spec.width}x${spec.height} is not a whole number of ${scale} x ${scale} blocks; pick a scale that divides both (1920x1080: 2, 4, 6, 8, 10, 12)`);
  if (scale % 2) console.warn(`cvpixel: scale ${scale} is odd: 4:2:0 chroma smears across pixels (reference/pixel-art.md); use an even scale or a yuv444p encode`);
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  Object.assign(c.style, { position: "fixed", left: "0", top: "0", width: spec.width + "px", height: spec.height + "px", imageRendering: "pixelated" });
  parent.appendChild(c);
  const g = c.getContext("2d", { willReadFrequently: true }); g.imageSmoothingEnabled = false;
  const off = document.createElement("canvas"); off.width = w; off.height = h; const og = off.getContext("2d", { willReadFrequently: true });
  const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return {
    g, w, h, scale, canvas: c,
    clear(color) { g.clearRect(0, 0, w, h); if (color && !spec.alpha) { g.fillStyle = color; g.fillRect(0, 0, w, h); } },
    rect(x, y, rw, rh, color) { g.fillStyle = color; g.fillRect(Math.round(x), Math.round(y), rw, rh); },
    px(x, y, color) { g.fillStyle = color; g.fillRect(Math.round(x), Math.round(y), 1, 1); },
    // Crisp text from any font: draw it, then keep only the pixels that are at least half covered (thr, 0 to 255). Bold, 8 px or more, reads well; a pixel font
    // (Press Start 2P, Silkscreen) at its native size, or a multiple of it, is crisper still. align: "left", "center" or "right" around x.
    text(str, x, y, color, font = 'bold 8px "DejaVu Sans Mono", monospace', { thr = 128, align = "left" } = {}) {
      og.clearRect(0, 0, w, h); og.font = font; og.textBaseline = "top"; og.fillStyle = "#fff";
      const tw = Math.ceil(og.measureText(str).width), x0 = Math.round(align === "center" ? x - tw / 2 : align === "right" ? x - tw : x);
      og.fillText(str, x0, Math.round(y));
      const d = og.getImageData(0, 0, w, h), [r, gr, b] = rgb(color);
      for (let i = 0; i < d.data.length; i += 4) { const on = d.data[i + 3] >= thr; d.data[i] = r; d.data[i + 1] = gr; d.data[i + 2] = b; d.data[i + 3] = on ? 255 : 0; }
      og.putImageData(d, 0, 0); g.drawImage(off, 0, 0); return tw;
    },
  };
}

// Time held on whole animation frames: a picture that changes 12 times a second ("on twos" at 24 fps, "on threes" at 36) is tick(t, 12).
export const tick = (t, fps) => Math.floor(t * fps + 1e-9) / fps;

// A palette from palettes.json (same folder): ids such as "pico8"; returns the colours as #rrggbb strings.
export async function palette(id) {
  const all = await (await fetch(new URL("palettes.json", import.meta.url))).json();
  if (!all[id]) throw new Error(`cvpixel: no palette '${id}' (known: ${Object.keys(all).join(", ")})`);
  return all[id].colors.map((c) => "#" + c.replace("#", ""));
}

// Sprite sheets from Aseprite (File > Export Sprite Sheet, or `aseprite -b in.aseprite --sheet s.png --data s.json --format json-array --list-tags`): json-array and
// json-hash are both read. A frame is {frame:{x,y,w,h}, duration (ms), spriteSourceSize, sourceSize}; a tag is {name, from, to, direction}.
export const parseSheet = (j) => ({
  frames: Array.isArray(j.frames) ? j.frames : Object.entries(j.frames).map(([filename, f]) => ({ filename, ...f })),      // json-hash is keyed by file name, in frame order
  tags: Object.fromEntries((j.meta.frameTags || []).map((t) => [t.name, t])), meta: j.meta,
});
export async function loadSheet(jsonUrl) {
  const url = new URL(jsonUrl, location.href), j = await (await fetch(url)).json();
  const img = new Image(); img.src = new URL(j.meta.image, url).href; await img.decode();
  return { img, ...parseSheet(j) };
}

// Which frame of a tag is showing at time t seconds (looping; once:true, or a tag with "repeat", holds the last). The order follows the tag's direction as Aseprite plays it:
// forward 0 1 2 3, reverse 3 2 1 0, pingpong 0 1 2 3 2 1 (the ends are not repeated), pingpong_reverse 3 2 1 0 1 2. Frame durations are honoured.
export function frameAt(sheet, tag, t, { once = false } = {}) {
  const tg = tag ? sheet.tags[tag] : { from: 0, to: sheet.frames.length - 1, direction: "forward" };
  if (!tg) throw new Error(`cvpixel: no tag '${tag}' (known: ${Object.keys(sheet.tags).join(", ")})`);
  const up = []; for (let i = tg.from; i <= tg.to; i++) up.push(i);
  const down = [...up].reverse(), mid = (a) => a.slice(1, -1);
  const seq = { forward: up, reverse: down, pingpong: [...up, ...mid(down)], pingpong_reverse: [...down, ...mid(up)] }[tg.direction || "forward"] || up;
  const total = seq.reduce((s, i) => s + sheet.frames[i].duration, 0), reps = Number(tg.repeat) || 0; let ms = Math.max(0, t) * 1000;       // a tag's "repeat" (a quoted number) plays it that many times, then holds
  ms = once || reps ? Math.min(ms, (once ? 1 : reps) * total - 1e-6) % total : ms % total;
  for (const i of seq) { if (ms < sheet.frames[i].duration) return i; ms -= sheet.frames[i].duration; }
  return seq[seq.length - 1];
}

// Draw sheet frame i with its top-left at whole logical pixel (x, y); flip mirrors it left to right inside its own source size (a sprite that walks left).
export function drawFrame(g, sheet, i, x, y, { flip = false } = {}) {
  const f = sheet.frames[i], r = f.frame, s = f.spriteSourceSize || { x: 0, y: 0, w: r.w, h: r.h }, sw = (f.sourceSize || { w: r.w }).w;
  const dx = Math.round(x) + (flip ? sw - s.x - s.w : s.x), dy = Math.round(y) + s.y;
  if (!flip) { g.drawImage(sheet.img, r.x, r.y, r.w, r.h, dx, dy, r.w, r.h); return; }
  g.save(); g.translate(dx + r.w, dy); g.scale(-1, 1); g.drawImage(sheet.img, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h); g.restore();
}

// Hit-stop: the world's time while the action freezes for `dur` seconds at `at` (fighting games hold 9 to 14 frames at 60 fps, so 0.15 to 0.25 s): hitstop(t, 5, 0.2) is t until 5, 5 for 0.2 s, then t - 0.2.
export const hitstop = (t, at, dur) => (t < at ? t : t < at + dur ? at : t - dur);

// Screen shake as whole-pixel offsets that change n times a second, from a hash of the step, so it is the same every time it is asked: [dx, dy] in -amp..amp.
export function shake(t, amp = 2, fps = 24, seed = 1) {
  const n = Math.floor(t * fps + 1e-9), hash = (k) => { let v = Math.imul(k ^ (seed * 0x9e3779b1), 0x85ebca6b); v ^= v >>> 13; v = Math.imul(v, 0xc2b2ae35); return (v ^ (v >>> 16)) >>> 0; };
  return [(hash(n) % (2 * amp + 1)) - amp, (hash(n + 7919) % (2 * amp + 1)) - amp];
}

// A vertical gradient through a list of colours with 4 x 4 ordered (Bayer) dithering between neighbours: the classic pixel-art sky. Ordered dithering is
// the only kind that does not shimmer from frame to frame (measured: error diffusion changes about a third of the pixels each frame, Bayer none).
const BAYER4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
export function ditherV(g, x, y, w, h, colors) {
  const d = g.createImageData(w, h), rgb = colors.map((c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16))), n = colors.length - 1;
  for (let j = 0; j < h; j++) {
    const p = h > 1 ? (j / (h - 1)) * n : 0, k = Math.min(n - 1, Math.floor(p)), frac = p - k;
    for (let i = 0; i < w; i++) {
      const c = rgb[frac > (BAYER4[(j & 3) * 4 + (i & 3)] + 0.5) / 16 ? k + 1 : k], o = (j * w + i) * 4;
      d.data[o] = c[0]; d.data[o + 1] = c[1]; d.data[o + 2] = c[2]; d.data[o + 3] = 255;
    }
  }
  g.putImageData(d, Math.round(x), Math.round(y));
}

// The pixel-art fade: k from 0 to 1 turns the picture into `color` pixel by pixel in 4 x 4 Bayer order, with nothing in between (no blended colours).
export function ditherFade(g, w, h, k, color) {
  if (k <= 0) return;
  const d = g.getImageData(0, 0, w, h), c = [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16));
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) if ((BAYER4[(j & 3) * 4 + (i & 3)] + 0.5) / 16 <= k) { const o = (j * w + i) * 4; d.data[o] = c[0]; d.data[o + 1] = c[1]; d.data[o + 2] = c[2]; d.data[o + 3] = 255; }
  g.putImageData(d, 0, 0);
}

// Indexed art with palette cycling (Mark Ferrari's trick for water, fire and sky): idx is a Uint8Array of palette indices (w x h, 255 = transparent), cycles lists
// {from, to, rate}: the colours from..to rotate by one every 1/rate seconds, which animates the picture without changing a pixel of it.
export function paintIndexed(g, idx, w, h, colors, cycles, t, x = 0, y = 0) {
  const map = colors.map((_, i) => i);
  for (const { from, to, rate } of cycles || []) { const n = to - from + 1, s = Math.floor(t * rate + 1e-9) % n; for (let i = 0; i < n; i++) map[from + i] = from + ((i + s) % n); }
  const rgb = colors.map((c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16))), d = g.createImageData(w, h);
  for (let i = 0; i < idx.length; i++) {
    if (idx[i] === 255) continue; const c = rgb[map[idx[i]]], o = i * 4;
    d.data[o] = c[0]; d.data[o + 1] = c[1]; d.data[o + 2] = c[2]; d.data[o + 3] = 255;
  }
  const tmp = document.createElement("canvas"); tmp.width = w; tmp.height = h; tmp.getContext("2d").putImageData(d, 0, 0); g.drawImage(tmp, Math.round(x), Math.round(y));
}
