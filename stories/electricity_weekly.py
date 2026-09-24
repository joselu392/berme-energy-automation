#!/usr/bin/env python3
import csv
import io
import json
import math
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

OMIE_DOWNLOAD = "https://www.omie.es/es/file-download"
HIST_MAX_MWH = 544.98
HIST_MAX_DATE = "8 mar 2022"

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)
OUT_IMG = DOCS / "story-weekly-electricity.jpg"
OUT_JSON = DOCS / "story-weekly-electricity.json"

def completed_week():
    ref = os.getenv("BERME_REFERENCE_DATE")
    today = date.fromisoformat(ref) if ref else datetime.now(ZoneInfo("Europe/Madrid")).date()
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(days=7)
    end = this_monday - timedelta(days=1)
    return start, end

def fetch_day(d):
    filename = f"marginalpdbc_{d:%Y%m%d}.1"
    r = requests.get(
        OMIE_DOWNLOAD,
        params={"parents": "marginalpdbc", "filename": filename},
        timeout=30,
        headers={"User-Agent": "BermeEnergyAutomation/1.0"}
    )
    r.raise_for_status()
    text = r.content.decode("latin-1", errors="replace")
    prices = []
    reader = csv.reader(io.StringIO(text), delimiter=";")
    for row in reader:
        row = [c.strip() for c in row]
        if len(row) < 6:
            continue
        try:
            y = int(row[0]); m = int(row[1]); day = int(row[2])
            period = int(row[3])
            price_spain = float(row[5].replace(",", "."))
        except Exception:
            continue
        if (y, m, day) == (d.year, d.month, d.day) and 1 <= period <= 100:
            prices.append(price_spain)
    if not prices:
        raise RuntimeError(f"No se pudieron leer precios OMIE para {d} ({filename})")
    return prices

def fmt_num(x, decimals=3):
    return f"{x:.{decimals}f}".replace(".", ",")

def load_week():
    start, end = completed_week()
    days = []
    cur = start
    while cur <= end:
        prices = fetch_day(cur)
        days.append({
            "date": cur.isoformat(),
            "mean_mwh": sum(prices) / len(prices),
            "periods": len(prices)
        })
        cur += timedelta(days=1)

    daily_means = [x["mean_mwh"] for x in days]
    weekly_mwh = sum(daily_means) / len(daily_means)
    min_daily = min(days, key=lambda x: x["mean_mwh"])
    max_daily = max(days, key=lambda x: x["mean_mwh"])
    pct_vs_hist = (weekly_mwh / HIST_MAX_MWH - 1.0) * 100.0

    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "weekly_mean_mwh": weekly_mwh,
        "weekly_mean_kwh": weekly_mwh / 1000,
        "min_daily_mwh": min_daily["mean_mwh"],
        "max_daily_mwh": max_daily["mean_mwh"],
        "historical_max_mwh": HIST_MAX_MWH,
        "historical_max_date": HIST_MAX_DATE,
        "pct_vs_historical": pct_vs_hist,
        "daily": days,
        "source": "OMIE - precios del mercado diario en España"
    }

def font(size, bold=False, italic=False):
    candidates = []
    if bold and italic:
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"]
    elif bold:
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    elif italic:
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"]
    else:
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    return ImageFont.truetype(candidates[0], size)

def draw_bulb(img, cx, cy, scale=1.0):
    d = ImageDraw.Draw(img, "RGBA")
    r = int(128*scale)
    # soft glow
    for i in range(10, 0, -1):
        rr = r + i*10
        a = int(5 + (10-i)*1.7)
        d.ellipse((cx-rr, cy-rr, cx+rr, cy+rr), fill=(238, 208, 137, a))
    # glass
    d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(255, 244, 214, 115), outline=(213,184,125,190), width=max(2,int(3*scale)))
    # filament
    y0 = cy-25
    d.arc((cx-44*scale, y0-28*scale, cx+44*scale, y0+48*scale), 10, 170, fill=(206,139,35,255), width=max(2,int(5*scale)))
    d.line((cx-30*scale, y0+20*scale, cx-22*scale, cy+74*scale), fill=(206,139,35,255), width=max(2,int(4*scale)))
    d.line((cx+30*scale, y0+20*scale, cx+22*scale, cy+74*scale), fill=(206,139,35,255), width=max(2,int(4*scale)))
    # base
    base_y = cy+r-12
    d.rounded_rectangle((cx-62*scale, base_y, cx+62*scale, base_y+56*scale), radius=10*scale, fill=(151,119,67,255))
    for k in range(4):
        yy=base_y+8+k*12*scale
        d.line((cx-57*scale, yy, cx+57*scale, yy), fill=(86,72,52,255), width=max(2,int(3*scale)))
    d.polygon([(cx-35*scale,base_y+56*scale),(cx+35*scale,base_y+56*scale),(cx+20*scale,base_y+78*scale),(cx-20*scale,base_y+78*scale)], fill=(70,61,47,255))

