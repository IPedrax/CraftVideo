// html-render.mjs: render an HTML scene to an H.264 mp4 (or stills, or a transparent overlay) with headless Chromium + ffmpeg.
// A scene page must define window.craftvideo.seek(t) (seconds): make the DOM / canvas a PURE FUNCTION OF t, return when ready.
// The spec and the narration cues are available as window.__CV_SPEC = {width,height,fps,duration,timeline,alpha}.
//   node html-render.mjs scene.html out.mp4 --width 1920 --height 1080 --fps 30 --duration 30 [--timeline timeline.json]
//   node html-render.mjs scene.html out.mp4 ... --stills "1.4 8.9" --sheet sheet.png
//   node html-render.mjs scene.html out.mov ... --alpha 1        (transparent background -> ProRes 4444 with alpha, for overlays)
//   node html-render.mjs scene.html out.mp4 ... --gpu auto       (WebGL on the GPU: off | auto | vulkan | egl; env CRAFTVIDEO_GPU.
//                                                                 WebGPU scenes: request the adapter with powerPreference "high-performance", fall back to
//                                                                 forceFallbackAdapter (software), and await device.queue.onSubmittedWorkDone() in seek())
//   node html-render.mjs --check
// The page is served from a private origin (http://cv.local) out of the scene's folder (--root DIR to widen it), so ES modules,
// import maps, fetch() and GLB/texture loading all work. If three.js is installed (scripts/get_three.sh) a bare `import "three"` and
// `import ... from "three/addons/..."` resolve to it automatically; a scene with its own import map keeps it.
import { createRequire } from "node:module";
import { spawn, execFileSync } from "node:child_process";
import { readFileSync, existsSync, mkdtempSync, rmSync, statSync } from "node:fs";
import { resolve, join, dirname, extname, sep } from "node:path";
import { tmpdir } from "node:os";

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
const timeline = o.timeline && existsSync(o.timeline) ? JSON.parse(readFileSync(o.timeline, "utf8")) : null;

const pw = loadPlaywright(); if (!pw) { console.error("playwright not found"); process.exit(2); }
const { browser, renderer, gpu } = await launch(pw, o.gpu);
console.error(`html: renderer ${renderer}${gpu === "off" ? "" : ` (gpu ${gpu})`}`);
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on("pageerror", (e) => console.error("scene error:", e.message));
page.on("console", (m) => { if ((m.type() === "error" || m.type() === "warning") && !/GL Driver Message.*Performance/.test(m.text())) console.error(`scene ${m.type()}:`, m.text().slice(0, 600)); });   // WebGPU validation errors arrive as warnings
await page.addInitScript((spec) => { window.__CV_SPEC = spec; }, { width: W, height: H, fps: FPS, duration: DUR, timeline, alpha: ALPHA });   // alpha: draw no background, the output is a transparent overlay

// ---- serve the scene's folder from a private origin ----
const sceneAbs = resolve(scene), root = resolve(o.root || dirname(sceneAbs)), ORIGIN = "http://cv.local";
const THREE = [process.env.THREE_DIR, join(process.env.HOME || "", ".local/share/craftvideo/three"), join(root, "node_modules/three"), join(process.cwd(), "node_modules/three")]
  .find((d) => d && existsSync(join(d, "build/three.module.js")));
const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".css": "text/css", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".avif": "image/avif", ".woff2": "font/woff2",
  ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".wasm": "application/wasm",
  ".mp4": "video/mp4", ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ktx2": "image/ktx2", ".hdr": "application/octet-stream", ".bin": "application/octet-stream" };
