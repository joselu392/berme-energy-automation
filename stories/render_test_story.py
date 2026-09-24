from PIL import Image, ImageDraw, ImageFont
import math
from pathlib import Path

W, H = 1080, 1920
BG = "#F5F1E9"
INK = "#111111"
MUTED = "#55534F"
GREEN = "#0B7A2A"
OLIVE = "#69705B"
PALE_GREEN = "#E8F2E4"
CARD = "#FBF9F4"
LINE = "#D8D2C7"

OUT = Path("docs/story-test-luz.jpg")
OUT.parent.mkdir(parents=True, exist_ok=True)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

def font(size, bold=False, italic=False):
    if bold and italic:
        p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"
    elif bold:
        p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    elif italic:
        p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"
    else:
        p = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p, size)

def rr(xy, r=28, fill=CARD, outline=None, width=1):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

# Soft decorative blobs
d.ellipse((820, -170, 1240, 250), fill="#ECEFE4")
d.ellipse((-180, 1680, 320, 2180), fill="#E9EDE2")

# Logo bulb icon
cx, cy = 82, 92
d.ellipse((cx-29, cy-28, cx+29, cy+30), outline=INK, width=4)
d.line((cx-11, cy+31, cx+11, cy+31), fill=INK, width=4)
d.line((cx-13, cy+39, cx+13, cy+39), fill=INK, width=4)
d.line((cx-9, cy+47, cx+9, cy+47), fill=INK, width=4)
d.line((cx, cy+28, cx, cy+1), fill=INK, width=3)
d.arc((cx-11, cy-8, cx+3, cy+12), 200, 20, fill=INK, width=3)
for a in range(0, 360, 45):
    if a in (90,270):
        continue
    rad=math.radians(a)
    x1=cx+39*math.cos(rad); y1=cy-3+39*math.sin(rad)
    x2=cx+50*math.cos(rad); y2=cy-3+50*math.sin(rad)
    d.line((x1,y1,x2,y2), fill=INK, width=3)

# Wordmark
d.text((132, 60), "Berme", font=font(42, bold=True), fill=INK)
d.text((275, 60), "Energy", font=font(42, italic=True), fill=INK)
d.text((748, 66), "HOY · 24 SEP 2026", font=font(24), fill=INK)

# Decorative large bulb, upper right
d.ellipse((720, 120, 1050, 460), fill="#FBF1D8", outline="#E1CFAC", width=3)
d.ellipse((744, 145, 1026, 428), outline="#FFF8E9", width=14)
d.line((842, 255, 842, 385), fill="#C58D24", width=6)
d.line((908, 255, 908, 385), fill="#C58D24", width=6)
d.arc((842, 224, 908, 300), 0, 180, fill="#C58D24", width=5)
d.rectangle((820, 430, 930, 455), fill="#A7834A")
d.rectangle((827, 458, 923, 475), fill="#6F6047")

# Heading
d.text((54, 235), "Precio medio", font=font(63, bold=True), fill=INK)
d.text((54, 310), "de la", font=font(63, bold=True), fill=INK)
d.text((245, 310), "luz", font=font(63, bold=True), fill=GREEN)
d.text((54, 395), "€/kWh (mercado mayorista)", font=font(31), fill=INK)

# Main card
rr((48, 515, 1032, 1420), r=32, fill="#FCFAF6")
d.text((83, 555), "Hoy · 24 SEP 2026", font=font(31), fill=INK)

# Current price
d.text((80, 625), "0,157", font=font(118, bold=True), fill=INK)
d.text((462, 704), "€/kWh", font=font(44), fill=INK)
d.text((84, 765), "157,24 €/MWh", font=font(34), fill=MUTED)

# % badge
rr((655, 625, 995, 785), r=24, fill=PALE_GREEN)
d.text((700, 650), "↓ -71%", font=font(50, bold=True), fill=GREEN)
d.text((708, 717), "vs. máximo histórico", font=font(22), fill=INK)

# Daily min / mean / max chart
chart_y0, chart_y1 = 910, 1165
d.text((83, 845), "Rango de hoy", font=font(31, bold=True), fill=INK)
for i in range(5):
    y = chart_y1 - i*(chart_y1-chart_y0)/4
    d.line((105, y, 970, y), fill="#E2DDD4", width=2)

vals = [("Mínimo", 0.01762), ("Media", 0.15724), ("Máximo", 0.28823)]
max_scale = 0.32
bar_w = 145
xs = [240, 500, 760]
for (label, v), x in zip(vals, xs):
    h = (v/max_scale)*(chart_y1-chart_y0)
    top = chart_y1-h
    col = GREEN if label == "Media" else OLIVE
    d.rounded_rectangle((x, top, x+bar_w, chart_y1), radius=18, fill=col)
    d.text((x+bar_w/2, chart_y1+18), label, font=font(23), fill=INK, anchor="ma")
    d.text((x+bar_w/2, top-16), f"{v:.3f}".replace(".", ","), font=font(27, bold=True), fill=INK, anchor="ms")

# Historic max panel
rr((80, 1235, 1000, 1385), r=25, fill="#F2EFE8")
d.text((110, 1265), "Máximo histórico", font=font(31, bold=True), fill=INK)
d.text((110, 1312), "0,545", font=font(64, bold=True), fill=INK)
d.text((320, 1335), "€/kWh", font=font(29), fill=INK)
d.text((770, 1332), "8 mar 2022", font=font(27), fill=INK)

# Source
d.ellipse((65, 1466, 103, 1504), outline=INK, width=3)
d.text((84, 1467), "i", font=font(25, bold=True), fill=INK, anchor="ma")
d.text((125, 1455), "Fuente: OMIE. Mercado diario España · 24/09/2026.", font=font(23), fill=MUTED)
d.text((125, 1492), "Precio mayorista; no equivale al precio final de tu factura.", font=font(22), fill=MUTED)

# CTA
rr((65, 1572, 1015, 1745), r=28, fill="#66724D")
d.text((108, 1605), "Si necesitas ayuda con tu factura,", font=font(29), fill="white")
d.text((108, 1651), "escríbenos.", font=font(39, bold=True), fill="white")
d.text((360, 1657), "Te ayudamos gratuitamente.", font=font(25), fill="white")

# Footer
d.line((65, 1810, 132, 1810), fill=GREEN, width=4)
d.text((65, 1830), "Ahorra con", font=font(34), fill=INK)
d.text((65, 1872), "Berme Energy.", font=font(36, italic=True), fill=GREEN)

img.save(OUT, "JPEG", quality=92, optimize=True, progressive=True)
print(f"Rendered {OUT} ({W}x{H})")
