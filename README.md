# Monitor de HonduCompras

Monitor automático del portal oficial de HonduCompras para detectar procesos de contratación y enviar alertas por Telegram cuando los resultados sean verificables.

## Fuente

- Portal oficial: https://honducompras.gob.hn/
- Búsqueda avanzada conocida: http://sicc.honducompras.gob.hn/HC/procesos/busquedahistorico.aspx

El monitor no utiliza la API EDCA de SEFIN como sustituto del portal de licitaciones.

## Estado y protección contra avisos falsos

GitHub Actions intenta ejecutar el monitor cada 5 minutos y también permite ejecución manual desde **Actions**. La búsqueda se limita a los últimos 14 días.

La página puede responder HTTP 200 y aun así no devolver los resultados: en las pruebas recientes devolvió el texto **“Cargando…”** y tablas del formulario. Por eso el monitor ahora exige una tabla de procesos reconocible y enlaces de detalle antes de enviar alertas. Si la página no entrega resultados verificables, la ejecución se marca como error y no envía notificaciones falsas; el siguiente ciclo programado volverá a intentarlo.

Esto significa que el sondeo automático está configurado, pero las alertas de oportunidades solo se consideran operativas cuando la búsqueda avanzada devuelve resultados reales que el monitor pueda validar.

## Configurar Telegram

En el repositorio, abre **Settings → Secrets and variables → Actions → New repository secret** y agrega:

- `TELEGRAM_BOT_TOKEN`: token creado con `@BotFather`.
- `TELEGRAM_CHAT_ID`: identificador del chat o canal que recibirá los avisos.

Para un chat privado, abre el bot y envíale `/start` antes de probarlo. No publiques el token ni lo incluyas en el código.

## Deduplicación

Los identificadores de procesos ya notificados se guardan en `seen_processes.json` y se conservan mediante la caché de GitHub Actions para evitar avisos repetidos entre ejecuciones.

## Comprobar el estado

Consulta la pestaña [Actions](https://github.com/Rickeffecto/Honducompras-monitor/actions). Busca `SEARCH_RESULTS_VALIDATED: yes` en los registros para confirmar que la página entregó resultados verificables. Un resultado HTTP 200 por sí solo no demuestra que la búsqueda haya funcionado.
