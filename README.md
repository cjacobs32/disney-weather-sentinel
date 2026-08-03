# Disney Sentinel v1.5

Disney Sentinel es una plataforma personal, gratuita y auditable para monitorear Walt Disney World mediante GitHub Free, GitHub Actions, GitHub Pages y Telegram.

## Estado actual

```text
Fase 0: APROBADA
Promociones: OPERATIVAS
Centro de configuración: OPERATIVO con Dashboard v2.3
Apertura de ventas: IMPLEMENTADA
Disponibilidad real: IMPLEMENTADA, pendiente de validar la primera corrida productiva v1.5
Histórico por consulta y gráficos: IMPLEMENTADOS
```

## Centro de configuración

Cada viaje admite:

- destino operativo (`WALT_DISNEY_WORLD`);
- ventanas de fechas y noches;
- pasajeros y edades;
- hoteles prioritarios y alternativos desde un catálogo amigable;
- entradas y plan de comidas;
- promociones y audiencias a vigilar;
- umbrales de baja de precio;
- días y horarios de monitoreo en `America/Argentina/Buenos_Aires`;
- Telegram activado o desactivado por viaje.

El modelo ya contiene el campo destino, pero el único recolector productivo de esta versión es Walt Disney World. Email continúa fuera de alcance, como etapa posterior.

## Disponibilidad e histórico

Cuando Disney habilita una ventana, el monitor registra disponibilidad, tipo de habitación cuando puede extraerlo y precio total. Cada consulta saludable genera observaciones append-only en:

```text
data/history/prices/<profileId>/<AAAA-MM>.jsonl
```

El dashboard consolida series por combinación de viaje, fecha, hotel, habitación y paquete, con:

- precio anterior;
- precio actual;
- variación;
- mínimo y máximo;
- cantidad de consultas;
- puntos para gráficos.

## Horarios

Los workflows se despiertan en cuatro franjas compatibles con GitHub Actions: 03, 09, 15 y 21 h de Buenos Aires. Cada viaje filtra cuáles de esas franjas utiliza. Las ejecuciones manuales no quedan bloqueadas por el horario.

## Archivos principales

- `config/trips.json`: viajes y preferencias personales. No se reemplaza con este update.
- `config/destinations.json`: catálogo de destinos y hoteles.
- `config/monitoring.json`: controles globales de seguridad y costo.
- `data/current/dashboard.json`: contrato consolidado para el frontend.
- `data/history/prices/`: histórico append-only de cada consulta.

## Seguridad y costo

No hay proxies, bypass de CAPTCHA, reservas, inicios de sesión ni pagos automatizados. Todo funciona dentro de GitHub Free y Telegram.

## Instalación

Seguir [INSTALAR_V1_5.md](INSTALAR_V1_5.md).

## Validación local

```bash
npm run typecheck
npm test
npm run validate-config
```
## Consulta manual de todas las fechas

Desde v1.6.0, `npm run availability-all` recorre todas las fechas del perfil indicado por `SENTINEL_AVAILABILITY_PROFILE_ID`. El workflow manual permite elegir entre todas las fechas o una sola prioridad. La programación automática conserva la estrategia de bajo consumo.

