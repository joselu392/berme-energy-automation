#!/usr/bin/env python3
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = ROOT / "assets"
DOCS.mkdir(exist_ok=True)

OUT_IMG = DOCS / "story-weekly-electricity.jpg"
OUT_JSON = DOCS / "story-weekly-electricity.json"
HISTORY_JSON = DOCS / "retail-electricity-history.json"

TODAY_SEED = date(2026, 9, 24)

# Metodología fija Berme Energy:
# - 10 comercializadoras seleccionadas.
# - Hogar / 2.0TD / precio único 24h.
# - Término de energía en €/kWh, sin impuestos.
# - Se excluyen potencia, cuotas, mantenimiento y servicios adicionales.
# - Se utiliza la oferta pública online para nuevas contrataciones cuando aplica.
PROVIDERS = [
    {
        "name": "Endesa",
        "tariff": "Conecta Luz",
        "url": "https://www.endesa.com/es/luz-y-gas/luz/conecta-de-endesa",
        "parser": "endesa",
        "seed": 0.11999,
    },
    {
        "name": "Iberdrola",
        "tariff": "Plan Online",
        "url": "https://www.iberdrola.es/luz/tarifas/plan-online",
        "fallback_url": "https://ifinanzas.es/energia/comparar/iberdrola-plan-online-vs-octopus-relax",
        "parser": "iberdrola",
        "seed": 0.1249,
    },
    {
        "name": "Naturgy",
        "tariff": "Tarifa Por Uso Luz",
        "url": "https://www.naturgy.es/precios_tarifauso_luz",
        "parser": "naturgy",
        "seed": 0.112,
    },
    {
        "name": "Repsol",
        "tariff": "Tarifa Sin Horarios",
        "url": "https://www.repsol.es/particulares/hogar/luz-y-gas/tarifas/plan-mixto-rl2/",
        "parser": "repsol",
        "seed": 0.119970,
    },
    {
        "name": "TotalEnergies",
        "tariff": "A tu Aire Siempre Luz",
        "url": "https://www.totalenergies.es/es/hogares",
        "parser": "totalenergies",
        "seed": 0.0999,
    },
    {
        "name": "Octopus",
        "tariff": "Octopus Relax",
        "url": "https://octopusenergy.es/precios",
        "fallback_url": "https://luzometro.com/companias-luz/octopus-energy",
        "parser": "octopus",
        "seed": 0.129,
    },
    {
        "name": "Pepeenergy",
        "tariff": "Tarifa Estable",
        "url": "https://www.pepeenergy.com/tarifas-luz",
        "parser": "pepeenergy",
        "seed": 0.1199,
    },
    {
        "name": "Gana Energía",
        "tariff": "Tarifa 24 horas",
        "url": "https://ganaenergia.com/contratacion-luz?tid=6a103e94eeeae36be0aa992c",
        "fallback_url": "https://www.servalys.es/comercializadoras/ganaenergia/tarifas",
        "parser": "gana",
        "seed": 0.1190,
    },
    {
        "name": "Holaluz",
        "tariff": "Tarifa Clásica online",
        "url": "https://www.holaluz.com/luz/tarifas-luz",
        "fallback_url": "https://www.tarifadeluzhoy.com/comparador/holaluz-octopus-energy",
        "parser": "holaluz",
        "seed": 0.165,
    },
    {
        "name": "Plenitude",
        "tariff": "Fácil Plus Luz",
        "url": "https://eniplenitude.es/",
        "parser": "plenitude",
        "seed": 0.119990,
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
}

def reference_date():
    ref = os.getenv("BERME_REFERENCE_DATE")
    return date.fromisoformat(ref) if ref else datetime.now(ZoneInfo("Europe/Madrid")).date()

def html_text(url, attempts=3):
    last = None
    for i in range(attempts):
        try:
            r = requests.get(url, timeout=35, headers=HEADERS, allow_redirects=True)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = " ".join(soup.stripped_strings)
            return re.sub(r"\s+", " ", text)
        except Exception as e:
            last = e
            if i + 1 < attempts:
                time.sleep(2 + i)
    raise last

def num(raw):
    return float(raw.replace(".", "").replace(",", ".") if "," in raw else raw)

def validate_price(v):
    if not (0.05 <= v <= 0.35):
        raise ValueError(f"Precio fuera de rango: {v}")
    return v

def first_regex(text, patterns):
    for p in patterns:
        m = re.search(p, text, flags=re.I | re.S)
        if m:
            return validate_price(num(m.group(1)))
    raise ValueError("No se encontró un precio 24h válido")

def parse_price(provider, text):
    p = provider["parser"]

    if p == "endesa":
        return first_regex(text, [
            r"Tarifa Conecta Luz.{0,1200}?T\.?\s*de energía.{0,500}?(0[,.]\d{4,6})\s*€/kWh",
            r"Tarifa Conecta Luz.{0,1500}?(0[,.]\d{4,6})\s*€/kWh",
        ])

    if p == "iberdrola":
        return first_regex(text, [
            r"subi[oó]\s+de\s+0[,.]\d+\s+a\s+(0[,.]\d{4,6})\s*€/kWh",
            r"Plan Online.{0,1000}?Las 24 horas del día\s*(0[,.]\d{4,6})\s*€/kWh",
            r"Plan Online.{0,1200}?Precio de energía consumida.{0,500}?(0[,.]\d{4,6})\s*€/kWh",
            r"Plan Online.{0,1800}?(0[,.]\d{4,6})\s*€/kWh",
        ])

    if p == "naturgy":
        return first_regex(text, [
            r"Precio fijo las 24h\s*(0[,.]\d{4,6})\s*€/kWh",
            r"Tarifa Por Uso Luz.{0,700}?T[eé]rmino de Energ[ií]a.{0,300}?(0[,.]\d{4,6})\s*€/kWh",
        ])

    if p == "repsol":
        # We deliberately select the option WITHOUT Asistente 24h.
        idx = text.lower().find("no incluye asistente")
        if idx >= 0:
            before = text[max(0, idx - 2200):idx]
            vals = re.findall(r"(0[,.]\d{4,6})\s*€/kWh", before, flags=re.I)
            if vals:
                return validate_price(num(vals[-1]))
        return first_regex(text, [
            r"-7\s*%.{0,1000}?24 horas\s*(0[,.]\d{4,6})\s*€/kWh",
            r"24 horas\s*(0[,.]\d{4,6})\s*€/kWh.{0,1200}?No incluye asistente",
        ])

    if p == "totalenergies":
        return first_regex(text, [
            r"Precio luz\s*(0[,.]\d{4,6})\s*€/kWh",
            r"A tu Aire Siempre Luz.{0,900}?(0[,.]\d{4,6})\s*€/kWh",
        ])

    if p == "octopus":
        return first_regex(text, [
            r"Octopus Relax.{0,700}?Energ[ií]a\s*(0[,.]\d{3,6})\s*€/kWh",
            r"Octopus Relax.{0,500}?(0[,.]\d{3,6})\s*€/kWh",
        ])

    if p == "pepeenergy":
        return first_regex(text, [
            r"La del mismo precio todo el d[ií]a\s*(0[,.]\d{4,6})\s*€/kWh",
            r"Tarifa Estable de Luz.{0,300}?(0[,.]\d{4,6})\s*€/kWh",
            r"Mismo precio todo el d[ií]a:\s*(0[,.]\d{4,6})\s*€/kWh",
        ])

    if p == "gana":
        return first_regex(text, [
            r"Tarifa 24 horas.{0,1000}?24h\s*:\s*(0[,.]\d{4,6})\s*€/kWh",
            r"Tarifa 24 horas.{0,900}?Energ[ií]a\s*(0[,.]\d{4,6})\s*€/kWh",
        ])

    if p == "holaluz":
        return first_regex(text, [
            r"Descuentos publicados.{0,250}?(0[,.]\d{3,6})\s*€/kWh",
            r"Tarifa Cl[aá]sica.{0,900}?Si contratas online:\s*(0[,.]\d{3,6})\s*€/kWh",
            r"Si contratas online:\s*(0[,.]\d{3,6})\s*€/kWh",
        ])

    if p == "plenitude":
        return first_regex(text, [
            r"F[aá]cil Plus Luz.{0,800}?Consumo de energ[ií]a\s*(0[,.]\d{4,6})\s*€/kWh",
            r"F[aá]cil Plus Luz.{0,700}?(0[,.]\d{4,6})\s*€/kWh",
        ])

    raise ValueError(f"Parser desconocido: {p}")

def load_history():
    if not HISTORY_JSON.exists():
        return []
    try:
        data = json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def latest_previous_price(history, provider_name, today, max_age_days=14):
    for snapshot in reversed(history):
        try:
            d = date.fromisoformat(snapshot["date"])
        except Exception:
            continue
        if d >= today:
            continue
        age = (today - d).days
        if age > max_age_days:
            break
        for row in snapshot.get("providers", []):
            if row.get("name") == provider_name and isinstance(row.get("price_eur_kwh"), (int, float)):
                return float(row["price_eur_kwh"]), d.isoformat()
    return None, None

def collect_prices():
    today = reference_date()
    history = load_history()
    rows = []
    live_count = 0

    for provider in PROVIDERS:
        errors = []
        price = None
        used_url = provider["url"]
        status = "live"

        urls = [provider["url"]]
        if provider.get("fallback_url"):
            urls.append(provider["fallback_url"])

        for url in urls:
            try:
                text = html_text(url)
                price = parse_price(provider, text)
                used_url = url
                status = "live" if url == provider["url"] else "live_fallback_source"
                live_count += 1
                break
            except Exception as e:
                errors.append(f"{url}: {type(e).__name__}: {e}")

        if price is None:
            old, old_date = latest_previous_price(history, provider["name"], today)
            if old is not None:
                price = old
                status = f"cached_{old_date}"
            elif abs((today - TODAY_SEED).days) <= 14:
                price = provider["seed"]
                status = "bootstrap_seed"
            else:
                status = "failed"

        rows.append({
            "name": provider["name"],
            "tariff": provider["tariff"],
            "price_eur_kwh": price,
            "status": status,
            "source_url": used_url,
            "errors": errors[-2:],
        })

    for r in rows:
        print("TARIFF_STATUS", r["name"], r["status"], r["price_eur_kwh"], " | ".join(r.get("errors", [])))

    valid = [r for r in rows if isinstance(r["price_eur_kwh"], (int, float))]
    non_seed = [r for r in valid if not r["status"].startswith("bootstrap")]
    # Publishing-quality guardrail: 10 prices available and at least 8 freshly fetched
    # (the remaining 2 may use a recent cached value if a website is temporarily down).
    if len(valid) != 10 or live_count < 8:
        raise RuntimeError(
            f"Control de calidad fallido: {len(valid)}/10 precios válidos, "
            f"{live_count}/10 obtenidos en vivo. No se genera una Story publicable."
        )

    prices = [r["price_eur_kwh"] for r in valid]
    avg = mean(prices)
    min_row = min(valid, key=lambda r: r["price_eur_kwh"])
    max_row = max(valid, key=lambda r: r["price_eur_kwh"])

    prev_snapshot = None
    for snap in reversed(history):
        if snap.get("date") != today.isoformat() and isinstance(snap.get("average_eur_kwh"), (int, float)):
            prev_snapshot = snap
            break

    change = None
    if prev_snapshot and prev_snapshot["average_eur_kwh"]:
        change = (avg / float(prev_snapshot["average_eur_kwh"]) - 1) * 100

    snapshot = {
        "date": today.isoformat(),
        "methodology": {
            "scope": "Residencial España, tarifa 24h / precio único",
            "metric": "Término de energía €/kWh sin impuestos",
            "sample": 10,
            "excludes": "potencia, cuotas, mantenimiento, servicios extra e impuestos",
            "aggregation": "media aritmética simple de una tarifa seleccionada por comercializadora",
        },
        "average_eur_kwh": avg,
        "min": {"name": min_row["name"], "price_eur_kwh": min_row["price_eur_kwh"]},
        "max": {"name": max_row["name"], "price_eur_kwh": max_row["price_eur_kwh"]},
        "change_vs_previous_pct": change,
        "live_sources": live_count,
        "providers": valid,
    }

    history = [h for h in history if h.get("date") != today.isoformat()]
    history.append(snapshot)
    history = sorted(history, key=lambda h: h.get("date", ""))[-104:]
    HISTORY_JSON.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    return snapshot

def font(size, bold=False, italic=False):
    base = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
    if bold and italic:
        path = base + "-BoldOblique.ttf"
    elif bold:
        path = base + "-Bold.ttf"
    elif italic:
        path = base + "-Oblique.ttf"
    else:
        path = base + ".ttf"
    return ImageFont.truetype(path, size)

def fmt(v, decimals=3):
    return f"{v:.{decimals}f}".replace(".", ",")

def paste_bulb(img):
    asset = ASSETS / "bulb_approved.jpg"
    if not asset.exists():
        return
    bulb = Image.open(asset).convert("RGB")
    target_w = 330
    target_h = round(bulb.height * target_w / bulb.width)
    bulb = bulb.resize((target_w, target_h), Image.Resampling.LANCZOS)
    # The approved crop already contains the same warm background.
    img.paste(bulb, (750, 205))

def render(data):
    W, H = 1080, 1920
    BG = (247, 244, 237)
    INK = (15, 15, 15)
    MUTED = (83, 82, 79)
    GREEN = (42, 111, 57)
    OLIVE = (90, 102, 74)
    CARD = (253, 251, 247)
    LIGHT = (244, 242, 236)
    GRID = (226, 222, 214)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Fixed approved hero asset; data never changes this image.
    paste_bulb(img)

    current = date.fromisoformat(data["date"])
    months = ["ENE","FEB","MAR","ABR","MAY","JUN","JUL","AGO","SEP","OCT","NOV","DIC"]

    # TOP SAFE AREA: no essential content above 205px.
    d.multiline_text(
        (920, 210),
        f"ACTUALIZADO\n{current.day} {months[current.month-1]} {current.year}",
        font=font(23), fill=INK, anchor="ra", align="right", spacing=7
    )

    d.text((72, 330), "Precio medio", font=font(63, bold=True), fill=INK)
    d.text((72, 405), "tarifas", font=font(63, bold=True), fill=INK)
    d.text((285, 405), "24h", font=font(63, bold=True), fill=GREEN)
    d.text((74, 485), "10 comercializadoras · residencial · €/kWh", font=font(28), fill=INK)

    # Main card.
    d.rounded_rectangle((60, 565, 1020, 1250), radius=34, fill=CARD)
    d.text((100, 600), "Media analizada", font=font(29), fill=INK)
    d.text((96, 645), fmt(data["average_eur_kwh"], 3), font=font(104, bold=True), fill=INK)
    d.text((438, 710), "€/kWh", font=font(38), fill=INK)

    change = data.get("change_vs_previous_pct")
    badge = (665, 620, 980, 755)
    d.rounded_rectangle(badge, radius=24, fill=(236, 241, 231))
    if change is None:
        d.text((822, 653), "10 tarifas", font=font(37, bold=True), fill=OLIVE, anchor="ma")
        d.text((822, 706), "muestra actual", font=font(19), fill=MUTED, anchor="ma")
    else:
        arrow = "↓" if change < 0 else "↑"
        d.text((822, 646), f"{arrow} {change:+.1f}%", font=font(42, bold=True), fill=OLIVE, anchor="ma")
        d.text((822, 704), "vs. semana anterior", font=font(19), fill=MUTED, anchor="ma")

    # 10 providers: two perfectly aligned columns of five.
    d.text((100, 790), "Tarifas 24h incluidas en la media", font=font(25, bold=True), fill=INK)
    sorted_rows = sorted(data["providers"], key=lambda r: r["price_eur_kwh"])
    left = sorted_rows[:5]
    right = sorted_rows[5:]
    col_x = [100, 555]
    list_top = 838
    row_h = 49

    for col, rows in enumerate((left, right)):
        x = col_x[col]
        for i, row in enumerate(rows):
            y = list_top + i * row_h
            d.line((x, y + 37, x + 390, y + 37), fill=GRID, width=1)
            name = row["name"]
            if len(name) > 13:
                name = name[:13] + "…"
            d.text((x, y), name, font=font(20), fill=MUTED)
            d.text((x + 390, y), fmt(row["price_eur_kwh"], 3), font=font(21, bold=True), fill=INK, anchor="ra")

    # Three equal metric cards — fixed width/height/padding.
    metric_y0, metric_y1 = 1095, 1215
    gap = 16
    total_w = 880
    cell_w = (total_w - 2 * gap) // 3
    start_x = 100
    metrics = [
        ("Mínimo", data["min"]["price_eur_kwh"], data["min"]["name"]),
        ("Media", data["average_eur_kwh"], "10 tarifas"),
        ("Máximo", data["max"]["price_eur_kwh"], data["max"]["name"]),
    ]
    for i, (label, value, sub) in enumerate(metrics):
        x0 = start_x + i * (cell_w + gap)
        x1 = x0 + cell_w
        d.rounded_rectangle((x0, metric_y0, x1, metric_y1), radius=20, fill=LIGHT)
        d.text(((x0+x1)/2, metric_y0+16), label, font=font(20, bold=True), fill=INK, anchor="ma")
        d.text(((x0+x1)/2, metric_y0+49), fmt(value, 3), font=font(35, bold=True), fill=INK, anchor="ma")
        d.text(((x0+x1)/2, metric_y0+89), sub, font=font(17), fill=MUTED, anchor="ma")

    # Source/methodology.
    d.ellipse((80, 1302, 116, 1338), outline=INK, width=3)
    d.text((98, 1301), "i", font=font(23, bold=True), fill=INK, anchor="ma")
    d.text((137, 1292), "Fuentes: webs públicas de las 10 comercializadoras seleccionadas.", font=font(18), fill=MUTED)
    d.text((137, 1322), "Término energía sin impuestos; excluye potencia, cuotas y servicios.", font=font(18), fill=MUTED)

    # Signature + CTA are safely above Instagram's bottom controls.
    d.line((78, 1408, 150, 1408), fill=GREEN, width=4)
    d.text((78, 1425), "Ahorra con", font=font(29), fill=INK)
    d.text((265, 1425), "Berme Energy.", font=font(30, italic=True), fill=GREEN)

    d.rounded_rectangle((72, 1495, 1008, 1605), radius=26, fill=(92, 104, 75))
    d.text((540, 1522), "Si quieres revisar tu factura, escríbenos.", font=font(25, bold=True), fill="white", anchor="ma")
    d.text((540, 1564), "Te ayudamos gratuitamente.", font=font(23), fill="white", anchor="ma")

    # Bottom ~315 px intentionally blank for reply / heart / share UI.
    img.save(OUT_IMG, "JPEG", quality=94, optimize=True, progressive=True)

def main():
    data = collect_prices()
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    render(data)
    print(json.dumps({
        "date": data["date"],
        "average_eur_kwh": round(data["average_eur_kwh"], 6),
        "min": data["min"],
        "max": data["max"],
        "live_sources": data["live_sources"],
        "image": str(OUT_IMG),
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
