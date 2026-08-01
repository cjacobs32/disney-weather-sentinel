# Disney Weather Sentinel 4.0

Aplicación de costo cero para consultar el tiempo de Orlando bajo demanda, guardar pronósticos y compararlos posteriormente con observaciones oficiales.

## Cambios de esta versión

1. **Histórico observado:** el modo histórico usa NOAA/NCEI GHCN-Daily, estación Orlando International Airport (`USW00012815`, KMCO). Ya no presenta un reanálisis modelado como si fuera una medición real.
2. **Rango libre:** no existe un límite artificial de 15 días. Se puede consultar un día, un mes, un año o varios años. Para períodos extensos, la interfaz resume por mes y el JSON conserva todos los registros diarios.

## Qué significa “observado”

Los datos históricos son mediciones de una estación física:

- Fuente: NOAA / NCEI.
- Dataset: GHCN-Daily Daily Summaries.
- Estación: Orlando International Airport, KMCO.
- Identificador: `USW00012815`.
- Distancia aproximada a Walt Disney World: 24,5 km.

No son mediciones dentro de Magic Kingdom, EPCOT, Hollywood Studios o Animal Kingdom. La temperatura suele ser una referencia útil para Orlando; la lluvia puede variar considerablemente entre KMCO y Disney.

Los valores ausentes quedan como **Sin dato**. Una traza de precipitación se conserva como **Traza**. No se reemplazan faltantes con cero ni con un modelo.

## Stack gratuito

- GitHub Pages para el frontend.
- GitHub Actions solo bajo demanda.
- NOAA/NCEI Access Data Service sin API key.
- Open-Meteo sin API key para pronóstico, tendencia estacional y referencia climática.
- Archivos JSON y Markdown versionados en Git.
- Sin servidor, base de datos, tarjeta ni cron activo.

## Estructura

```text
.github/workflows/weather-query.yml  Workflow manual
docs/                                Frontend para GitHub Pages
src/disney_weather/                  Motor Python
data/                                Resultados versionados
reports/                             Informes Markdown
tests/                               Pruebas
```

## Publicación rápida

1. Crear un repositorio público vacío.
2. Subir el contenido de esta carpeta a la raíz del repositorio.
3. Ir a `Settings → Actions → General → Workflow permissions` y elegir `Read and write permissions`.
4. Ir a `Settings → Pages`.
5. Elegir `Deploy from a branch`.
6. Seleccionar rama `main` y carpeta `/docs`.
7. Abrir la URL de GitHub Pages cuando termine la publicación.

No hay Secrets que configurar.

## Uso del frontend

Elegir:

- **Automática según las fechas**.
- **Observado: qué midió una estación oficial**.
- **Futuro: mejor información disponible**.
- **Capturar pronóstico para comparar después**.

Luego completar `Desde`, `Hasta` y presionar **Analizar período**.

### Períodos históricos largos

La consulta se divide internamente por años para reducir el tamaño de cada llamada a NOAA. Si el período supera 180 días:

- la pantalla muestra un resumen mensual;
- el gráfico usa una muestra visual;
- el JSON descargado mantiene todos los días devueltos.

La estación tiene cobertura desde 1952. Si se pide una fecha anterior, el sistema acepta el rango y declara las fechas sin cobertura.

### Fechas futuras

El selector permite cualquier rango, pero la disponibilidad meteorológica depende de los modelos:

- hasta aproximadamente 16 días: pronóstico diario;
- después: tendencia estacional, cuando está disponible;
- cualquier fecha: referencia climática basada en años anteriores.

El sistema no inventa valores diarios para fechas fuera del horizonte.

## Uso desde GitHub Actions

Abrir:

```text
Actions → Consulta meteorológica Disney → Run workflow
```

Operaciones:

- `historical`: observaciones NOAA/NCEI.
- `future`: pronóstico, tendencia y referencia climática.
- `capture`: guarda el pronóstico vigente.
- `compare`: compara capturas con observaciones de KMCO.

No existe `schedule:` activo.

## Validación local

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest -q
```

La versión entregada incluye siete pruebas unitarias.
