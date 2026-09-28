# Agente 1 — Stories

Objetivo: generar y publicar automáticamente tres Stories semanales de Berme Energy.

## Stories
1. Precio medio de la luz — OMIE España — €/kWh.
2. Precio medio del gas — MIBGAS PVB — €/kWh.
3. Precio medio de los combustibles — Gasolina 95, Diésel A y Brent.

## Reglas
- Periodo: semana completa anterior, lunes a domingo.
- No mezclar series ni unidades incompatibles.
- Los gráficos deben basarse en datos reales.
- El Brent se expresa en $/barril.
- CTA: “Si necesitas ayuda con tu factura, escríbenos. Te ayudamos gratuitamente.”
- Formato final: 1080 × 1920 px.
- Plantillas fijas: cada ejecución solo actualiza datos, fechas, porcentajes y gráficos.
- Mantener 220 px libres arriba y 300 px libres abajo para la interfaz de Instagram.
- El flujo de prueba usa la misma plantilla fija de luz que la publicación semanal.

La publicación automática se activará cuando Meta Instagram API esté autorizada y sus credenciales estén guardadas como GitHub Secrets.
