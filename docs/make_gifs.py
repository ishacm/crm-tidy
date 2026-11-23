"""Regenerate the README / Pages animation (original artwork).  python docs/make_gifs.py -> docs/sweep.gif/.webp"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BG, PANEL, LINE = (12, 13, 14), (24, 26, 28), (45, 48, 51)
INK, MUTED, ORANGE, GREEN, RED, YELLOW = (236, 231, 221), (150, 145, 136), (240, 138, 75), (140, 203, 143), (242, 120, 105), (232, 196, 110)
W, H = 760, 360
f = lambda p, s: ImageFont.truetype(p, s)

# (messy, clean, score, tier, note)
ROWS = [
    ("ANNA SCHMIDT   CFO     anna@ACME.example", "Anna Schmidt   CFO     anna@acme.example", 100, "A", ""),
    ("anna schmidt           anna@acme.example ", None, None, None, "duplicate → merged"),
    ("jane DOE       cfo     jane.doe@         ", "Jane Doe       CFO     jane.doe@  ", None, None, "broken email → needs a human"),
    ("ORBIT DEVTOOLS  Sr Accountant  lucas@... ", "Orbit Devtools  Senior Accountant  ", 85, "A", ""),
    ("Tom Becker   Working Student   tom@gmail", "Tom Becker   Working Student   ", 20, "D", ""),
    ("priya nair   founder & ceo   priya@rb.ex", "Priya Nair   Founder & CEO   ", 62, "B", ""),
]
TIER_COL = {"A": GREEN, "B": YELLOW, "C": ORANGE, "D": MUTED}


def broom(d, x, y):
    d.line([x + 40, y - 70, x + 10, y + 10], fill=(170, 120, 80), width=7)       # handle
    d.polygon([(x - 18, y + 8), (x + 34, y + 8), (x + 44, y + 44), (x - 30, y + 44)], fill=ORANGE)
    for k in range(-24, 42, 8):
        d.line([x + k, y + 44, x + k - 4, y + 54], fill=ORANGE, width=3)
    for k in range(3):  # dust
        d.ellipse([x - 44 - k * 14, y + 40 - k * 6, x - 38 - k * 14, y + 46 - k * 6], fill=LINE)


def frame(i, n):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((28, 20), "crm-tidy", font=f(BOLD, 26), fill=INK)
    d.text((158, 28), "a messy CRM in, a scored one out", font=f(SANS, 16), fill=MUTED)
    sweep_x = -60 + (i / (n * 0.62)) * (W + 120)
    top = 74
    for k, (messy, clean, score, tier, note) in enumerate(ROWS):
        y = top + k * 40
        d.rounded_rectangle([24, y, W - 24, y + 32], 6, fill=PANEL)
        done = sweep_x > 600
        if sweep_x < 40:
            d.text((36, y + 8), messy, font=f(MONO, 14), fill=MUTED)
            continue
        if clean is None:  # duplicate collapses once the broom has passed it
            if sweep_x < 420:
                d.text((36, y + 8), messy, font=f(MONO, 14), fill=MUTED)
            else:
                d.text((36, y + 8), "↳ " + note, font=f(MONO, 14), fill=ORANGE)
            continue
        cut = int(min(len(messy), max(0, (sweep_x - 36) / 8.4)))
        shown = clean[:cut] + messy[cut:] if cut < len(clean) else clean
        d.text((36, y + 8), shown, font=f(MONO, 14), fill=INK)
        if note and done:
            d.text((W - 300, y + 8), note, font=f(MONO, 13), fill=RED)
        if score is not None and i > n * 0.66 + k:
            col = TIER_COL[tier]
            d.rounded_rectangle([W - 150, y + 5, W - 34, y + 27], 11, outline=col, width=2)
            d.text((W - 140, y + 8), f"{score:>3}/100  {tier}", font=f(MONO, 13), fill=col)
    if -60 < sweep_x < W + 40:
        broom(d, int(sweep_x), 300)
    if i > n * 0.8:
        d.text((28, H - 34), "60 rows → 55 records · 5 duplicates merged · every score explains itself",
               font=f(MONO, 13), fill=GREEN)
    return im


def main():
    n = 64
    frames = [frame(i, n) for i in range(n)]
    dur = [70] * n
    dur[-1] = 3000
    q = [fr.quantize(colors=40, method=Image.Quantize.MEDIANCUT) for fr in frames]
    q[0].save(OUT / "sweep.gif", save_all=True, append_images=q[1:], duration=dur, loop=0, optimize=True)
    frames[0].save(OUT / "sweep.webp", save_all=True, append_images=frames[1:], duration=dur, loop=0, quality=65, method=6)
    for p in ("sweep.gif", "sweep.webp"):
        print(p, (OUT / p).stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
