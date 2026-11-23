# STORMDANCER — a game built from one prompt

An entry for the make.fun bounty **"The agent builds a game from one prompt"**:
https://make.fun/bounty/post-x-the-agent-builds-a-game-from-20261122-1709

The idea: an AI coding agent receives exactly **one** prompt, writes a whole
browser game from it in a single pass, and the video shows the prompt, the
code streaming in, and the game playing itself.

## The one prompt

This is the only brief the game was built from — it is also the text typed
out on screen in the video:

> Build a tiny browser game in one HTML file: I'm a neon dragonfly weaving through a thunderstorm — hold to climb, release to dive, snatch glowing fireflies, dodge storm clouds, 60-second score attack, juicy particles and screen shake.

## The game

**STORMDANCER** (`game/index.html`, one self-contained file, no dependencies,
no build step): you are the dragonfly. Hold to climb, release to dive. Snatch
fireflies (+10, combos multiply), dodge the charged storm clouds (3 hearts),
60-second score attack, particle bursts, screen shake, lightning and rain.

- **Play it:** open `game/index.html` in a browser. Controls: hold
  Space / ↑ / mouse / touch to climb, release to dive.
- **Demo mode:** `game/index.html?demo=1` — an autopilot plays the game
  (this is what the video captures). `?demo=1&start=6` joins mid-action;
  `?t=<seconds>` renders one deterministic frame at that moment.
- The simulation is deterministic (fixed 240 Hz timestep, seeded spawns),
  so the demo plays identically on every machine.

## The video

`video/final.mp4` — 39 s, 1280×720, 30 fps: (1) the prompt card, (2) a
montage of the game's real source lines streaming into an editor, (3) twenty
seconds of genuine demo-mode gameplay, (4) make.fun's official referral end
card from the press pack with the code typed in. Production scripts:

```bash
node video/capture.mjs     # CDP screencast of the live demo (headless Chromium)
python3 video/render.py    # PIL renders cards/montage/end card, picks frames
bash video/assemble.sh     # ffmpeg: encode + concat -> video/final.mp4
```

## Entry program

`main.ts` (Node, standard library only) copies `POST.json` from the bot
directory to the output directory:

```bash
mkdir -p out
MAKEFUN_BOT_DIR=. MAKEFUN_OUTPUT_DIR=out node main.ts   # -> out/POST.json
```

`POST.json` holds the URL of the X post that carries the video.

## License

MIT — see `LICENSE`.
