# Berme Energy · Agentes

MVP gratuito del agente de captación y seguimiento comercial.

## Funciones incluidas

- Alta de leads con detección de duplicados.
- Embudo comercial y prioridades.
- Próxima fecha de seguimiento.
- Registro de actividad.
- Mensajes sugeridos por IA para aprobación humana.
- Límites comerciales: no promete ahorro ni solicita documentación sensible prematuramente.

## Infraestructura gratuita

- Cloudflare Workers Free.
- Cloudflare D1 Free.
- Workers AI dentro de su asignación gratuita.
- GitHub Actions para comprobaciones y despliegue.

## Despliegue

El flujo `Deploy Berme Captacion Agent` verifica el proyecto, aplica las migraciones D1,
configura el acceso privado y publica el agente al actualizar `main`. También admite
ejecución manual desde GitHub Actions.

El envío de mensajes es manual y requiere aprobación. Así se evitan cargos de WhatsApp y mensajes accidentales.
