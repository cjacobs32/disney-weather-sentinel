# Disney Sentinel v1.6.0

## Objetivo

Permitir que una sola ejecución manual verifique todas las fechas configuradas para un viaje, sin tener que repetir el workflow cambiando `window_priority`.

## Comportamiento

- `npm run availability-all` recorre las fechas por prioridad.
- Cada fecha mantiene su propio estado, histórico, eventos y evidencia.
- El resultado final informa cuántas fechas fueron solicitadas y completadas.
- `validation_mode=true` mantiene Telegram y el circuito productivo sin cambios.
- `validation_mode=false` utiliza las reglas productivas normales.
- La ejecución automática programada continúa con la estrategia de rotación de bajo consumo.
