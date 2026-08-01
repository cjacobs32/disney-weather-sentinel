# Arquitectura — Disney Weather Sentinel 4.0

## Principio de veracidad

El sistema separa tres conceptos:

1. **Observación:** dato medido por una estación física.
2. **Pronóstico:** predicción emitida antes de la fecha objetivo.
3. **Referencia modelada:** tendencia o climatología para planificación.

No se etiqueta una reconstrucción modelada como “lo que ocurrió realmente”.

## Flujo histórico

```text
Frontend o GitHub Actions
        ↓
NOAA/NCEI Access Data Service
        ↓
GHCN-Daily Daily Summaries
        ↓
USW00012815 · Orlando International Airport
        ↓
Normalización + cobertura + faltantes
        ↓
JSON completo + informe + visualización
```

Variables principales:

- `TMAX`: máxima diaria observada.
- `TMIN`: mínima diaria observada.
- `PRCP`: precipitación diaria observada.
- `AWND`: viento medio diario.
- `WSF2` / `WSF5`: viento rápido observado.
- atributos GHCN para trazas y banderas de calidad.

## Rango de fechas

No hay una validación de cantidad máxima de días. El único control estructural es que la fecha final no sea anterior a la inicial.

Las observaciones se descargan en bloques por año y se consolidan por fecha. Para períodos extensos:

- el almacenamiento conserva el detalle diario;
- el informe y frontend pueden resumir por mes;
- el gráfico aplica muestreo exclusivamente visual.

## Flujo futuro

```text
Open-Meteo Forecast
Open-Meteo Seasonal
Open-Meteo ERA5-Land para referencia climática
        ↓
Pronóstico diario + tendencia + contexto histórico
```

La ausencia de un pronóstico diario para una fecha lejana no se completa artificialmente.

## Comparación

```text
Pronóstico guardado para Disney
        versus
Observación oficial de KMCO
```

La comparación informa la estación y la distancia aproximada. La precipitación requiere cautela por su variabilidad espacial.

## Persistencia

- `data/queries/historical/`
- `data/queries/future/`
- `data/forecast_snapshots/`
- `data/comparisons/`
- `reports/`
- `docs/generated/`

No se utiliza base de datos.

## Costos y seguridad

- Sin API keys meteorológicas.
- Sin tarjeta.
- Sin backend permanente.
- Sin cron activo.
- GitHub Pages y GitHub Actions manual.
