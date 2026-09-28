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
- GitHub Actions para comprobaciones.

## Puesta en marcha

1. Crear una cuenta gratuita de Cloudflare.
2. Ejecutar `npm install` y `npx wrangler login`.
3. Crear D1 con `npx wrangler d1 create berme-energy`.
4. Sustituir `database_id` en `wrangler.toml`.
5. Crear el secreto con `npx wrangler secret put ADMIN_TOKEN`.
6. Ejecutar `npm run db:remote` y `npm run deploy`.

El envío de mensajes es manual y requiere aprobación. Así se evitan cargos de WhatsApp y mensajes accidentales.
