#!/usr/bin/env python3
"""Berme Energy: media horaria de tarifas residenciales por tramos."""
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT_IMG = DOCS / "story-weekly-electricity.jpg"
OUT_JSON = DOCS / "story-weekly-electricity.json"
HISTORY_JSON = DOCS / "retail-electricity-hourly-history.json"

# Orden de cada tupla: valle, llano, punta. Precios de energía sin impuestos.
# Cada ejecución intenta refrescarlos desde la página indicada. El último dato
# válido guardado se usa si una web impide temporalmente la lectura automática.
PROVIDERS = [
    ("Endesa", "Conecta 3 Periodos", "https://www.endesa.com/es/luz-y-gas/luz/one/tarifa-one-luz-3periodos", (0.094410, 0.117810, 0.186210)),
    ("Iberdrola", "Plan Online 3 Periodos", "https://www.iberdrola.es/luz/tarifas/plan-online-tres-periodos", (0.099000, 0.136000, 0.194000)),
    ("Naturgy", "Tarifa Noche", "https://www.naturgy.es/hogar/luz/tarifa_noche", (0.080900, 0.105200, 0.173700)),
    ("Repsol", "Discriminación Horaria", "https://www.repsol.es/particulares/hogar/luz-y-gas/tarifas/tarifa-discriminacion-horaria/", (0.096900, 0.115900, 0.199900)),
    ("TotalEnergies", "Programa tu Ahorro", "https://www.totalenergies.es/es/hogares/tarifas-luz", (0.064852, 0.092051, 0.160301)),
    ("Octopus", "Octopus 3", "https://octopusenergy.es/tarifa-octopus-3", (0.079000, 0.098000, 0.184000)),
    ("Gana Energía", "Tramos Horarios", "https://ganaenergia.com/tarifas-luz/tramos-horarios", (0.080000, 0.104000, 0.171000)),
    ("Holaluz", "Tarifa 3", "https://www.holaluz.com/luz/tarifas-luz", (0.134000, 0.163000, 0.242000)),
    ("Plenitude", "Tendencia", "https://eniplenitude.es/hogar/tarifas-luz/tendencia/", (0.185000, 0.174000, 0.248000)),
    # Pepeenergy es indexada. Esta referencia se sustituye cuando su web
    # publica el siguiente promedio mensual por periodos.
    ("Pepeenergy", "Variable", "https://www.pepeenergy.com/tarifas-luz/tarifa-variable-luz", (0.143113, 0.205116, 0.278941)),
]

# Primera muestra empresarial verificable (pequeños negocios 2.0TD, <=15 kW).
# Endesa e Iberdrola publican precio 24 h; Naturgy publica tres periodos.
BUSINESS_PROVIDERS = [
    ("Endesa", (0.124777, 0.124777, 0.124777)),
    ("Iberdrola", (0.143331, 0.143331, 0.143331)),
    ("Naturgy", (0.129000, 0.164000, 0.237000)),
]

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "es-ES,es;q=0.9"}

def reference_date():
    raw = os.getenv("BERME_REFERENCE_DATE")
    return date.fromisoformat(raw) if raw else datetime.now(ZoneInfo("Europe/Madrid")).date()

def page_text(url):
    response = requests.get(url, headers=HEADERS, timeout=8)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", " ".join(soup.stripped_strings))

def number(value):
    return float(value.replace(".", "").replace(",", ".") if "," in value else value)

