#!/usr/bin/env python3
import csv, io, json, os, xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"; DOCS.mkdir(exist_ok=True)
OUT_IMG=DOCS/"story-weekly-brent.jpg"
OUT_JSON=DOCS/"story-weekly-brent.json"
FRED="https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"
ECB="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"

def completed_week():
    ref=os.getenv("BERME_REFERENCE_DATE")
    today=date.fromisoformat(ref) if ref else datetime.now(ZoneInfo("Europe/Madrid")).date()
    mon=today-timedelta(days=today.weekday())
    return mon-timedelta(days=7), mon-timedelta(days=1)

def fred():
    r=requests.get(FRED,timeout=30,headers={"User-Agent":"BermeEnergyAutomation/1.0"}); r.raise_for_status()
    rows={}
    for x in csv.DictReader(io.StringIO(r.text)):
        raw=x.get("DCOILBRENTEU","")
        if raw and raw not in {".","NA"}:
            rows[date.fromisoformat(x["DATE"])]=float(raw)
    return rows

def ecb():
    r=requests.get(ECB,timeout=30,headers={"User-Agent":"BermeEnergyAutomation/1.0"}); r.raise_for_status()
    root=ET.fromstring(r.content)
    rates={}
    for cube in root.iter():
        t=cube.attrib.get("time")
        if not t: continue
        for child in list(cube):
            if child.attrib.get("currency")=="USD":
                rates[date.fromisoformat(t)]=float(child.attrib["rate"])
    return rates

def fnum(x,n=2): return f"{x:.{n}f}".replace(".",",")

def build():
    start,end=completed_week(); b=fred(); fx=ecb()
    common=sorted(set(b)&set(fx))
    eur={d:b[d]/fx[d] for d in common}
    weekly=[(d,eur[d]) for d in common if start<=d<=end]
    if len(weekly)<3: raise RuntimeError(f"Pocos datos Brent/ECB para {start}..{end}: {len(weekly)}")
    hist_d=max(common,key=lambda d:eur[d]); hist_v=eur[hist_d]
    vals=[v for _,v in weekly]; avg=sum(vals)/len(vals)
    return {
      "week_start":start.isoformat(),"week_end":end.isoformat(),
      "weekly_mean_eur_bbl":avg,"min_eur_bbl":min(vals),"max_eur_bbl":max(vals),
      "historical_max_eur_bbl":hist_v,"historical_max_date":hist_d.isoformat(),
      "pct_vs_historical":(avg/hist_v-1)*100,
      "daily":[{"date":d.isoformat(),"eur_bbl":v} for d,v in weekly],
      "source":"EIA/FRED Brent spot + tipo de cambio de referencia BCE"
    }