def render(data):
    W,H = 1080,1920
    BG=(247,244,237)
    INK=(15,15,15)
    MUTED=(86,83,78)
    GREEN=(10,126,46)
    OLIVE=(101,113,79)
    LIGHT=(244,242,236)
    CARD=(253,251,247)
    img=Image.new("RGB",(W,H),BG)
    d=ImageDraw.Draw(img)

    # decorative shapes
    d.ellipse((760,-120,1190,310), fill=(235,240,226))
    d.ellipse((-180,1530,330,2040), fill=(232,238,224))
    draw_bulb(img, 850, 375, 0.92)

    # TOP SAFE AREA: first 205 px intentionally empty
    start=date.fromisoformat(data["week_start"])
    end=date.fromisoformat(data["week_end"])
    months=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    week_text=f"SEMANA DEL\n{start.day} AL {end.day} {months[end.month-1].upper()} {end.year}"
    d.multiline_text((930,210), week_text, font=font(24), fill=INK, anchor="ra", align="right", spacing=7)

    d.text((75,315),"Precio medio",font=font(65,bold=True),fill=INK)
    d.text((75,392),"de la",font=font(65,bold=True),fill=INK)
    d.text((270,392),"luz",font=font(65,bold=True),fill=GREEN)
    d.text((77,478),"€/kWh (mercado mayorista)",font=font(31),fill=INK)

    # main card
    d.rounded_rectangle((60,565,1020,1265), radius=32, fill=CARD)
    d.text((105,605),"Esta semana",font=font(31),fill=INK)

    wk=data["weekly_mean_kwh"]
    d.text((100,660),fmt_num(wk,3),font=font(112,bold=True),fill=INK)
    d.text((455,732),"€/kWh",font=font(39),fill=INK)
    d.text((105,780),f'{fmt_num(data["weekly_mean_mwh"],2)} €/MWh',font=font(32),fill=MUTED)

    pct=round(data["pct_vs_historical"])
    badge=(650,640,985,790)
    d.rounded_rectangle(badge, radius=24, fill=(232,242,228))
    arrow="↓" if pct < 0 else "↑"
    d.text((685,665),f"{arrow} {pct:+d}%",font=font(49,bold=True),fill=GREEN)
    d.text((690,728),"vs. máximo histórico",font=font(21),fill=INK)

    # weekly line chart: daily means
    chart=(120,875,950,1055)
    x0,y0,x1,y1=chart
    vals=[x["mean_mwh"]/1000 for x in data["daily"]]
    vmin=min(vals); vmax=max(vals)
    low=max(0, vmin-(vmax-vmin)*0.30)
    high=vmax+(vmax-vmin)*0.30 if vmax>vmin else vmax+0.03
    if high-low < 0.04: high=low+0.04
    for i in range(4):
        yy=y1-i*(y1-y0)/3
        d.line((x0,yy,x1,yy),fill=(220,216,208),width=2)
    pts=[]
    for i,v in enumerate(vals):
        x=x0+i*(x1-x0)/6
        y=y1-(v-low)/(high-low)*(y1-y0)
        pts.append((x,y))
    d.line(pts,fill=GREEN,width=6,joint="curve")
    for x,y in pts:
        d.ellipse((x-6,y-6,x+6,y+6),fill=GREEN)
    labels=["L","M","X","J","V","S","D"]
    for i,l in enumerate(labels):
        x=x0+i*(x1-x0)/6
        d.text((x,1070),l,font=font(22),fill=MUTED,anchor="ma")
    d.text((105,835),"Media diaria de la semana",font=font(27,bold=True),fill=INK)

    # metrics
    d.rounded_rectangle((95,1125,985,1235), radius=24, fill=LIGHT)
    items=[
      ("Mínimo",data["min_daily_mwh"]/1000),
      ("Máximo",data["max_daily_mwh"]/1000),
      ("Máximo histórico",data["historical_max_mwh"]/1000),
    ]
    xs=[205,505,805]
    for i,(lab,val) in enumerate(items):
        d.text((xs[i],1147),lab,font=font(22,bold=(i==2)),fill=INK,anchor="ma")
        d.text((xs[i],1183),fmt_num(val,3),font=font(40,bold=True),fill=INK,anchor="ma")
        d.text((xs[i],1221),"€/kWh",font=font(19),fill=INK,anchor="ma")
    d.text((805,1240),data["historical_max_date"],font=font(18),fill=MUTED,anchor="ma")

    # source
    d.text((95,1305),"Fuente: OMIE. Precio medio diario del mercado mayorista.",font=font(21),fill=MUTED)
    d.text((95,1338),"No equivale al precio final de tu factura.",font=font(21),fill=MUTED)

    # CTA, deliberately higher
    d.rounded_rectangle((70,1400,1010,1515), radius=28, fill=(94,109,70))
    d.text((540,1430),"Si quieres revisar tu factura, escríbenos.",font=font(27,bold=True),fill="white",anchor="ma")
    d.text((540,1474),"Te ayudamos gratuitamente.",font=font(24),fill="white",anchor="ma")

    # tagline; everything ends before y=1600
    d.line((80,1555,150,1555),fill=GREEN,width=4)
    d.text((80,1572),"Ahorra con",font=font(28),fill=INK)
    d.text((80,1607),"Berme Energy.",font=font(30,italic=True),fill=GREEN)

    # bottom 280+ px intentionally blank for Instagram reply bar / controls
    img.save(OUT_IMG,"JPEG",quality=93,optimize=True,progressive=True)

def main():
    data=load_week()
    OUT_JSON.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    render(data)
    print(json.dumps({
        "week": [data["week_start"],data["week_end"]],
        "weekly_mean_mwh": round(data["weekly_mean_mwh"],2),
        "weekly_mean_kwh": round(data["weekly_mean_kwh"],5),
        "image": str(OUT_IMG)
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