def labelled_price(text, labels):
    for label in labels:
        patterns = [
            rf"{label}.{{0,150}}?(0[,.]\d{{3,6}})\s*€?\s*/?\s*kWh",
            rf"(0[,.]\d{{3,6}})\s*€?\s*/?\s*kWh.{{0,100}}?{label}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I | re.S)
            if match:
                value = number(match.group(1))
                if 0.04 <= value <= 0.40:
                    return value
    raise ValueError("precio por tramo no encontrado")

def live_periods(text):
    valley = labelled_price(text, [r"(?:periodo|tramo|hora|energ[ií]a)?\s*valle", r"off[- ]peak"])
    flat = labelled_price(text, [r"(?:periodo|tramo|hora|energ[ií]a)?\s*llan[oa]", r"mid[- ]peak"])
    peak = labelled_price(text, [r"(?:periodo|tramo|hora|energ[ií]a)?\s*punta", r"peak"])
    if not valley <= max(flat, peak) or peak < min(valley, flat):
        raise ValueError("orden de precios incoherente")
    return valley, flat, peak

def load_history():
    try:
        return json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []

def cached_periods(history, name):
    for snapshot in reversed(history):
        for row in snapshot.get("providers", []):
            if row.get("name") == name and len(row.get("period_prices", [])) == 3:
                return tuple(row["period_prices"])
    return None

def collect():
    today = reference_date()
    history = load_history()
    rows = []
    for name, tariff, url, seed in PROVIDERS:
        status = "live"
        try:
            periods = live_periods(page_text(url))
            # Reject power terms, tax-inclusive duplicates and unrelated cards
            # accidentally matched on pages that contain several products.
            if any(abs(value / reference - 1) > 0.25 for value, reference in zip(periods, seed)):
                raise ValueError("precios leídos no corresponden a la tarifa seleccionada")
        except Exception as exc:
            periods = cached_periods(history, name) or seed
            status = "cached" if cached_periods(history, name) else "verified_reference"
            print("TARIFF_FALLBACK", name, type(exc).__name__, exc)
        rows.append({"name": name, "tariff": tariff, "source_url": url,
                     "period_prices": list(periods), "status": status})

    averages = [mean(row["period_prices"][i] for row in rows) for i in range(3)]
    valley, flat, peak = averages
    weekday = [valley] * 8 + [flat] * 2 + [peak] * 4 + [flat] * 4 + [peak] * 4 + [flat] * 2
    # Semana completa: cinco laborables con 2.0TD y sábado/domingo enteros en valle.
    weekly_hours = weekday * 5 + [valley] * 48
    week_end = today - timedelta(days=today.weekday() + 1)
    week_start = week_end - timedelta(days=6)
    previous_weekly = [item["weekly_average_eur_kwh"] for item in history
                       if isinstance(item.get("weekly_average_eur_kwh"), (int, float))]
    weekly_average = mean(weekly_hours)
    business_weekly = []
    for _, (business_valley, business_flat, business_peak) in BUSINESS_PROVIDERS:
        business_weekly.append((88 * business_valley + 40 * business_flat + 40 * business_peak) / 168)
    business_average = mean(business_weekly)
    previous_business = [item["business_weekly_average_eur_kwh"] for item in history
                         if isinstance(item.get("business_weekly_average_eur_kwh"), (int, float))]
    business_historical = mean(previous_business) if previous_business else business_average
    historical_average = mean(previous_weekly) if previous_weekly else weekly_average
    change_vs_historical = (weekly_average / historical_average - 1) * 100 if historical_average else 0
    snapshot = {
        "date": today.isoformat(),
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "methodology": {
            "scope": "España peninsular, hogar 2.0TD, día laborable",
            "metric": "Media aritmética del término de energía sin impuestos",
            "sample": 10,
            "periods": "Valle 00-08; llano 08-10, 14-18 y 22-24; punta 10-14 y 18-22",
            "excludes": "potencia, cuotas, mantenimiento, servicios e impuestos",
        },
        "period_average": {"valley": valley, "flat": flat, "peak": peak},
        "weekly_average_eur_kwh": weekly_average,
        "business_weekly_average_eur_kwh": business_average,
        "business_historical_average_eur_kwh": business_historical,
        "business_change_vs_historical_pct": (business_average / business_historical - 1) * 100,
        "business_sample": len(BUSINESS_PROVIDERS),
        "historical_average_eur_kwh": historical_average,
        "change_vs_historical_pct": change_vs_historical,
        "historical_weeks": len(previous_weekly) + 1,
        "weekly_history": previous_weekly[-11:] + [weekly_average],
        "providers": rows,
    }
    history = [item for item in history if item.get("date") != today.isoformat()] + [snapshot]
    HISTORY_JSON.write_text(json.dumps(history[-104:], ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot

def font(size, bold=False):
    suffix = "-Bold.ttf" if bold else ".ttf"
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans" + suffix, size)

def fmt(value):
    return f"{value:.3f}".replace(".", ",")

def render(data):
    width, height = 1080, 1920
    bg, ink, muted = (247,244,237), (15,15,15), (83,82,79)
    green, olive, card, light = (42,111,57), (90,102,74), (253,251,247), (239,237,231)
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    months = ["ENE","FEB","MAR","ABR","MAY","JUN","JUL","AGO","SEP","OCT","NOV","DIC"]

    # 220 px superiores y 300 px inferiores reservados para Instagram.
    draw.text((72,330), "Precio medio", font=font(62, True), fill=ink)
    draw.text((72,405), "semanal", font=font(62, True), fill=green)
    draw.text((74,485), "Hogares y pequeños negocios 2.0TD · €/kWh", font=font(28), fill=ink)

    draw.rounded_rectangle((60,565,1020,1370), radius=34, fill=card)
    weekly = data["weekly_average_eur_kwh"]
    business = data["business_weekly_average_eur_kwh"]
    columns = [("HOGARES", weekly, "10 tarifas", data["change_vs_historical_pct"]),
               ("NEGOCIOS", business, f'{data["business_sample"]} tarifas', data["business_change_vs_historical_pct"])]
    has_comparison = data["historical_weeks"] > 1
    for index, (label, value, sample, pct) in enumerate(columns):
        x = 100 + index * 455
        draw.text((x,610), label, font=font(22, True), fill=muted)
        draw.text((x,660), fmt(value), font=font(72, True), fill=ink)
        draw.text((x+300,710), "€/kWh", font=font(25), fill=ink)
        draw.text((x,760), sample, font=font(18), fill=muted)
        if has_comparison:
            draw.text((x+300,760), f'{pct:+.1f}% vs. histórico'.replace(".", ","), font=font(18, True), fill=green, anchor="ra")

    weeks = data["historical_weeks"]
    if has_comparison:
        historical = data["historical_average_eur_kwh"]
        draw.rounded_rectangle((100,820,975,940), radius=22, fill=light)
        draw.text((135,840), "Media histórica registrada", font=font(23, True), fill=ink)
        draw.text((135,875), f'Hogares {fmt(historical)}', font=font(29, True), fill=ink)
        draw.text((500,875), f'Negocios {fmt(data["business_historical_average_eur_kwh"])}', font=font(29, True), fill=ink)
        draw.text((930,882), f'{weeks} semanas', font=font(21), fill=muted, anchor="ra")
        draw.text((100,985), "Evolución semanal", font=font(27, True), fill=ink)
        x0, y0, x1, y1 = 110, 1045, 960, 1245
        values = data["weekly_history"]
        lo, hi = min(values) * .90, max(values) * 1.08
        if hi == lo:
            hi = lo + 0.01
        for i in range(4):
            y = y1 - i * (y1-y0) / 3
            draw.line((x0,y,x1,y), fill=(220,216,208), width=2)
        points=[]
        count = max(1, len(values) - 1)
        for index, value in enumerate(values):
            x=x0+index*(x1-x0)/count
            y=y1-(value-lo)/(hi-lo)*(y1-y0)
            points.append((x,y))
        draw.line(points, fill=green, width=7, joint="curve")
        draw.text((110,1270), "Semanas anteriores", font=font(18), fill=muted)
        draw.text((960,1270), "Semana actual", font=font(18), fill=muted, anchor="ra")
    else:
        pass

    start=date.fromisoformat(data["week_start"]); end=date.fromisoformat(data["week_end"])
    period_y = 875 if not has_comparison else 1315
    draw.text((100,period_y), f"Semana del {start.day} {months[start.month-1]} al {end.day} {months[end.month-1]}", font=font(21, True), fill=ink)
    draw.text((90,1420), "Fuentes: tarifas públicas de las comercializadoras seleccionadas.", font=font(18), fill=muted)
    draw.text((90,1450), "Energía sin impuestos; excluye potencia, cuotas y servicios.", font=font(18), fill=muted)
    draw.rounded_rectangle((72,1510,1008,1620), radius=26, fill=olive)
    draw.text((540,1537), "Si quieres revisar tu factura, escríbenos.", font=font(25, True), fill="white", anchor="ma")
    draw.text((540,1580), "Te ayudamos gratuitamente.", font=font(23), fill="white", anchor="ma")
    image.save(OUT_IMG, "JPEG", quality=94, optimize=True, progressive=True)

def main():
    data = collect()
    render(data)
    print(json.dumps({"weekly_average": round(data["weekly_average_eur_kwh"], 4), "image": str(OUT_IMG)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
