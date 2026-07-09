"""Generate the FigForge app icon: a white figure-layout card (no backdrop).

Run:  py scripts/make_icon.py
Outputs figforge/resources/icon.ico (+ icon.png preview).
"""
import os

from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "figforge", "resources")
os.makedirs(OUT, exist_ok=True)

S = 1024
RED, GREEN, AMBER = (236, 93, 87), (52, 178, 123), (243, 180, 58)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

# ---- soft shadow so the white card shows on any background ----------------
m = int(S * 0.06)
card = [m, m, S - m, S - m]
pr = int(S * 0.16)
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle(
    [card[0], card[1] + int(S * 0.012), card[2], card[3] + int(S * 0.024)],
    radius=pr, fill=(55, 65, 90, 105))
shadow = shadow.filter(ImageFilter.GaussianBlur(int(S * 0.02)))
img = Image.alpha_composite(img, shadow)
draw = ImageDraw.Draw(img)

# ---- white card (the figure page / frame) with a hairline border ----------
draw.rounded_rectangle(card, radius=pr, fill=(255, 255, 255, 255),
                       outline=(205, 210, 219, 255), width=max(2, int(S * 0.006)))

# ---- panels (asymmetric: tall A, B over C) -------------------------------
cp, g = int(S * 0.085), int(S * 0.05)
cx0, cy0, cx1, cy1 = card[0] + cp, card[1] + cp, card[2] - cp, card[3] - cp
cw, ch = cx1 - cx0, cy1 - cy0
wA = int(cw * 0.46)
bx0 = cx0 + wA + g
hB = (ch - g) // 2
prr = int(S * 0.024)
ax = [cx0, cy0, cx0 + wA, cy1]
draw.rounded_rectangle(ax, radius=prr, fill=RED)
draw.rounded_rectangle([bx0, cy0, cx1, cy0 + hB], radius=prr, fill=GREEN)
draw.rounded_rectangle([bx0, cy0 + hB + g, cx1, cy1], radius=prr, fill=AMBER)

# ---- save ----------------------------------------------------------------
base = img.resize((256, 256), Image.LANCZOS)
base.save(os.path.join(OUT, "icon.png"))
base.save(os.path.join(OUT, "icon.ico"),
          format="ICO",
          sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                 (64, 64), (128, 128), (256, 256)])
print("wrote:", OUT)
