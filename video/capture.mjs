// capture.mjs — records STORMDANCER running in demo mode, via CDP screencast.
//
// Launches the Playwright-cache headless Chromium on the game with
// ?demo=1&start=6 (the autopilot joins mid-action), subscribes to
// Page.startScreencast, and saves every frame as a JPEG plus an index.json
// with each frame's screencast timestamp, so the assembler can rebuild an
// exact 30 fps timeline. No dependencies: Node's global WebSocket is the
// CDP transport.
//
//   node video/capture.mjs            (CAPTURE_MS env overrides duration)

import { spawn } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..");
const CHROME =
  process.env.CHROME_BIN ||
  join(process.env.HOME, ".cache/ms-playwright/chromium_headless_shell-1255/chrome-headless-shell-linux64/chrome-headless-shell");
const PORT = 9333;
const DURATION_MS = parseInt(process.env.CAPTURE_MS || "21500", 10);
const GAME_URL = "file://" + join(repoRoot, "game", "index.html") + "?demo=1&start=6";
const OUT_DIR = join(here, "frames");

rmSync(OUT_DIR, { recursive: true, force: true });
mkdirSync(OUT_DIR, { recursive: true });

const chrome = spawn(CHROME, [
  `--remote-debugging-port=${PORT}`,
  "--window-size=1280,720",
  "--no-sandbox",
  "--hide-scrollbars",
  "--force-device-scale-factor=1",
  "--user-data-dir=/tmp/cdp-profile-postx",
  GAME_URL,
], { stdio: ["ignore", "ignore", "pipe"] });
chrome.stderr.on("data", () => {});

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function pageWsUrl() {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const targets = await res.json();
      const page = targets.find(t => t.type === "page" && t.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* not up yet */ }
    await sleep(250);
  }
  throw new Error("CDP page target never appeared");
}

const frames = [];
let msgId = 0;
const pending = new Map();
let ws;

function send(method, params = {}) {
  const id = ++msgId;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise(resolve => pending.set(id, resolve));
}

async function main() {
  const url = await pageWsUrl();
  ws = new WebSocket(url);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg.result); pending.delete(msg.id); return; }
    if (msg.method === "Page.screencastFrame") {
      const { data, metadata, sessionId } = msg.params;
      const name = `f${String(frames.length).padStart(5, "0")}.jpg`;
      writeFileSync(join(OUT_DIR, name), Buffer.from(data, "base64"));
      frames.push({ file: name, ts: metadata.timestamp });
      send("Page.screencastFrameAck", { sessionId });
    }
  };

  await send("Page.enable");
  await send("Page.startScreencast", { format: "jpeg", quality: 82, maxWidth: 1280, maxHeight: 720, everyNthFrame: 1 });
  console.log(`screencast started; recording ${DURATION_MS} ms of demo gameplay…`);
  await sleep(DURATION_MS);
  await send("Page.stopScreencast").catch(() => {});
  ws.close();

  if (frames.length === 0) throw new Error("screencast produced no frames");
  const t0 = frames[0].ts;
  const index = frames.map(f => ({ file: f.file, t: +(f.ts - t0).toFixed(4) }));
  writeFileSync(join(OUT_DIR, "index.json"), JSON.stringify({ fps_hint: frames.length / (frames[frames.length - 1].ts - t0), frames: index }, null, 1));
  console.log(`captured ${frames.length} frames over ${(frames[frames.length - 1].ts - t0).toFixed(2)}s -> ${OUT_DIR}`);
}

main()
  .catch(err => { console.error("capture failed:", err.message); process.exitCode = 1; })
  .finally(() => { chrome.kill("SIGKILL"); });
