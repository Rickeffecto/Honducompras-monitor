# Monitor de HonduCompras

Proyecto para detectar nuevas oportunidades de contratación en Honduras y enviar avisos por Telegram.

## Estado

Diagnóstico inicial. Antes de activar notificaciones, hay que validar la página o endpoint que enumera los procesos activos para evitar alertas incompletas o falsas.

Portal oficial: https://www.honducompras.gob.hn/

## Próximos pasos

1. Validar el listado real de procesos activos y los enlaces de detalle.
2. Implementar extracción y deduplicación de oportunidades.
3. Configurar Telegram mediante secretos de GitHub Actions (`TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`).
4. Programar comprobaciones aproximadamente cada 15 minutos.

Nunca guardes tokens en el código ni los publiques.
