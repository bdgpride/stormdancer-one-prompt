#!/usr/bin/env python3
"""render.py — renders every non-gameplay frame of the video with PIL.

Segments produced (1280x720, 30 fps, PNG frames):
  framesA/  prompt card      4.0 s — "ONE PROMPT." + the prompt typed out
  framesB/  agent montage   10.0 s — the game's real source lines streaming
                                     into an editor window + build log
  framesC/  gameplay        20.0 s — frames picked from capture.mjs output
                                     onto an exact 30 fps timeline, with the
                                     "Built from one prompt. Zero edits."
                                     overlay baked into the first seconds
  framesD/  end card         5.0 s — make.fun's official 16:9 referral card
                                     (press pack, sha256-verified against
                                     manifest.json) over the blurred last
                                     gameplay frame, referral code typed in

Run after capture.mjs:  python3 video/render.py
Then:                   bash video/assemble.sh
"""

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "assets")
W, H, FPS = 1280, 720, 30

REFERRAL_CODE = "2my8wvpk"
PROMPT = (
    "Build a tiny browser game in one HTML file: I'm a neon dragonfly weaving "
    "through a thunderstorm \u2014 hold to climb, release to dive, snatch glowing "
    "fireflies, dodge storm clouds, 60-second score attack, juicy particles "
    "and screen shake."
)

FONTS = "/usr/share/fonts/truetype/dejavu"
SANS_BOLD = os.path.join(FONTS, "DejaVuSans-Bold.ttf")
SANS = os.path.join(FONTS, "DejaVuSans.ttf")
MONO = os.path.join(FONTS, "DejaVuSansMono.ttf")
MONO_BOLD = os.path.join(FONTS, "DejaVuSansMono-Bold.ttf")
JB_MONO_BOLD = os.path.join(ASSETS, "JetBrainsMono-Bold.ttf")


def font(path, size):
    return ImageFont.truetype(path, size)


def lerp(a, b, p):
    return a + (b - a) * p


def ease(p):
    return p * p * (3 - 2 * p)


# ---------------------------------------------------------------- assets
def fetch(url, dest):
    # curl with retries: this VM's connection sometimes truncates transfers
    if not os.path.exists(dest):
        print("fetch", url)
        head = subprocess.run(["curl", "-sIL", url], capture_output=True, text=True).stdout
        sizes = re.findall(r"content-length:\s*(\d+)", head, re.I)
        want = int(sizes[-1]) if sizes else None  # last block = final response
        for attempt in range(4):
            subprocess.run(["curl", "-sL", "--retry", "3", "-o", dest, url], check=True)
            if want is None or os.path.getsize(dest) == want:
                break
            print(f"  truncated ({os.path.getsize(dest)} of {want} bytes), retry {attempt + 1}")
            os.remove(dest)
        if not os.path.exists(dest):
            raise RuntimeError(f"could not download {url}")
    return dest


def get_assets():
    """The end card comes from make.fun's press pack, verified against the
    manifest's own sha256 — the file is used exactly as published."""
    os.makedirs(ASSETS, exist_ok=True)
    manifest_path = fetch("https://make.fun/press/manifest.json",
                          os.path.join(ASSETS, "manifest.json"))
    manifest = json.load(open(manifest_path))
    card_entry = next(
        f for f in manifest["referral_card"]["files"]
        if f["path"] == "referral-card/16x9/makefun-card-16x9-transparent.webm"
    )
    card = fetch(card_entry["url"], os.path.join(ASSETS, "card-16x9.webm"))
    digest = hashlib.sha256(open(card, "rb").read()).hexdigest()
    assert digest == card_entry["sha256"], f"end card sha256 mismatch: {digest}"
    print("end card verified:", digest[:16], "…")
    fetch("https://github.com/JetBrains/JetBrainsMono/raw/master/fonts/ttf/JetBrainsMono-Bold.ttf",
          JB_MONO_BOLD)
    # decode the card (VP9 alpha) to 1280x720 PNG frames at 30 fps
    card_dir = os.path.join(ASSETS, "cardframes")
    if not os.path.exists(os.path.join(card_dir, "075.png")):
        os.makedirs(card_dir, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", card,
             "-vf", "scale=1280:720,fps=30", os.path.join(card_dir, "%03d.png")],
            check=True)
    return card_dir


def gradient_bg(top=(7, 10, 30), bottom=(18, 8, 43)):
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        p = y / H
        c = tuple(round(lerp(top[i], bottom[i], p)) for i in range(3))
        for x in range(0, W, 8):
            for dx in range(8):
                px[x + dx, y] = c
    return img


def save_frames(frames, dirname):
    out = os.path.join(HERE, dirname)
    os.makedirs(out, exist_ok=True)
    for old in os.listdir(out):
        os.remove(os.path.join(out, old))
    for i, img in enumerate(frames):
        img.save(os.path.join(out, f"{i:04d}.png"))
    print(dirname, len(frames), "frames")


