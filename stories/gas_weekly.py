#!/usr/bin/env python3
import json, os, re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"; DOCS.mkdir(exist_ok=True)
OUT_IMG=DOCS/"story-weekly-gas.jpg"
OUT_JSON=DOCS/"story-weekly-gas.json"
MIBGAS_URL="https://www.mibgas.es/es/market-results"
HIST_MAX_MWH=240.0
HIST_MAX_DATE="29 ago 2022"

def completed_week():
    ref=os.getenv("BERME_REFERENCE_DATE")
    today=date.fromisoformat(ref) if ref else datetime.now(ZoneInfo("Europe/Madrid")).date()
    mon=today-timedelta(days=today.weekday())
    return mon-timedelta(days=7), mon-timedelta(days=1)

def get_page(qdate):
    r=requests.get(MIBGAS_URL,params={"date":qdate.isoformat()},timeout=30,
                   headers={"User-Agent":"BermeEnergyAutomation/1.0"})
    r.raise_for_status()
    txt=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",r.text))
    return txt.replace("&nbsp;"," ")

def daily_price(target):
    needle=target.strftime("%d/%m")
    for back in range(1,8):
        q=target-timedelta(days=back)
        txt=get_page(q)
        m=re.search(r"Diario\s+(.*?)(?:Fin de semana|Resto de mes|Mes\s)",txt,re.I)
        if not m:
            continue
        block=m.group(1)
        pairs=re.findall(r"(\d{2}/\d{2})\s+(-?\d{1,3}(?:[.,]\d+)?)",block)
        for ddmm,raw in pairs:
            if ddmm==needle:
                return float(raw.replace(".","").replace(",","."))
    raise RuntimeError(f"No se encontró precio MIBGAS Diario para {target}")

def fnum(x,n=3): return f"{x:.{n}f}".replace(".",",")

def build():
    start,end=completed_week()
    daily=[]
    d=start
    while d<=end:
        p=daily_price(d)
        daily.append({"date":d.isoformat(),"price_mwh":p})
        d+=timedelta(days=1)
    vals=[x["price_mwh"] for x in daily]
    avg=sum(vals)/len(vals)
    return {
        "week_start":start.isoformat(),"week_end":end.isoformat(),
        "weekly_mean_mwh":avg,"weekly_mean_kwh":avg/1000,
        "min_mwh":min(vals),"max_mwh":max(vals),
        "historical_max_mwh":HIST_MAX_MWH,"historical_max_date":HIST_MAX_DATE,
        "pct_vs_historical":(avg/HIST_MAX_MWH-1)*100,
        "daily":daily,
        "source":"MIBGAS PVB - producto Diario (D+1)"
    }

def font(size,bold=False,italic=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans"
    p+=("-BoldOblique.ttf" if bold and italic else "-Bold.ttf" if bold else "-Oblique.ttf" if italic else ".ttf")
    return ImageFont.truetype(p,size)

def draw_burner(img):
    d=ImageDraw.Draw(img,"RGBA")
    cx,cy=850,350
    for r,a in [(145,18),(125,25),(105,35)]:
        d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(70,130,255,a))
    d.ellipse((705,325,995,500),fill=(20,28,36,255))
    d.ellipse((735,340,965,455),fill=(7,8,10,255),outline=(115,130,145,255),width=5)
    for i in range(9):
        x=755+i*24
        pts=[(x,370),(x-10,315),(x,275),(x+12,315)]
        d.polygon(pts,fill=(30,120,255,220))
        d.polygon([(x,362),(x-5,325),(x,300),(x+6,326)],fill=(110,205,255,220))