const IMPORTMAP = `<script type="importmap">${JSON.stringify({ imports: { "three": "/__cv/three/build/three.module.js", "three/addons/": "/__cv/three/examples/jsm/", "three/examples/jsm/": "/__cv/three/examples/jsm/" } })}</script>`;
const inside = (file, dir) => file === dir || file.startsWith(dir + sep);
await page.route(ORIGIN + "/**", (route) => {
  const p = decodeURIComponent(new URL(route.request().url()).pathname);
  let file = p.startsWith("/__cv/three/") ? (THREE && join(THREE, p.slice(12))) : join(root, p);
  const base = p.startsWith("/__cv/three/") ? THREE : root;
  if (!file || !inside(resolve(file), base) || !existsSync(file) || !statSync(file).isFile()) {
    if (p !== "/favicon.ico") console.error(`scene: 404 ${p}${p.startsWith("/__cv/three/") && !THREE ? " (three.js is not installed: run scripts/get_three.sh)" : ""}`);
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
await page.goto(`${ORIGIN}/${sceneAbs.slice(root.length + 1).split(sep).map(encodeURIComponent).join("/")}`);
await page.waitForFunction(() => window.craftvideo && typeof window.craftvideo.seek === "function", { timeout: 15000 })
  .catch(() => { console.error("the scene never defined window.craftvideo.seek(t)"); process.exit(3); });
await page.evaluate(() => document.fonts && document.fonts.ready);
if (ALPHA) await page.addStyleTag({ content: "html,body{background:transparent !important}" });
const seek = (t) => page.evaluate((tt) => window.craftvideo.seek(tt), t);
const shot = (opts = {}) => page.screenshot({ type: "png", omitBackground: ALPHA, ...opts });

if (o.stills) {
  const times = o.stills.split(/\s+/).filter(Boolean), dir = mkdtempSync(join(tmpdir(), "cvstill-")), files = [];
  for (const t of times) { await seek(+t); const f = join(dir, `still_${t}.png`); await shot({ path: f }); files.push(f); }
  await browser.close();
  // one still is just that image; several are tiled by ffmpeg (3 columns, no labels: the order is the order given)
  if (files.length === 1) { execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-i", files[0], "-frames:v", "1", o.sheet || "sheet.png"]); rmSync(dir, { recursive: true, force: true }); console.error(`${o.sheet || "sheet.png"}: 1 still`); process.exit(0); }
  const cols = 3, rows = Math.ceil(files.length / cols), args = ["-hide_banner", "-loglevel", "error", "-y"];
  files.forEach((f) => args.push("-i", f));
  const sc = files.map((_, i) => `[${i}:v]scale=640:-1[s${i}]`).join(";");
  const lay = files.map((_, i) => `${(i % cols) * 640}_${Math.floor(i / cols) * Math.round(640 * H / W)}`).join("|");
  args.push("-filter_complex", `${sc};${files.map((_, i) => `[s${i}]`).join("")}xstack=inputs=${files.length}:layout=${lay}[o]`, "-map", "[o]", "-frames:v", "1", o.sheet || "sheet.png");
  execFileSync("ffmpeg", args); rmSync(dir, { recursive: true, force: true });
  console.error(`${o.sheet || "sheet.png"}: ${files.length} stills`); process.exit(0);
}

const enc = ALPHA ? ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", "-r", String(FPS), "-an", out]
                  : ["-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-r", String(FPS), "-an", "-movflags", "+faststart", out];
const ff = spawn("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-", ...enc], { stdio: ["pipe", "inherit", "inherit"] });
const done = new Promise((res, rej) => { ff.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg exited " + c)))); });
const t0 = Date.now();
let first = null;
for (let i = 0; i < N; i++) {
  await seek(i / FPS);
  const buf = await shot();
  if (i === 0) first = buf;
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
}
ff.stdin.end(); await done;
// determinism guard: seek(0) after the whole run must reproduce the first frame, or the scene is not a pure function of t
if (first && N > 1) { await seek(0); if (!(await shot()).equals(first)) console.error("html: WARNING: the frame at t=0 came out different the second time. The scene depends on history (a timer, an unseeded random, an animation clock, or renderer state: see reference/motion-graphics.md). Frames may not match what you previewed."); }
await browser.close();
console.error(`html: ${N} frames at ${W}x${H} @ ${FPS} -> ${out} (${((Date.now() - t0) / N).toFixed(0)} ms per frame${ALPHA ? ", with alpha" : ""})`);
