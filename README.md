# Berme Energy Automation

Automatización de contenidos y futuros agentes operativos de Berme Energy.

## Arquitectura prevista

- `stories/` — Agente 1: datos energéticos, diseño y publicación de Stories.
- `captacion/` — Agente 3: captación de leads (fase posterior).
- `seguimiento/` — Agente 2: seguimiento de oportunidades (fase posterior).
- `orchestrator/` — coordinación entre agentes cuando el sistema comercial esté activo.
- `docs/` — páginas públicas requeridas por integraciones (privacidad y eliminación de datos).
- `config/` — branding y configuración común.

## Seguridad

Nunca se guardarán tokens, contraseñas ni secretos de Meta en el repositorio. Se almacenarán en GitHub Secrets.

## Estado

En configuración inicial de Meta Instagram API para publicar Stories automáticamente.