# ---------------------------------------------------------------- segment A
def wrap_words(draw, words, fnt, max_w):
    lines, cur = [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def segment_a():
    bg = gradient_bg()
    frames = []
    title_f = font(SANS_BOLD, 98)
    label_f = font(SANS_BOLD, 25)
    prompt_f = font(MONO, 30)
    tail_f = font(SANS_BOLD, 31)
    words = PROMPT.split(" ")
    probe = ImageDraw.Draw(bg)
    lines_full = wrap_words(probe, words, prompt_f, 940)
    total_words = len(words)

    for k in range(4 * FPS):
        t = k / FPS
        img = bg.copy()
        d = ImageDraw.Draw(img, "RGBA")
        # title pops in
        p = min(1.0, max(0.0, (t - 0.10) / 0.35))
        if p > 0:
            size = round(lerp(70, 98, ease(p)))
            tf = font(SANS_BOLD, size)
            d.text((W / 2 + 3, 118 + 3), "ONE PROMPT.", font=tf, fill=(20, 120, 140, 160), anchor="ma")
            d.text((W / 2, 118), "ONE PROMPT.", font=tf, fill=(255, 255, 255, 255), anchor="ma")
        # prompt box
        box = (140, 292, 1140, 566)
        d.rounded_rectangle(box, radius=18, fill=(13, 17, 40, 255), outline=(55, 244, 255, 255), width=2)
        d.text((140, 258), "THE WHOLE BRIEF:", font=label_f, fill=(123, 241, 255, 255))
        # typed words
        tp = min(1.0, max(0.0, (t - 0.65) / 2.45))
        shown = int(total_words * ease(tp)) if tp > 0 else 0
        shown_words = words[:shown]
        lines = wrap_words(d, shown_words, prompt_f, 940)
        y = 322
        for ln in lines:
            d.text((172, y), ln, font=prompt_f, fill=(225, 233, 255, 255))
            y += 42
        # blinking caret at the end of the typed text
        if t > 0.65 and int(t * 2.4) % 2 == 0:
            last = lines[-1] if lines else ""
            cx = 172 + d.textlength(last, font=prompt_f) + 4
            cy = 322 + (len(lines) - 1) * 42 if lines else 322
            d.rectangle((cx, cy + 4, cx + 15, cy + 36), fill=(55, 244, 255, 255))
        # closing line
        if t > 3.25:
            a = min(1.0, (t - 3.25) / 0.4)
            d.text((W / 2, 616), "\u2014 that\u2019s it. watch what it built \u25b8",
                   font=tail_f, fill=(255, 224, 102, int(255 * a)), anchor="ma")
        frames.append(img)
    return frames


# ---------------------------------------------------------------- segment B
TOKEN_RE = re.compile(
    r"(?P<str>\"[^\"\n]*\"|'[^'\n]*')"
    r"|(?P<num>\b\d+(?:\.\d+)?\b)"
    r"|(?P<kw>\b(?:const|let|var|function|return|if|else|for|while|new|typeof)\b)"
)
COLORS = {"str": (255, 212, 121), "num": (123, 241, 255), "kw": (255, 126, 219),
          "plain": (215, 224, 255), "comment": (122, 148, 110)}


def draw_code_line(d, x, y, text, fnt, char_w, upto=None):
    if upto is not None:
        text = text[:upto]
    if text.lstrip().startswith("//"):
        d.text((x, y), text, font=fnt, fill=COLORS["comment"])
        return
    pos = 0
    for m in TOKEN_RE.finditer(text):
        if m.start() > pos:
            d.text((x + pos * char_w, y), text[pos:m.start()], font=fnt, fill=COLORS["plain"])
        d.text((x + m.start() * char_w, y), m.group(0), font=fnt, fill=COLORS[m.lastgroup])
        pos = m.end()
    if pos < len(text):
        d.text((x + pos * char_w, y), text[pos:], font=fnt, fill=COLORS["plain"])


def pick_code_lines():
    src = open(os.path.join(ROOT, "game", "index.html")).read().splitlines()
    start = next(i for i, ln in enumerate(src) if "autopilot (demo mode)" in ln)
    picked = []
    for i in range(start, len(src)):
        text = src[i].rstrip()
        if not text.strip():
            continue
        if len(text) > 92:
            text = text[:92] + "\u2026"
        picked.append((i + 1, text))
        if len(picked) >= 64:
            break
    return picked, len(src)


def segment_b():
    lines, total_lines = pick_code_lines()
    frames = []
    mono = font(MONO, 20)
    char_w = mono.getlength("M")
    small = font(MONO, 18)
    log_f = font(MONO_BOLD, 20)
    logs = [
        (0.5, "$ agent run \u2014 brief: 1 prompt, 1 file, no edits after"),
        (3.0, f"> writing game/index.html \u2026 {total_lines} lines"),
        (5.7, "> dependencies: 0 \u00b7 assets: 0 \u00b7 build step: none"),
        (8.2, "> done in one pass \u2713 launching demo \u25b8"),
    ]
    VISIBLE = 16
    for k in range(10 * FPS):
        t = k / FPS
        img = Image.new("RGB", (W, H), (9, 11, 26))
        d = ImageDraw.Draw(img, "RGBA")
        # window chrome
        d.rectangle((0, 0, W, 46), fill=(20, 24, 48))
        for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse((18 + i * 26, 15, 34 + i * 26, 31), fill=c)
        d.text((110, 13), "game/index.html \u2014 the whole game, written from the prompt",
               font=small, fill=(160, 172, 210))
        # progress hairline
        d.rectangle((0, 46, W * min(1.0, t / 9.4), 49), fill=(55, 244, 255))
        # code reveal: accelerating stream, current line types out
        p = min(1.0, max(0.0, (t - 0.4) / 8.6))
        reveal = len(lines) * (p * p * (3 - 2 * p))
        full = int(reveal)
        frac = reveal - full
        first = max(0, full - VISIBLE + 1)
        y = 66
        for j in range(first, min(full + 1, len(lines))):
            lineno, text = lines[j]
            d.text((26, y), str(lineno).rjust(4), font=mono, fill=(61, 74, 107))
            upto = None
            if j == full:
                upto = max(1, int(len(text) * frac))
            draw_code_line(d, 96, y, text, mono, char_w, upto)
            if j == full and int(t * 2.4) % 2 == 0:
                cx = 96 + (upto or 0) * char_w
                d.rectangle((cx, y + 2, cx + 10, y + 24), fill=(55, 244, 255))
            y += 31
        # terminal strip
        d.rectangle((0, 636, W, H), fill=(4, 5, 13))
        d.line((0, 636, W, 636), fill=(55, 244, 255), width=1)
        shown_logs = [s for (when, s) in logs if t >= when]
        ly = 652
        for s in shown_logs[-2:]:
            d.text((26, ly), s, font=log_f, fill=(74, 246, 160))
            ly += 30
        frames.append(img)
    return frames


# ---------------------------------------------------------------- segment C
def segment_c():
    cap_dir = os.path.join(HERE, "frames")
    index = json.load(open(os.path.join(cap_dir, "index.json")))["frames"]
    frames = []
    overlay_f = font(SANS_BOLD, 34)
    n_out = 20 * FPS
    src = 0
    for k in range(n_out):
        t = k / FPS
        while src + 1 < len(index) and index[src + 1]["t"] <= t:
            src += 1
        img = Image.open(os.path.join(cap_dir, index[src]["file"])).convert("RGB")
        if t < 2.3:
            d = ImageDraw.Draw(img, "RGBA")
            alpha = 1.0 if t < 1.9 else max(0.0, (2.3 - t) / 0.4)
            text = "Built from one prompt. Zero edits."
            tw = d.textlength(text, font=overlay_f)
            x0, y0 = (W - tw) / 2 - 26, H - 118
            d.rounded_rectangle((x0, y0, x0 + tw + 52, y0 + 62), radius=14,
                                fill=(5, 6, 15, int(190 * alpha)))
            d.text(((W - tw) / 2, y0 + 12), text, font=overlay_f,
                   fill=(255, 255, 255, int(255 * alpha)))
        frames.append(img)
    return frames


# ---------------------------------------------------------------- segment D
def segment_d(card_dir, last_game_frame):
    bg = last_game_frame.copy()
    bg = ImageEnhance.Color(bg).enhance(0.35)
    bg = bg.filter(ImageFilter.GaussianBlur(19))
    card_frames = []
    i = 1
    while os.path.exists(os.path.join(card_dir, f"{i:03d}.png")):
        card_frames.append(Image.open(os.path.join(card_dir, f"{i:03d}.png")).convert("RGBA"))
        i += 1
    held = card_frames[-1]
    code_f = ImageFont.truetype(JB_MONO_BOLD, 41)
    frames = []
    TYPE_START, TYPE_STEP = 1.55, 0.085
    for k in range(5 * FPS):
        t = k / FPS
        img = bg.copy().convert("RGBA")
        card = card_frames[min(int(t * FPS), len(card_frames) - 1)] if t < 2.5 else held
        img.alpha_composite(card, (0, 0))
        shown = int((t - TYPE_START) / TYPE_STEP) if t >= TYPE_START else 0
        shown = max(0, min(len(REFERRAL_CODE), shown))
        if shown > 0:
            d = ImageDraw.Draw(img)
            # cover the card's blinking caret (press guide), then the code
            d.rectangle((287, 461, 293, 515), fill=(255, 255, 255))
            d.text((288, 489), REFERRAL_CODE[:shown], font=code_f,
                   fill=(25, 20, 25), anchor="lm")
        frames.append(img.convert("RGB"))
    return frames


def main():
    card_dir = get_assets()
    save_frames(segment_a(), "framesA")
    save_frames(segment_b(), "framesB")
    c_frames = segment_c()
    save_frames(c_frames, "framesC")
    save_frames(segment_d(card_dir, c_frames[-1]), "framesD")
    print("all segments rendered")


if __name__ == "__main__":
    main()
