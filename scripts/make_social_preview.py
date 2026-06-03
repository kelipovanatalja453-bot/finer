"""Compose the GitHub social-preview card (1280x640) for Finer OS.

On-brand with the product: warm paper background, Morningstar red accent,
a real product screenshot framed on the right. Rendered at 2x then downsampled
for crisp anti-aliasing. Output: docs/assets/finer-social-preview.png
"""
from PIL import Image, ImageDraw, ImageFont

S = 2  # supersample factor
W, H = 1280 * S, 640 * S

# palette (from the dashboard / landing theme)
PAPER = (243, 239, 231)
INK = (26, 24, 22)
INK_SOFT = (110, 104, 92)
RED = (225, 27, 34)
BORDER = (214, 208, 192)
CARD = (255, 255, 255)
HEADER_BG = (247, 244, 237)

HIRAGINO = "/System/Library/Fonts/Hiragino Sans GB.ttc"
ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"


def cjk(size, bold=True):
    return ImageFont.truetype(HIRAGINO, size * S, index=2 if bold else 0)


def latin(size, bold=True):
    return ImageFont.truetype(ARIAL_BOLD if bold else ARIAL, size * S)


img = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(img)

# ---- Right: product screenshot in a browser-like frame ----
shot = Image.open("src/finer_dashboard/public/landing/research.png").convert("RGB")
card_w = 560 * S
scale = card_w / shot.width
shot_h = int(shot.height * scale)
shot = shot.resize((card_w, shot_h), Image.LANCZOS)

bar_h = 30 * S
crop_h = 430 * S  # show top portion (header + scores + curve)
shot_crop = shot.crop((0, 0, card_w, min(crop_h, shot_h)))
card_h = bar_h + shot_crop.height
cx = W - card_w - 70 * S
cy = (H - card_h) // 2

# soft shadow
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.rounded_rectangle([cx + 6 * S, cy + 10 * S, cx + card_w + 6 * S, cy + card_h + 10 * S],
                     radius=10 * S, fill=(20, 18, 14, 40))
img.paste(Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB"), (0, 0))
d = ImageDraw.Draw(img)

# card body + header bar
d.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=10 * S, fill=CARD, outline=BORDER, width=1 * S)
d.rectangle([cx + 1 * S, cy + 1 * S, cx + card_w - 1 * S, cy + bar_h], fill=HEADER_BG)
for i, col in enumerate([(232, 120, 120), (232, 196, 120), (150, 200, 150)]):
    d.ellipse([cx + (16 + i * 16) * S, cy + 11 * S, cx + (24 + i * 16) * S, cy + 19 * S], fill=col)
d.text((cx + 78 * S, cy + 8 * S), "finer.os / research", font=latin(11, bold=False), fill=INK_SOFT)
img.paste(shot_crop, (cx, cy + bar_h))
# header divider + crop fade line
d.line([cx, cy + bar_h, cx + card_w, cy + bar_h], fill=BORDER, width=1 * S)

# ---- Left: brand + headline ----
x = 80 * S
# logo square + activity pulse
ls = 46 * S
ly = 70 * S
d.rounded_rectangle([x, ly, x + ls, ly + ls], radius=8 * S, fill=RED)
pts = [(0.16, 0.54), (0.34, 0.54), (0.45, 0.30), (0.56, 0.74), (0.66, 0.54), (0.84, 0.54)]
d.line([(x + px * ls, ly + py * ls) for px, py in pts], fill=(255, 255, 255), width=3 * S, joint="curve")
d.text((x + ls + 16 * S, ly + 6 * S), "Finer OS", font=latin(28), fill=INK)

# eyebrow
ey = ly + ls + 30 * S
d.text((x, ey), "AI-NATIVE 投研自动化流水线", font=cjk(15), fill=RED)

# headline (3 lines)
hy = ey + 36 * S
lh = 56 * S
hf = cjk(38)
for i, line in enumerate(["把财经 KOL 的内容，", "变成可回测、可审计的", "投资事件。"]):
    d.text((x - 2 * S, hy + i * lh), line, font=hf, fill=INK)

# red rule
ry = hy + 3 * lh + 18 * S
d.rectangle([x, ry, x + 56 * S, ry + 4 * S], fill=RED)

# pipeline strip
py = ry + 26 * S
d.text((x, py), "F0 → F1 → F2 → F3 → F4 → F5 → F6 → F7 → F8", font=latin(15, bold=True), fill=INK_SOFT)

# bottom tagline (en)
ty = H - 78 * S
d.text((x, ty), "From noisy KOL timelines to auditable investment intelligence.",
       font=latin(14, bold=False), fill=INK_SOFT)

out = img.resize((1280, 640), Image.LANCZOS)
out.save("docs/assets/finer-social-preview.png")
print("wrote docs/assets/finer-social-preview.png", out.size)
