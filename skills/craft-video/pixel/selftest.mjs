// node selftest.mjs: the parts of cvpixel.js that are plain logic (no browser): held time, Aseprite frame order, durations and repeat, both sheet shapes, hit-stop, the shake.
import { tick, frameAt, shake, parseSheet, hitstop } from "./cvpixel.js";
import assert from "node:assert/strict";

assert.equal(tick(0.49, 12), 5 / 12); assert.equal(tick(1 / 12, 12), 1 / 12); assert.equal(tick(0.0833, 12), 0);       // held on whole frames, and exact on a frame edge
assert.ok([0, 0.1, 0.5, 2.25, 7.999].every((t, i, a) => i === 0 || tick(t, 12) >= tick(a[i - 1], 12)), "tick never goes backwards");

const mk = (dir, ms = [100, 100, 100, 100]) => parseSheet({ frames: ms.map((duration, i) => ({ filename: `f ${i}`, frame: { x: 16 * i, y: 0, w: 16, h: 16 }, duration })),
  meta: { image: "s.png", frameTags: [{ name: "t", from: 0, to: ms.length - 1, direction: dir }] } });
const run = (sh, secs) => secs.map((s) => frameAt(sh, "t", s));
assert.deepEqual(run(mk("forward"), [0, 0.1, 0.2, 0.3, 0.4]), [0, 1, 2, 3, 0]);                                        // loops
assert.deepEqual(run(mk("reverse"), [0, 0.1, 0.2, 0.3]), [3, 2, 1, 0]);
assert.deepEqual(run(mk("pingpong"), [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]), [0, 1, 2, 3, 2, 1, 0]);                       // the ends are not repeated: 0 1 2 3 2 1
assert.deepEqual(run(mk("pingpong_reverse"), [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]), [3, 2, 1, 0, 1, 2, 3]);
assert.deepEqual(run(mk("forward", [50, 200, 50]), [0, 0.049, 0.05, 0.249, 0.25, 0.299, 0.3]), [0, 0, 1, 1, 2, 2, 0]);   // durations are honoured
assert.equal(frameAt(mk("forward"), "t", 99, { once: true }), 3);                                                      // once holds the last frame
assert.equal(frameAt(mk("forward"), null, 0.15), 1);                                                                   // no tag: every frame in order
assert.throws(() => frameAt(mk("forward"), "nope", 0), /no tag/);
const rep = mk("forward"); rep.tags.t.repeat = "2";                                                                    // repeat "2": two plays of 0 1 2 3, then the last frame holds
assert.deepEqual(run(rep, [0.35, 0.4, 0.75, 0.8, 5]), [3, 0, 3, 3, 3]);
assert.deepEqual([0, 4.9, 5, 5.1, 5.19].map((t) => hitstop(t, 5, 0.2)), [0, 4.9, 5, 5, 5]);                          // t, then frozen at 5 for 0.2 s ...
assert.ok(Math.abs(hitstop(5.2, 5, 0.2) - 5) < 1e-9 && Math.abs(hitstop(6, 5, 0.2) - 5.8) < 1e-9);                    // ... then t minus the time spent frozen

const arr = parseSheet({ frames: [{ frame: { x: 0, y: 0, w: 8, h: 8 }, duration: 90 }], meta: { image: "a.png" } });                    // json-array
const hash = parseSheet({ frames: { "a 0.aseprite": { frame: { x: 0, y: 0, w: 8, h: 8 }, duration: 90 }, "a 1.aseprite": { frame: { x: 8, y: 0, w: 8, h: 8 }, duration: 90 } }, meta: { image: "a.png" } }); // json-hash
assert.equal(arr.frames.length, 1); assert.deepEqual(hash.frames.map((f) => f.filename), ["a 0.aseprite", "a 1.aseprite"]); assert.equal(hash.frames[1].frame.x, 8);

const a = [0, 0.01, 0.04, 0.05, 1.5].map((t) => shake(t, 2, 24)), b = [0, 0.01, 0.04, 0.05, 1.5].map((t) => shake(t, 2, 24));
assert.deepEqual(a, b, "the same time gives the same shake"); assert.deepEqual(a[0], a[1], "it holds for 1/24 s");
assert.ok(a.every(([x, y]) => Math.abs(x) <= 2 && Math.abs(y) <= 2 && Number.isInteger(x) && Number.isInteger(y)), "whole pixels within the amplitude");
const seen = new Set(Array.from({ length: 200 }, (_, i) => shake(i / 24, 2, 24).join(","))); assert.ok(seen.size > 10, "it moves");
console.log("cvpixel selftest: ok (held time, 4 tag directions, durations, repeat, both sheet shapes, hit-stop, shake)");
