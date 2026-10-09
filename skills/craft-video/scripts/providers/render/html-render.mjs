// html-render.mjs: render an HTML scene to an H.264 mp4 (or stills) with headless Chromium + ffmpeg.
// A scene page must define window.craftvideo.seek(t) (seconds): make the DOM a PURE FUNCTION OF t, return when ready.
// The spec and the narration cues are available as window.__CV_SPEC = {width,height,fps,duration,timeline}.
//   node html-render.mjs scene.html out.mp4 --width 1920 --height 1080 --fps 30 --duration 30 [--timeline timeline.json]
//   node html-render.mjs scene.html out.mp4 ... --stills "1.4 8.9" --sheet sheet.png
//   node html-render.mjs --check
import { createRequire } from "node:module";
import { spawn, execFileSync } from "node:child_process";
import { readFileSync, existsSync, mkdtempSync, rmSync } from "node:fs";
import { resolve, join } from "node:path";
import { tmpdir } from "node:os";

const require = createRequire(import.meta.url);
function loadPlaywright() {
  const bases = [process.env.PLAYWRIGHT_DIR, process.env.VOICESTUDIO_DIR && join(process.env.VOICESTUDIO_DIR, "node_modules"),
    "/mnt/ai/VoiceStudio/node_modules", process.cwd(), join(process.env.HOME || "", ".local/lib/node_modules")].filter(Boolean);
  for (const b of bases) { try { return require(require.resolve("playwright", { paths: [b] })); } catch {} }
  try { return require("playwright"); } catch {}
  return null;
}
async function launch(pw) {
  const exe = process.env.CRAFTVIDEO_CHROMIUM;
  const flags = ["--force-device-scale-factor=1", "--hide-scrollbars", "--font-render-hinting=none"];
  const tries = [exe ? { executablePath: exe } : {}, { executablePath: "/usr/bin/chromium" }, { executablePath: "/usr/bin/google-chrome-stable" }];
  let last;
  for (const t of tries) {
    if (t.executablePath && !existsSync(t.executablePath)) continue;
    try { return await pw.chromium.launch({ ...t, args: flags }); } catch (e) { last = e; }
  }
  throw last || new Error("no Chromium found: install one for Playwright, or set CRAFTVIDEO_CHROMIUM");
}

const argv = process.argv.slice(2);
if (argv[0] === "--check") {
  const pw = loadPlaywright();
  if (!pw) { console.log("playwright not found (set PLAYWRIGHT_DIR to a node_modules that has it)"); process.exit(1); }
  try { const b = await launch(pw); await b.close(); process.exit(0); } catch (e) { console.log("no usable Chromium: " + String(e.message).split("\n")[0]); process.exit(1); }
}
const [scene, out, ...rest] = argv;
const o = { width: 1920, height: 1080, fps: 30, duration: 30 };
for (let i = 0; i < rest.length; i += 2) o[rest[i].replace(/^--/, "")] = rest[i + 1];
const W = +o.width, H = +o.height, FPS = +o.fps, DUR = +o.duration, N = Math.round(FPS * DUR);
const timeline = o.timeline && existsSync(o.timeline) ? JSON.parse(readFileSync(o.timeline, "utf8")) : null;

const pw = loadPlaywright(); if (!pw) { console.error("playwright not found"); process.exit(2); }
const browser = await launch(pw);
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on("pageerror", (e) => console.error("scene error:", e.message));
await page.addInitScript((spec) => { window.__CV_SPEC = spec; }, { width: W, height: H, fps: FPS, duration: DUR, timeline });
await page.goto("file://" + resolve(scene));
await page.waitForFunction(() => window.craftvideo && typeof window.craftvideo.seek === "function", { timeout: 15000 })
  .catch(() => { console.error("the scene never defined window.craftvideo.seek(t)"); process.exit(3); });
await page.evaluate(() => document.fonts && document.fonts.ready);
const seek = (t) => page.evaluate((tt) => window.craftvideo.seek(tt), t);

if (o.stills) {
  const times = o.stills.split(/\s+/).filter(Boolean), dir = mkdtempSync(join(tmpdir(), "cvstill-")), files = [];
  for (const t of times) { await seek(+t); const f = join(dir, `still_${t}.png`); await page.screenshot({ path: f }); files.push(f); }
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

const ff = spawn("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
  "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-r", String(FPS), "-an", "-movflags", "+faststart", out],
  { stdio: ["pipe", "inherit", "inherit"] });
const done = new Promise((res, rej) => { ff.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg exited " + c)))); });
for (let i = 0; i < N; i++) {
  await seek(i / FPS);
  const buf = await page.screenshot({ type: "png" });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
}
ff.stdin.end(); await done; await browser.close();
console.error(`html: ${N} frames at ${W}x${H} @ ${FPS} -> ${out}`);
