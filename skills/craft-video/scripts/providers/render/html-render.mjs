// html-render.mjs: render an HTML scene to an H.264 mp4 (or stills, or a transparent overlay) with headless Chromium + ffmpeg.
// A scene page must define window.craftvideo.seek(t) (seconds): make the DOM / canvas a PURE FUNCTION OF t, return when ready.
// The spec and the narration cues are available as window.__CV_SPEC = {width,height,fps,duration,timeline,alpha}.
//   node html-render.mjs scene.html out.mp4 --width 1920 --height 1080 --fps 30 --duration 30 [--timeline timeline.json]
//   node html-render.mjs scene.html out.mp4 ... --stills "1.4 8.9" --sheet sheet.png
//   node html-render.mjs scene.html out.mov ... --alpha 1        (transparent background -> ProRes 4444 with alpha, for overlays)
//   node html-render.mjs scene.html out.mp4 ... --gpu auto       (WebGL on the GPU: off | auto | vulkan | egl; env CRAFTVIDEO_GPU.
//                                                                 WebGPU scenes: request the adapter with powerPreference "high-performance", fall back to
//                                                                 forceFallbackAdapter (software), and await device.queue.onSubmittedWorkDone() in seek())
//   node html-render.mjs scene.html out.mp4 ... --workers 4      (capture frames on 4 pages at once; frames are pure functions of t, so the video is identical; env CRAFTVIDEO_WORKERS, "auto")
//   node html-render.mjs scene.html out.mp4 ... --shutter 180 --subframes 8   (motion blur: 8 renders across a 180 degree shutter averaged per frame; 8x the capture time; not with --alpha)
//   node html-render.mjs scene.html out.mp4 ... --grain 8        (luma film grain: ffmpeg noise strength, luma std = strength / 3 of 255 levels (measured, and it survives x264 crf 14):
//                                                                 8 is subtle, 16 clearly visible; fixed seed, so a re-render is identical; not with --alpha)
//   node html-render.mjs scene.html out.json ... --lint 1        (no video: audit the layout at many times and write a report; exit 1 on an error. See lint below.)
//   node html-render.mjs scene.html out.mp4 ... --look dark-keynote   (a look from looks/*.json, or a path: its colour and type roles reach the scene as window.__CV_SPEC.look
//                                                                 and as CSS variables --cv-ground, --cv-ink, --cv-accent, --cv-display-font, --cv-display-size ... before the page runs)
//   node html-render.mjs --check
// Before encoding, a preflight visits five times forward and then backward and fails if any frame differs the second time (--preflight 0 skips it;
// --preflight-psnr 60 forgives renderer noise: a revisit within 60 dB of the first visit passes).
// The page is served from a private origin (http://cv.local) out of the scene's folder (--root DIR to widen it), so ES modules,
// import maps, fetch() and GLB/texture loading all work. If three.js is installed (scripts/get_three.sh) a bare `import "three"` and
// `import ... from "three/addons/..."` resolve to it automatically; a scene with its own import map keeps it.
//
// The shutter (sub-frame averaging, linear in time, in 16-bit with ffmpeg tmix) and grain follow the practice documented by Motionmaxxing
// (Tejashmakwana/motionmaxxing, Apache-2.0): a 180 degree shutter over 8 sub-frames and luma grain; this is our own implementation. The layout audit is our own
// code with the same idea as HyperFrames' `check` (heygen-com/hyperframes, Apache-2.0): audit text boxes at sampled times and only report what is held.
import { createRequire } from "node:module";
import { spawn, spawnSync, execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, readdirSync, existsSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { resolve, join, dirname, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir, cpus } from "node:os";

const require = createRequire(import.meta.url);
function loadPlaywright() {
  const bases = [process.env.PLAYWRIGHT_DIR, process.env.VOICESTUDIO_DIR && join(process.env.VOICESTUDIO_DIR, "node_modules"),
    "/mnt/ai/VoiceStudio/node_modules", process.cwd(), join(process.env.HOME || "", ".local/lib/node_modules")].filter(Boolean);
  for (const b of bases) { try { return require(require.resolve("playwright", { paths: [b] })); } catch {} }
  try { return require("playwright"); } catch {}
  return null;
}

// GPU modes. "off" is Chromium's default (software WebGL via SwiftShader: slow, but it runs anywhere). "vulkan" and "egl" are the two
// ways ANGLE reaches a real GPU on Linux; "auto" tries them in turn and keeps the first one that is not software.
const GPU_FLAGS = {
  off: [],
  vulkan: ["--use-angle=vulkan", "--enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan", "--ignore-gpu-blocklist", "--disable-vulkan-surface", "--enable-gpu-rasterization"],
  egl: ["--use-gl=angle", "--use-angle=gl-egl", "--ignore-gpu-blocklist"],
};
const rendererOf = (page) => page.evaluate(() => {
  const gl = document.createElement("canvas").getContext("webgl2");
  if (!gl) return "no WebGL2";
  const e = gl.getExtension("WEBGL_debug_renderer_info");
  return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : "unknown";
});
async function launchOnce(pw, gpu) {
  const exe = process.env.CRAFTVIDEO_CHROMIUM;
  // WebGPU is on in every mode (software through SwiftShader when there is no GPU path). The private origin is local and ours, so treat it as
  // secure: that is what exposes navigator.gpu and other secure-context APIs.
  const flags = ["--force-device-scale-factor=1", "--hide-scrollbars", "--font-render-hinting=none", "--enable-unsafe-webgpu", "--unsafely-treat-insecure-origin-as-secure=http://cv.local", ...GPU_FLAGS[gpu]];
  // a full system Chromium first: Playwright's bundled headless shell has no WebGPU and no proprietary codecs. The bundled one is the last resort.
  const tries = [exe && { executablePath: exe }, { executablePath: "/usr/bin/chromium" }, { executablePath: "/usr/bin/google-chrome-stable" }, {}].filter(Boolean);
  let last;
  for (const t of tries) {
    if (t.executablePath && !existsSync(t.executablePath)) continue;
    try { return await pw.chromium.launch({ ...t, args: flags }); } catch (e) { last = e; }
  }
  throw last || new Error("no Chromium found: install one for Playwright, or set CRAFTVIDEO_CHROMIUM");
}
async function launch(pw, mode) {
  const want = ({ 0: "off", 1: "auto", false: "off", true: "auto" })[mode] ?? mode ?? "off";
  if (!(want in GPU_FLAGS) && want !== "auto") throw new Error(`unknown --gpu '${want}' (off, auto, vulkan, egl)`);
  const order = want === "auto" ? ["vulkan", "egl"] : [want];
  for (const g of order) {
    let b; try { b = await launchOnce(pw, g); } catch { continue; }
    const r = await rendererOf(await b.newPage());
    if (want !== "auto" || !/swiftshader|llvmpipe|software|no WebGL/i.test(r)) return { browser: b, renderer: r, gpu: g };
    await b.close();
  }
  if (want === "auto") console.error("gpu: no hardware WebGL found, falling back to software");
  const b = await launchOnce(pw, "off"); return { browser: b, renderer: await rendererOf(await b.newPage()), gpu: "off" };
}

// ---- layout audit: runs INSIDE the page after seek(t). Returns the text boxes it sees and the faults among them ----
// rules: frame (text cut by the picture's edge), clipped (cut by an ancestor with overflow hidden), overlap (two different elements' text on top of each other),
// occluded (hidden behind an element with an opaque background), small (text under minFrac of the height), band (text in the bottom caption band). Opt-outs on any ancestor: data-cv-ignore (skip), data-cv-texture (small text
// is meant: sources, footers), data-cv-caption (belongs in the caption band), data-cv-layer (may overlap).
function auditPage({ W, H, band, minFrac }) {
  const boxes = [], issues = [];
  const alphaOf = (el) => { let a = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const s = getComputedStyle(e); if (s.display === "none" || s.visibility === "hidden") return 0; a *= parseFloat(s.opacity); } return a; };
  const desc = (el, text) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${el.classList.length ? "." + [...el.classList].slice(0, 2).join(".") : ""} "${text.slice(0, 28)}"`;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = walker.nextNode()); ) {
    const text = n.nodeValue.replace(/\s+/g, " ").trim(); if (!text) continue;
    const el = n.parentElement; if (!el || el.closest("script,style,noscript,canvas,[data-cv-ignore]")) continue;
    const alpha = alphaOf(el); if (alpha < 0.05) continue;
    const rg = document.createRange(); rg.selectNodeContents(n);
    const rs = [...rg.getClientRects()].filter((r) => r.width > 0.5 && r.height > 0.5); if (!rs.length) continue;
    let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity, it0 = Infinity, ib0 = -Infinity;
    for (const q of rs) { l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); b = Math.max(b, q.bottom);
      it0 = Math.min(it0, q.top + 0.18 * q.height); ib0 = Math.max(ib0, q.bottom - 0.18 * q.height); }   // the ink: a line box carries empty space above the capitals and below the baseline
    const cs = getComputedStyle(el); let sc = 1;                                    // the font size as drawn: computed size times every ancestor's scale
    for (let a = el; a && a.nodeType === 1; a = a.parentElement) { const tr = getComputedStyle(a).transform; if (tr && tr !== "none") { const m = new DOMMatrixReadOnly(tr); sc *= Math.hypot(m.a, m.b) || 1; } }
    const fs = parseFloat(cs.fontSize) * sc;
    // the window the text can be seen through: every ancestor that clips its overflow narrows it (cl*), then the picture itself (vl*)
    let cl = -Infinity, ct = -Infinity, cr = Infinity, cb = Infinity;
    for (let a = el; a && a.nodeType === 1 && a !== document.body && a !== document.documentElement; a = a.parentElement) {   // the page itself is the frame, not a container
      const s = getComputedStyle(a);
      if (/(hidden|clip|auto|scroll)/.test(s.overflowX + s.overflowY) && s.textOverflow !== "ellipsis") { const q = a.getBoundingClientRect(); cl = Math.max(cl, q.left); ct = Math.max(ct, q.top); cr = Math.min(cr, q.right); cb = Math.min(cb, q.bottom); }
    }
    const area = (r - l) * (b - t), cover = (x0, y0, x1, y1) => Math.max(0, Math.min(r, x1) - Math.max(l, x0)) * Math.max(0, Math.min(b, y1) - Math.max(t, y0));
    const byAncestor = cover(cl, ct, cr, cb), seenArea = cover(Math.max(cl, 0), Math.max(ct, 0), Math.min(cr, W), Math.min(cb, H));
    if (seenArea <= 0) continue;                                                   // not on screen at all (waiting to enter, or fully hidden)
    const d = desc(el, text), tex = !!el.closest("[data-cv-texture]"), cap = !!el.closest("[data-cv-caption]"), layer = !!el.closest("[data-cv-layer]");
    if (seenArea / area < 0.97) {
      const byContainer = byAncestor / area < 0.97;                                // the container clips it, or only the picture's edge does
      issues.push({ rule: byContainer ? "clipped" : "frame", key: (byContainer ? "clipped " : "frame ") + d, detail: `${byContainer ? "cut off by its container" : "cut off by the edge of the picture"}: ${d} (${Math.round(100 * seenArea / area)}% visible)` });
    }
    if (fs / H < minFrac && text.length >= 3 && !tex) issues.push({ rule: "small", key: "small " + d, detail: `text is ${(100 * fs / H).toFixed(2)}% of the height, under ${(100 * minFrac).toFixed(2)}%: ${d}` });
    if (band > 0 && !cap && b > H * (1 - band) && (b - Math.max(t, H * (1 - band))) / (b - t) > 0.25) issues.push({ rule: "band", key: "band " + d, detail: `text sits in the bottom ${Math.round(100 * band)}% reserved for captions: ${d}` });
    boxes.push({ d, el, l, t, r, b, it: it0, ib: ib0, area, alpha, layer, fs, color: cs.color, tex, text: text.slice(0, 40) });
  }
  // hidden: sample a 5 x 3 grid inside each text's ink; if something above it in the stack has an opaque background (and is not its own ancestor or descendant), it is hidden
  const opaqueBg = (e) => { let a = 1; for (let n = e; n && n.nodeType === 1; n = n.parentElement) a *= parseFloat(getComputedStyle(n).opacity);
    const m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/.exec(getComputedStyle(e).backgroundColor); return a >= 0.6 && !!m && (m[4] === undefined ? 1 : +m[4]) >= 0.6; };
  for (const B of boxes) {
    if (B.alpha < 0.3 || B.layer) continue;
    let pts = 0, hidden = 0, blocker = null;
    for (let gx = 0; gx < 5; gx++) for (let gy = 0; gy < 3; gy++) {
      const x = B.l + (B.r - B.l) * (gx + 0.5) / 5, y = B.it + (B.ib - B.it) * (gy + 0.5) / 3; if (x < 0 || y < 0 || x >= W || y >= H) continue;
      pts++; const stack = document.elementsFromPoint(x, y), own = stack.findIndex((e) => B.el === e || B.el.contains(e));
      const hit = stack.slice(0, own === -1 ? stack.length : own).find((e) => !e.contains(B.el) && !B.el.contains(e) && opaqueBg(e));
      if (hit) { hidden++; blocker = blocker || hit; }
    }
    if (pts >= 3 && hidden / pts >= 0.6) issues.push({ rule: "occluded", key: "occluded " + B.d, detail: `text is hidden behind ${desc(blocker, "").replace(/ ""$/, "")}: ${B.d}` });
  }
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const A = boxes[i], B = boxes[j];
    if (A.el === B.el || A.el.contains(B.el) || B.el.contains(A.el) || A.layer || B.layer || A.alpha < 0.3 || B.alpha < 0.3) continue;
    const w = Math.min(A.r, B.r) - Math.max(A.l, B.l), h = Math.min(A.ib, B.ib) - Math.max(A.it, B.it);      // overlap of the ink areas
    if (w > 0 && h > 0 && (w * h) / Math.min((A.r - A.l) * (A.ib - A.it), (B.r - B.l) * (B.ib - B.it)) > 0.2) { const k = [A.d, B.d].sort().join(" over "); issues.push({ rule: "overlap", key: "overlap " + k, detail: `text overlaps text: ${k}` }); }
  }
  return { boxes: boxes.map(({ el, ...rest }) => rest), issues };
}

// ---- looks: colour, type and motion roles as data (looks/*.json). A scene styles itself with var(--cv-ink, #fff) and keeps working without a look ----
function loadLook(name) {
  const dir = join(dirname(fileURLToPath(import.meta.url)), "../../../looks");
  const p = [name, join(dir, name.replace(/\.json$/, "") + ".json")].find((f) => existsSync(f) && statSync(f).isFile());
  if (!p) { console.error(`html: no look '${name}'. Looks in ${dir}: ${existsSync(dir) ? readdirSync(dir).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5)).join(", ") : "none"}`); process.exit(2); }
  return JSON.parse(readFileSync(p, "utf8"));
}
function lookCss(L) {
  const v = [];
  for (const [k, c] of Object.entries(L.color || {})) v.push(`--cv-${k}:${c}`);
  for (const [role, t] of Object.entries(L.type || {})) {
    v.push(`--cv-${role}-font:"${t.family}"${t.fallback ? ", " + t.fallback : ""}`, `--cv-${role}-weight:${t.weight}`, `--cv-${role}-size:${(t.size * 100).toFixed(3)}vh`);
    if (t.caps) v.push(`--cv-${role}-transform:uppercase`);
  }
  return `:root{${v.join(";")}}`;
}

const argv = process.argv.slice(2);
if (argv[0] === "--check") {
  const pw = loadPlaywright();
  if (!pw) { console.log("playwright not found (set PLAYWRIGHT_DIR to a node_modules that has it)"); process.exit(1); }
  try { const b = await launchOnce(pw, "off"); await b.close(); process.exit(0); } catch (e) { console.log("no usable Chromium: " + String(e.message).split("\n")[0]); process.exit(1); }
}
const [scene, out, ...rest] = argv;
const o = { width: 1920, height: 1080, fps: 30, duration: 30, gpu: process.env.CRAFTVIDEO_GPU || "off", alpha: "0" };
for (let i = 0; i < rest.length; i += 2) o[rest[i].replace(/^--/, "")] = rest[i + 1];
const W = +o.width, H = +o.height, FPS = +o.fps, DUR = +o.duration, N = Math.round(FPS * DUR), ALPHA = o.alpha === "1" || o.alpha === "true";
const SH = +o.shutter || 0, SUB = Math.max(2, Math.round(+o.subframes || 8)), GRAIN = +o.grain || 0, LINT = o.lint === "1" || o.lint === "true", PSNR = +o["preflight-psnr"] || 0;
const WORKERS = (() => { const w = o.workers ?? process.env.CRAFTVIDEO_WORKERS ?? "1"; const n = w === "auto" ? Math.min(4, Math.floor(cpus().length / 3)) : Math.round(+w); return Math.max(1, Math.min(N || 1, n || 1)); })();
if (ALPHA && (SH || GRAIN)) { console.error("html: --shutter and --grain do not work with --alpha (a transparent overlay)"); process.exit(2); }
const timeline = o.timeline && existsSync(o.timeline) ? JSON.parse(readFileSync(o.timeline, "utf8")) : null;
const LOOK = o.look ? loadLook(o.look) : null;

const pw = loadPlaywright(); if (!pw) { console.error("playwright not found"); process.exit(2); }
const { browser, renderer, gpu } = await launch(pw, o.gpu);
console.error(`html: renderer ${renderer}${gpu === "off" ? "" : ` (gpu ${gpu})`}`);
const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
await context.addInitScript((spec) => { window.__CV_SPEC = spec; }, { width: W, height: H, fps: FPS, duration: DUR, timeline, alpha: ALPHA, look: LOOK });   // alpha: draw no background, the output is a transparent overlay
if (LOOK) await context.addInitScript((css) => {              // the document has no root element yet when an init script runs: wait for it, which is still before the page's own styles and scripts
  const add = () => { const s = document.createElement("style"); s.id = "__cv_look"; s.textContent = css; (document.head || document.documentElement).appendChild(s); };
  if (document.documentElement) add(); else new MutationObserver((_, ob) => { if (document.documentElement) { ob.disconnect(); add(); } }).observe(document, { childList: true });
}, lookCss(LOOK));
const seen = new Set(), say = (m) => { if (!seen.has(m)) { seen.add(m); console.error(m); } };      // several pages would repeat every message

// ---- serve the scene's folder from a private origin ----
const sceneAbs = resolve(scene), root = resolve(o.root || dirname(sceneAbs)), ORIGIN = "http://cv.local";
const THREE = [process.env.THREE_DIR, join(process.env.HOME || "", ".local/share/craftvideo/three"), join(root, "node_modules/three"), join(process.cwd(), "node_modules/three")]
  .find((d) => d && existsSync(join(d, "build/three.module.js")));
const MASCOT = [process.env.MASCOT_DIR, join(process.env.HOME || "", ".local/share/craftvideo/mascot")].find((d) => d && existsSync(join(d, "clawd/clawd.js")));   // scripts/get_mascot.sh
const MOUNTS = { "/__cv/three/": [THREE, "three.js", "get_three.sh"], "/__cv/mascot/": [MASCOT, "the mascot kit", "get_mascot.sh"] };   // folders outside the scene's, served under a fixed path
const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".css": "text/css", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".avif": "image/avif", ".woff2": "font/woff2",
  ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".wasm": "application/wasm",
  ".mp4": "video/mp4", ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ktx2": "image/ktx2", ".hdr": "application/octet-stream", ".bin": "application/octet-stream" };
const IMPORTMAP = `<script type="importmap">${JSON.stringify({ imports: { "three": "/__cv/three/build/three.module.js", "three/addons/": "/__cv/three/examples/jsm/", "three/examples/jsm/": "/__cv/three/examples/jsm/" } })}</script>`;
const inside = (file, dir) => file === dir || file.startsWith(dir + sep);
await context.route(ORIGIN + "/**", (route) => {
  const p = decodeURIComponent(new URL(route.request().url()).pathname);
  const mount = Object.keys(MOUNTS).find((m) => p.startsWith(m)), [base, what, getter] = mount ? MOUNTS[mount] : [root];
  const file = mount ? (base && join(base, p.slice(mount.length))) : join(root, p);
  if (!file || !inside(resolve(file), base) || !existsSync(file) || !statSync(file).isFile()) {
    if (p !== "/favicon.ico") say(`scene: 404 ${p}${mount && !base ? ` (${what} is not installed: run scripts/${getter})` : ""}`);
    return route.fulfill({ status: 404, body: "not found" });
  }
  let body = readFileSync(file);
  if (resolve(file) === sceneAbs && THREE) {           // give the scene a bare `three` unless it brought its own import map
    let html = body.toString("utf8");
    if (!/type\s*=\s*["']importmap["']/.test(html)) html = /<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, (m) => m + IMPORTMAP) : IMPORTMAP + html;
    body = Buffer.from(html);
  }
  return route.fulfill({ status: 200, contentType: MIME[extname(file).toLowerCase()] || "application/octet-stream", body });
});
async function openPage() {
  const page = await context.newPage();
  page.on("pageerror", (e) => say("scene error: " + e.message));
  page.on("console", (m) => { if ((m.type() === "error" || m.type() === "warning") && !/GL Driver Message.*Performance/.test(m.text())) say(`scene ${m.type()}: ${m.text().slice(0, 600)}`); });   // WebGPU validation errors arrive as warnings
  await page.goto(`${ORIGIN}/${sceneAbs.slice(root.length + 1).split(sep).map(encodeURIComponent).join("/")}`);
  await page.waitForFunction(() => window.craftvideo && typeof window.craftvideo.seek === "function", { timeout: 15000 })
    .catch(() => { console.error("the scene never defined window.craftvideo.seek(t)"); process.exit(3); });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  if (ALPHA) await page.addStyleTag({ content: "html,body{background:transparent !important}" });
  return page;
}
const seek = (page, t) => page.evaluate((tt) => window.craftvideo.seek(tt), t);
const shot = (page, opts = {}) => page.screenshot({ type: "png", omitBackground: ALPHA, ...opts });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- stills: one page, one sheet ----
if (o.stills) {
  const page = await openPage();
  const times = o.stills.split(/\s+/).filter(Boolean), dir = mkdtempSync(join(tmpdir(), "cvstill-")), files = [];
  for (const t of times) { await seek(page, +t); const f = join(dir, `still_${t}.png`); await shot(page, { path: f }); files.push(f); }
  await browser.close();
  // one still is just that image; several are tiled by ffmpeg (3 columns, no labels: the order is the order given)
  if (files.length === 1) { execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-i", files[0], "-frames:v", "1", o.sheet || "sheet.png"]); rmSync(dir, { recursive: true, force: true }); console.error(`${o.sheet || "sheet.png"}: 1 still`); process.exit(0); }
  const cols = 3, args = ["-hide_banner", "-loglevel", "error", "-y"];
  files.forEach((f) => args.push("-i", f));
  const sc = files.map((_, i) => `[${i}:v]scale=640:-1[s${i}]`).join(";");
  const lay = files.map((_, i) => `${(i % cols) * 640}_${Math.floor(i / cols) * Math.round(640 * H / W)}`).join("|");
  args.push("-filter_complex", `${sc};${files.map((_, i) => `[s${i}]`).join("")}xstack=inputs=${files.length}:layout=${lay}[o]`, "-map", "[o]", "-frames:v", "1", o.sheet || "sheet.png");
  execFileSync("ffmpeg", args); rmSync(dir, { recursive: true, force: true });
  console.error(`${o.sheet || "sheet.png"}: ${files.length} stills`); process.exit(0);
}

// ---- lint: audit the layout at many times, report only what is HELD (an entrance or exit is motion, not a fault) ----
if (LINT) {
  const page = await openPage();
  await page.addStyleTag({ content: "*{pointer-events:auto !important}" });          // hit testing (the hidden-text rule) ignores elements with pointer-events none; rendering is unaffected
  const band = o.band === undefined ? 0.18 : +o.band, minFrac = +(o["min-size"] ?? 0.025), step = Math.max(+(o["lint-step"] ?? 0.5), DUR / 600), cstep = Math.max(+(o["contrast-step"] ?? 2), step);
  const HELD = 3, CHELD = 2, ts = []; for (let t = 0; t < DUR - 1e-6; t += step) ts.push(+t.toFixed(3)); ts.push(+Math.max(0, DUR - 1 / FPS).toFixed(3));
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  await page.evaluate(() => { const s = document.createElement("style"); s.id = "__cv_hide_text";   // attached first, then disabled: disabling before attaching does not stick
    s.textContent = "*{color:transparent !important;text-shadow:none !important;-webkit-text-fill-color:transparent !important;-webkit-text-stroke:0 !important;caret-color:transparent !important}svg text{fill:transparent !important;stroke:none !important}"; document.head.appendChild(s); s.disabled = true; });
  const seenAt = new Map();                                   // key -> {rule, detail, ts: [..]}
  const note = (rule, key, detail, t) => { if (!seenAt.has(key)) seenAt.set(key, { rule, detail, ts: [] }); seenAt.get(key).ts.push(t); };
  let nextContrast = 0;
  for (const t of ts) {
    await seek(page, t);
    const r = await page.evaluate(auditPage, { W, H, band, minFrac });
    for (const i of r.issues) note(i.rule, i.key, i.detail, t);
    if (!ALPHA && t >= nextContrast && r.boxes.length) {     // contrast: hide every glyph, screenshot the ground under each text box, compare with the text colour
      nextContrast = t + cstep;
      await page.evaluate(() => { document.getElementById("__cv_hide_text").disabled = false; });
      const png = (await shot(page)).toString("base64");
      await page.evaluate(() => { document.getElementById("__cv_hide_text").disabled = true; });
      const grounds = await page.evaluate(async ({ png, boxes }) => {
        const bmp = await createImageBitmap(await (await fetch("data:image/png;base64," + png)).blob()), c = new OffscreenCanvas(bmp.width, bmp.height), g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(bmp, 0, 0);
        return boxes.map((b) => { const x = Math.max(0, Math.floor(b.l)), y = Math.max(0, Math.floor(b.t)), w = Math.min(bmp.width - x, Math.ceil(b.r - b.l)), h = Math.min(bmp.height - y, Math.ceil(b.b - b.t)); if (w < 2 || h < 2) return null;
          const d = g.getImageData(x, y, w, h).data, px = []; for (let i = 0; i < d.length; i += 16) px.push([d[i], d[i + 1], d[i + 2]]); return px; });
      }, { png, boxes: r.boxes });
      r.boxes.forEach((b, i) => {
        const px = grounds[i], m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/.exec(b.color); if (!px || !m || b.tex || (m[4] !== undefined && +m[4] < 0.3)) return;
        const tl = lum([+m[1], +m[2], +m[3]]), ls = px.map(lum).sort((a, c) => a - c), worst = tl > 0.45 ? ls[Math.floor(ls.length * 0.9)] : ls[Math.floor(ls.length * 0.1)];
        const ratio = (Math.max(tl, worst) + 0.05) / (Math.min(tl, worst) + 0.05), need = b.fs / H >= 0.035 ? 3 : 4.5;
        if (ratio < need) note("contrast", "contrast " + b.d, `low contrast ${ratio.toFixed(1)}:1 (wanted ${need}:1): ${b.d}`, t);
      });
    }
  }
  const issues = [], ERR = new Set(["frame", "clipped", "overlap", "occluded"]);
  for (const [key, v] of seenAt) {                            // runs of neighbouring samples; a run shorter than HELD samples is motion, not a fault
    const gap = (v.rule === "contrast" ? cstep : step) * 1.5, need = v.rule === "contrast" ? CHELD : HELD; let run = [];
    const flush = () => { if (run.length >= need) issues.push({ rule: v.rule, severity: ERR.has(v.rule) ? "error" : "warn", detail: v.detail, from: run[0], to: run[run.length - 1], samples: run.length }); run = []; };
    for (const t of v.ts) { if (run.length && t - run[run.length - 1] > gap) flush(); run.push(t); } flush();
  }
  issues.sort((a, b) => a.from - b.from);
  const errors = issues.filter((i) => i.severity === "error").length;
  // for reading: a time range with several boxes of the same kind (a column of source lines) is one line; the report keeps every box
  const groups = [], HEAD = { small: `under ${(100 * minFrac).toFixed(1)}% of the height`, band: `in the bottom ${Math.round(100 * band)}% reserved for captions`, contrast: "with low contrast" };
  for (const i of issues) {
    const g = HEAD[i.rule] && groups.find((x) => x.rule === i.rule && x.from === i.from && x.to === i.to);
    if (g) { g.count++; if (g.examples.length < 3) g.examples.push(i.detail.replace(/^.*?: /, "")); }
    else groups.push({ ...i, count: 1, examples: [i.detail.replace(/^.*?: /, "")] });
  }
  writeFileSync(out, JSON.stringify({ scene, samples: ts.length, step, band, minSize: minFrac, errors, warnings: issues.length - errors, issues }, null, 1));
  console.error(`html lint: ${ts.length} times audited (every ${step} s), ${errors} error(s), ${issues.length - errors} warning(s) -> ${out}`);
  for (const g of groups) console.error(`  ${g.severity === "error" ? "ERROR" : "warn "} ${g.from.toFixed(1)} to ${g.to.toFixed(1)} s  ` +
    (g.count > 1 ? `${g.count} text boxes ${HEAD[g.rule]}, e.g. ${g.examples.join("; ")}` : g.detail));
  await browser.close(); process.exit(errors ? 1 : 0);
}

// ---- preflight: the scene must be a pure function of t. Visit five times forward, then backward, and compare: history dependence fails here, in seconds ----
// Byte-exact by default. A software GPU renderer can disagree with itself by a level in a pixel or two (the mascot's p5.brush frames do, about 100 dB PSNR apart), which is noise and not history:
// --preflight-psnr DB accepts a revisit whose PSNR against the first visit is at least that (a real dependence on history is far lower: a moved object is about 20 to 40 dB).
function closeEnough(a, b) {
  const d = mkdtempSync(join(tmpdir(), "cvpf-")); writeFileSync(join(d, "a.png"), a); writeFileSync(join(d, "b.png"), b);
  try {
    const r = spawnSync("ffmpeg", ["-hide_banner", "-i", join(d, "a.png"), "-i", join(d, "b.png"), "-lavfi", "psnr", "-f", "null", "-"], { encoding: "utf8" }), m = /average:(\S+)/.exec(r.stderr || "");
    return !!m && (m[1] === "inf" || +m[1] >= PSNR);
  } finally { rmSync(d, { recursive: true, force: true }); }
}
const pages = []; for (let k = 0; k < WORKERS; k++) pages.push(await openPage());
const page0 = pages[0];
if (o.preflight !== "0" && N > 1) {
  const times = [...new Set([0, 0.5, 0.25, 0.75, 1].map((f) => Math.round(f * (N - 1)) / FPS))], visited = new Map();
  for (const t of times) { await seek(page0, t); visited.set(t, await shot(page0)); }
  if (N >= 30 && times.length >= 3 && times.every((t) => visited.get(t).equals(visited.get(times[0])))) console.error("html: WARNING: the picture is identical at 0, 25, 50, 75 and 100% of the duration: seek(t) may be ignoring t. (Fine only if a still picture is the intent.)");
  for (const t of [...times].reverse()) {
    await seek(page0, t);
    const again = await shot(page0);
    if (!again.equals(visited.get(t)) && !(PSNR && closeEnough(again, visited.get(t)))) {
      console.error(`html: the scene is not a pure function of t: the frame at ${t.toFixed(2)} s came out different when visited a second time, in another order. The scene depends on history (a timer, an unseeded random, an animation clock, state built up frame by frame, or renderer state: see reference/motion-graphics.md). Fix it, or skip this check with --preflight 0.`);
      await browser.close(); process.exit(4);
    }
  }
}

// ---- encode: frames are captured on WORKERS pages and written to ffmpeg in order ----
const vf = [];
if (SH) vf.push("format=gbrp16le", `tmix=frames=${SUB}`, `select='not(mod(n+1,${SUB}))'`, `setpts=N/(${FPS}*TB)`);   // average each window of SUB sub-frames, keep one frame per window
if (GRAIN) vf.push("format=yuv420p", `noise=c0s=${GRAIN}:c0f=t+u:c0_seed=20261013`);                                   // luma grain, fixed seed
const enc = ALPHA ? ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", "-r", String(FPS), "-an", out]
                  : [...(vf.length ? ["-vf", vf.join(",")] : []), "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-r", String(FPS), "-an", "-movflags", "+faststart", out];
const ff = spawn("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS * (SH ? SUB : 1)), "-i", "-", ...enc], { stdio: ["pipe", "inherit", "inherit"] });
const done = new Promise((res, rej) => { ff.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg exited " + c)))); });
const t0 = Date.now();
let first = null, issued = 0, written = 0;
const frames = new Map(), AHEAD = WORKERS * 3;
async function capture(page, i) {                               // the picture(s) for output frame i: one, or SUB sub-frames across the shutter
  const t = i / FPS;
  if (!SH) { await seek(page, t); const b = await shot(page); if (i === 0) first = b; return [b]; }
  const S = SH / 360 / FPS, ts = Array.from({ length: SUB }, (_, k) => Math.min(DUR, Math.max(0, t + ((k + 0.5) / SUB - 0.5) * S))), bufs = new Array(SUB);
  await seek(page, ts[0]); bufs[0] = await shot(page); await seek(page, ts[SUB - 1]); bufs[SUB - 1] = await shot(page);
  if (bufs[0].equals(bufs[SUB - 1])) return bufs.fill(bufs[0]);   // nothing moves across this shutter: one picture is all of them
  for (let k = 1; k < SUB - 1; k++) { await seek(page, ts[k]); bufs[k] = await shot(page); }
  return bufs;
}
async function worker(page) {
  for (;;) {
    while (issued - written >= AHEAD) await sleep(2);           // do not run far ahead of the writer
    const i = issued++; if (i >= N) return;
    frames.set(i, await capture(page, i));
  }
}
async function writer() {
  for (let i = 0; i < N; i++) {
    while (!frames.has(i)) await sleep(2);
    const bufs = frames.get(i); frames.delete(i);
    for (const b of bufs) if (!ff.stdin.write(b)) await new Promise((r) => ff.stdin.once("drain", r));
    written = i + 1;
  }
  ff.stdin.end();
}
try { await Promise.all([writer(), ...pages.map(worker)]); await done; } catch (e) { console.error("html: " + e.message); await browser.close(); process.exit(1); }
// determinism guard: seek(0) after the whole run must reproduce the first frame, or the scene is not a pure function of t (not with a shutter: frame 0 is an average)
if (first && N > 1) { await seek(page0, 0); if (!(await shot(page0)).equals(first)) console.error("html: WARNING: the frame at t=0 came out different the second time. The scene depends on history (a timer, an unseeded random, an animation clock, or renderer state: see reference/motion-graphics.md). Frames may not match what you previewed."); }
await browser.close();
console.error(`html: ${N} frames at ${W}x${H} @ ${FPS} -> ${out} (${((Date.now() - t0) / N).toFixed(0)} ms per frame${WORKERS > 1 ? `, ${WORKERS} workers` : ""}${SH ? `, shutter ${SH} over ${SUB} sub-frames` : ""}${GRAIN ? `, grain ${GRAIN}` : ""}${ALPHA ? ", with alpha" : ""})`);