def render(data):
    W,H=1080,1920; BG=(247,244,237); INK=(15,15,15); MUTED=(83,82,79)
    GREEN=(10,126,46); CARD=(253,251,247); LIGHT=(244,242,236)
    img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    d.ellipse((760,-140,1190,290),fill=(235,240,226))
    draw_burner(img)
    s=date.fromisoformat(data["week_start"]); e=date.fromisoformat(data["week_end"])
    months=["ENE","FEB","MAR","ABR","MAY","JUN","JUL","AGO","SEP","OCT","NOV","DIC"]
    d.multiline_text((930,210),f"SEMANA DEL\n{s.day} AL {e.day} {months[e.month-1]} {e.year}",
                     font=font(24),fill=INK,anchor="ra",align="right",spacing=7)
    d.text((75,315),"Precio medio",font=font(65,True),fill=INK)
    d.text((75,392),"del",font=font(65,True),fill=INK)
    d.text((205,392),"gas",font=font(65,True),fill=GREEN)
    d.text((77,478),"€/kWh (mercado mayorista)",font=font(31),fill=INK)
    d.rounded_rectangle((60,565,1020,1265),radius=32,fill=CARD)
    d.text((105,605),"Esta semana",font=font(31),fill=INK)
    avg=data["weekly_mean_kwh"]
    d.text((100,660),fnum(avg,3),font=font(112,True),fill=INK)
    d.text((455,732),"€/kWh",font=font(39),fill=INK)
    d.text((105,780),f'{fnum(data["weekly_mean_mwh"],2)} €/MWh',font=font(32),fill=MUTED)
    pct=round(data["pct_vs_historical"])
    d.rounded_rectangle((650,640,985,790),radius=24,fill=(232,242,228))
    d.text((690,665),f'{"↓" if pct<0 else "↑"} {pct:+d}%',font=font(48,True),fill=GREEN)
    d.text((690,728),"vs. máximo histórico",font=font(21),fill=INK)
    d.text((105,835),"Media diaria de la semana",font=font(27,True),fill=INK)
    x0,y0,x1,y1=120,875,950,1055
    vals=[x["price_mwh"]/1000 for x in data["daily"]]
    lo=min(vals); hi=max(vals); pad=max((hi-lo)*.35,.003); lo=max(0,lo-pad); hi=hi+pad
    for i in range(4):
        yy=y1-i*(y1-y0)/3; d.line((x0,yy,x1,yy),fill=(220,216,208),width=2)
    pts=[]
    for i,v in enumerate(vals):
        x=x0+i*(x1-x0)/6; y=y1-(v-lo)/(hi-lo)*(y1-y0); pts.append((x,y))
    d.line(pts,fill=GREEN,width=6,joint="curve")
    for x,y in pts: d.ellipse((x-6,y-6,x+6,y+6),fill=GREEN)
    for i,l in enumerate(["L","M","X","J","V","S","D"]):
        x=x0+i*(x1-x0)/6; d.text((x,1070),l,font=font(22),fill=MUTED,anchor="ma")
    d.rounded_rectangle((95,1125,985,1235),radius=24,fill=LIGHT)
    metrics=[("Mínimo",data["min_mwh"]/1000),("Máximo",data["max_mwh"]/1000),("Máximo histórico",data["historical_max_mwh"]/1000)]
    for i,(lab,val) in enumerate(metrics):
        x=[205,505,805][i]
        d.text((x,1147),lab,font=font(22,i==2),fill=INK,anchor="ma")
        d.text((x,1183),fnum(val,3),font=font(40,True),fill=INK,anchor="ma")
        d.text((x,1221),"€/kWh",font=font(19),fill=INK,anchor="ma")
    d.text((805,1240),data["historical_max_date"],font=font(18),fill=MUTED,anchor="ma")
    d.text((95,1305),"Fuente: MIBGAS PVB. Precio diario del mercado mayorista.",font=font(21),fill=MUTED)
    d.text((95,1338),"No equivale al precio final de tu factura.",font=font(21),fill=MUTED)
    d.rounded_rectangle((70,1400,1010,1515),radius=28,fill=(94,109,70))
    d.text((540,1430),"Si quieres revisar tu factura, escríbenos.",font=font(27,True),fill="white",anchor="ma")
    d.text((540,1474),"Te ayudamos gratuitamente.",font=font(24),fill="white",anchor="ma")
    d.line((80,1555,150,1555),fill=GREEN,width=4)
    d.text((80,1572),"Ahorra con",font=font(28),fill=INK)
    d.text((80,1607),"Berme Energy.",font=font(30,italic=True),fill=GREEN)
    img.save(OUT_IMG,"JPEG",quality=93,optimize=True,progressive=True)

def main():
    data=build(); OUT_JSON.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); render(data)
    print(json.dumps({"week":[data["week_start"],data["week_end"]],"avg_mwh":round(data["weekly_mean_mwh"],2),"image":str(OUT_IMG)},ensure_ascii=False))

if __name__=="__main__": main()