def font(size,bold=False,italic=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans"
    p+=("-BoldOblique.ttf" if bold and italic else "-Bold.ttf" if bold else "-Oblique.ttf" if italic else ".ttf")
    return ImageFont.truetype(p,size)

def draw_oil(img):
    d=ImageDraw.Draw(img,"RGBA")
    d.rounded_rectangle((735,235,1070,430),radius=55,fill=(25,25,23,255))
    d.ellipse((700,250,875,425),fill=(20,20,18,255),outline=(145,145,135,255),width=8)
    d.ellipse((733,282,842,392),fill=(4,4,3,255))
    # oil stream
    d.polygon([(755,360),(810,355),(835,515),(790,540),(765,470)],fill=(32,27,15,245))
    d.polygon([(770,365),(795,360),(812,505),(798,515),(780,465)],fill=(165,115,35,120))

def render(data):
    W,H=1080,1920; BG=(247,244,237); INK=(15,15,15); MUTED=(83,82,79); GREEN=(10,126,46); CARD=(253,251,247); LIGHT=(244,242,236)
    img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    d.ellipse((760,-140,1190,290),fill=(235,240,226)); draw_oil(img)
    s=date.fromisoformat(data["week_start"]); e=date.fromisoformat(data["week_end"])
    months=["ENE","FEB","MAR","ABR","MAY","JUN","JUL","AGO","SEP","OCT","NOV","DIC"]
    d.multiline_text((930,210),f"SEMANA DEL\n{s.day} AL {e.day} {months[e.month-1]} {e.year}",font=font(24),fill=INK,anchor="ra",align="right",spacing=7)
    d.text((75,315),"Precio medio",font=font(65,True),fill=INK); d.text((75,392),"del",font=font(65,True),fill=INK); d.text((205,392),"petróleo",font=font(65,True),fill=GREEN)
    d.text((77,478),"€/barril (Brent)",font=font(31),fill=INK)
    d.rounded_rectangle((60,565,1020,1265),radius=32,fill=CARD); d.text((105,605),"Esta semana",font=font(31),fill=INK)
    avg=data["weekly_mean_eur_bbl"]; d.text((100,660),fnum(avg,2),font=font(104,True),fill=INK); d.text((450,732),"€/barril",font=font(36),fill=INK)
    pct=round(data["pct_vs_historical"]); d.rounded_rectangle((650,640,985,790),radius=24,fill=(232,242,228))
    d.text((690,665),f'{"↓" if pct<0 else "↑"} {pct:+d}%',font=font(48,True),fill=GREEN); d.text((690,728),"vs. máximo histórico",font=font(21),fill=INK)
    d.text((105,835),"Media diaria de la semana",font=font(27,True),fill=INK)
    x0,y0,x1,y1=120,875,950,1055; vals=[x["eur_bbl"] for x in data["daily"]]; lo=min(vals); hi=max(vals); pad=max((hi-lo)*.35,1.0); lo-=pad; hi+=pad
    for i in range(4):
        yy=y1-i*(y1-y0)/3; d.line((x0,yy,x1,yy),fill=(220,216,208),width=2)
    n=len(vals); pts=[]
    for i,v in enumerate(vals):
        x=x0+(i*(x1-x0)/(n-1 if n>1 else 1)); y=y1-(v-lo)/(hi-lo)*(y1-y0); pts.append((x,y))
    d.line(pts,fill=GREEN,width=6,joint="curve")
    for x,y in pts: d.ellipse((x-6,y-6,x+6,y+6),fill=GREEN)
    for i,item in enumerate(data["daily"]):
        lab=["L","M","X","J","V","S","D"][date.fromisoformat(item["date"]).weekday()]
        x=x0+(i*(x1-x0)/(n-1 if n>1 else 1)); d.text((x,1070),lab,font=font(22),fill=MUTED,anchor="ma")
    d.rounded_rectangle((95,1125,985,1235),radius=24,fill=LIGHT)
    hist_date=date.fromisoformat(data["historical_max_date"]); hist_label=f"{hist_date.day} {['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][hist_date.month-1]} {hist_date.year}"
    metrics=[("Mínimo",data["min_eur_bbl"]),("Máximo",data["max_eur_bbl"]),("Máximo histórico",data["historical_max_eur_bbl"])]
    for i,(lab,val) in enumerate(metrics):
        x=[205,505,805][i]; d.text((x,1147),lab,font=font(22,i==2),fill=INK,anchor="ma"); d.text((x,1183),fnum(val,2),font=font(38,True),fill=INK,anchor="ma"); d.text((x,1221),"€/barril",font=font(19),fill=INK,anchor="ma")
    d.text((805,1240),hist_label,font=font(18),fill=MUTED,anchor="ma")
    d.text((95,1305),"Fuente: EIA/FRED (Brent spot) + tipo de cambio BCE.",font=font(21),fill=MUTED)
    d.text((95,1338),"Precio de mercado; no equivale al precio final de carburantes.",font=font(21),fill=MUTED)
    d.rounded_rectangle((70,1400,1010,1515),radius=28,fill=(94,109,70))
    d.text((540,1430),"Si quieres revisar tu factura, escríbenos.",font=font(27,True),fill="white",anchor="ma"); d.text((540,1474),"Te ayudamos gratuitamente.",font=font(24),fill="white",anchor="ma")
    d.line((80,1555,150,1555),fill=GREEN,width=4); d.text((80,1572),"Ahorra con",font=font(28),fill=INK); d.text((80,1607),"Berme Energy.",font=font(30,italic=True),fill=GREEN)
    img.save(OUT_IMG,"JPEG",quality=93,optimize=True,progressive=True)

def main():
    data=build(); OUT_JSON.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); render(data)
    print(json.dumps({"week":[data["week_start"],data["week_end"]],"avg_eur_bbl":round(data["weekly_mean_eur_bbl"],2),"image":str(OUT_IMG)},ensure_ascii=False))
if __name__=="__main__": main()
