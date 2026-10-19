# Monitor de HonduCompras

Proyecto para detectar nuevas oportunidades de contratación en Honduras y, cuando la lectura de los procesos esté validada, enviar avisos por Telegram.

## Fuente de información

Se utilizará únicamente el portal oficial de HonduCompras y su opción **Búsqueda Avanzada**, indicada por ONCAE para consultar los procesos publicados por las instituciones:

- Portal oficial: https://honducompras.gob.hn/
- Búsqueda histórica conocida: https://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx
- Información de ONCAE: https://oncae.gob.hn/contacto/preguntas-frecuentes/

La API EDCA de SEFIN queda fuera del monitor.

## Estado actual

Fase de diagnóstico de acceso. `discover.py` prueba el portal oficial y la ruta conocida de Búsqueda Avanzada, identifica enlaces y campos de formularios y registra errores de conexión. La verificación SSL sigue activada: el script no ignora certificados vencidos.

**Todavía no se considera activo el detector de nuevas oportunidades.** Primero hay que confirmar que la búsqueda avanzada responde y extraer correctamente sus resultados y enlaces de detalle; después se implementarán deduplicación y notificaciones.

## Ejecución

GitHub Actions ejecuta el diagnóstico aproximadamente cada 15 minutos y permite iniciarlo manualmente desde la pestaña Actions.

## Próximos pasos

1. Confirmar acceso estable a Búsqueda Avanzada de HonduCompras.
2. Extraer los campos reales de cada proceso y sus enlaces oficiales.
3. Guardar identificadores vistos para evitar alertas duplicadas.
4. Configurar Telegram mediante secretos de GitHub Actions (`TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`).
5. Activar alertas solo después de validar la extracción.

Nunca guardes tokens en el código ni los publiques.
