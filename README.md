# Disney Weather Sentinel 2.0

Sistema de costo cero para consultar el clima de Walt Disney World / Orlando por períodos de hasta 15 días. No funciona como un monitor permanente: el uso normal es manual, desde una interfaz web o desde GitHub Actions.

## Qué resuelve

1. **Histórico:** permite consultar qué ocurrió en un período pasado, por ejemplo del 1 al 15 de noviembre de 2025.
2. **Futuro:** muestra la mejor información disponible según la distancia de las fechas:
   - pronóstico meteorológico diario cuando la fecha está dentro de los próximos 16 días;
   - tendencia estacional de ensamble para fechas más lejanas, dentro del horizonte disponible;
   - referencia climática calculada con las mismas fechas de años anteriores.
3. **Captura:** conserva el pronóstico vigente antes de un viaje.
4. **Comparación:** cuando el período termina, cruza la captura guardada con el histórico de referencia y calcula errores.

## Componentes

```text
Navegador / GitHub Pages
  ├─ consulta directa a Open-Meteo
  ├─ capturas en almacenamiento local del navegador
  ├─ exportación/importación JSON
  └─ comparación interactiva

GitHub Actions — ejecución exclusivamente manual
  ├─ recibe operación y fechas
  ├─ ejecuta Python tipado
  ├─ genera JSON y Markdown
  ├─ muestra el informe en el resumen del workflow
  └─ versiona el resultado en Git

Persistencia
  ├─ data/queries/historical/
  ├─ data/queries/future/
  ├─ data/forecast_snapshots/
  ├─ data/comparisons/
  ├─ reports/
  └─ docs/generated/       última consulta visible en el frontend
```

No hay servidor, base de datos, API key ni proceso ejecutándose continuamente.

## Frontend

La aplicación estática se encuentra en `docs/` y no utiliza frameworks, CDN ni servicios externos adicionales.

### Publicarlo sin costo con GitHub Pages

Para garantizar costo cero con GitHub Free, usar un repositorio **público**:

1. Subir el contenido del proyecto a GitHub.
2. Abrir `Settings > Pages`.
3. En `Build and deployment`, elegir `Deploy from a branch`.
4. Seleccionar la rama principal y la carpeta `/docs`.
5. Guardar.

GitHub mostrará la URL del sitio. No hace falta crear un workflow de despliegue.

> GitHub Pages en repositorios privados depende del plan de GitHub. Si se quiere mantener el repositorio privado sin asumir costos, el frontend puede ejecutarse localmente.

### Ejecutarlo localmente

Desde la raíz del proyecto:

```bash
python -m http.server 8080 --directory docs
```

Abrir `http://localhost:8080`.

No conviene abrir `index.html` directamente con `file://`, porque algunos navegadores restringen consultas de red y archivos JavaScript locales.

### Persistencia del navegador

Las capturas creadas desde el frontend se guardan en `localStorage` del dispositivo y navegador actual. Por eso la interfaz permite:

- descargar cada captura como JSON;
- importar nuevamente una captura;
- comparar una captura cuando sus fechas ya finalizaron.

Para conservar una captura de forma centralizada y versionada, usar la operación manual `capture` de GitHub Actions.

## GitHub Actions manual

El workflow activo es:

```text
.github/workflows/weather-query.yml
```

No contiene `schedule` ni cron.

### Habilitar escritura de resultados

1. Abrir `Settings > Actions > General`.
2. Ir a `Workflow permissions`.
3. Seleccionar `Read and write permissions`.
4. Guardar.

El token utilizado es `GITHUB_TOKEN`, generado automáticamente por GitHub. No se configura ningún secret.

### Ejecutar una consulta

1. Abrir la pestaña `Actions`.
2. Seleccionar `Consulta meteorológica Disney`.
3. Pulsar `Run workflow`.
4. Completar:
   - `operation`;
   - `start_date`;
   - `end_date`;
   - `climate_years`.
5. Ejecutar.

Las operaciones disponibles son:

| Operación | Uso |
|---|---|
| `historical` | Saber qué ocurrió en un período pasado. |
| `future` | Obtener pronóstico, tendencia y referencia según disponibilidad. |
| `capture` | Guardar el pronóstico actual para fechas dentro del horizonte diario. |
| `compare` | Comparar las capturas existentes con lo ocurrido después del período. |

El período inclusivo no puede superar 15 días.

### Ejemplos

Histórico de noviembre de 2025:

```text
operation: historical
start_date: 2025-11-01
end_date: 2025-11-15
```

Perspectiva para noviembre de 2026:

```text
operation: future
start_date: 2026-11-01
end_date: 2026-11-15
climate_years: 10
```

Capturar un pronóstico antes del viaje:

```text
operation: capture
start_date: 2026-11-01
end_date: 2026-11-15
```

La captura solo funcionará cuando todas las fechas se encuentren dentro del horizonte diario disponible. Después de finalizar el viaje:

```text
operation: compare
start_date: 2026-11-01
end_date: 2026-11-15
```

## Ejecución por línea de comandos

Requiere Python 3.12 o superior:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
pip install -e ".[dev]"
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

Comandos:

```bash
disney-weather historical --start 2025-11-01 --end 2025-11-15

disney-weather future --start 2026-11-01 --end 2026-11-15 --climate-years 10

disney-weather capture --start 2026-11-01 --end 2026-11-15

disney-weather compare --start 2026-11-01 --end 2026-11-15
```

## Fuentes meteorológicas

El proveedor predeterminado es Open-Meteo y no requiere API key.

- **Pronóstico diario:** modelos operativos `best_match`, hasta 16 días según disponibilidad del modelo.
- **Histórico del período:** Historical Weather API con selección automática del mejor conjunto histórico disponible.
- **Histórico y climatología:** ERA5-Land, usado para referencias consistentes entre años.
- **Tendencia estacional:** ensambles ECMWF EC46/SEAS5 a través de la Seasonal Forecast API.

## Interpretación obligatoria

- Un pronóstico diario no existe para cualquier fecha futura. El sistema no inventa detalle diario fuera del horizonte disponible.
- La tendencia estacional es probabilística y de resolución regional. No permite afirmar que lloverá un día concreto.
- La referencia climática describe antecedentes de años anteriores, no el pronóstico del año consultado.
- El “clima real” del sistema es una referencia modelada. No es una medición de una estación física instalada dentro de Walt Disney World.
- La precipitación local puede diferir considerablemente dentro del área de Orlando.

## Automatización opcional

Se incluye un ejemplo desactivado en:

```text
examples/optional-scheduled-capture.yml.example
```

No se ejecuta mientras permanezca fuera de `.github/workflows/` y conserve la extensión `.example`. Solo debe copiarse y adaptarse si en algún momento se decide capturar automáticamente un período concreto.

## Costos y credenciales

| Componente | Costo | Tarjeta | Secret |
|---|---:|:---:|:---:|
| Open-Meteo no comercial dentro de límites | US$ 0 | No | No |
| Frontend estático local | US$ 0 | No | No |
| GitHub Pages en repositorio público | US$ 0 | No | No |
| GitHub Actions manual | Dentro de la asignación gratuita | No, si no se configura facturación | No |
| JSON y Markdown en Git | US$ 0 | No | No |

No agregar una tarjeta ni habilitar gasto adicional de Actions si la exigencia es impedir cualquier cargo.

## Validaciones

```bash
ruff check .
mypy src
pytest -q
node --check docs/assets/app.js
```

El workflow ejecuta Ruff, Mypy y Pytest antes de consultar datos o realizar commits.

## Estructura

```text
.github/workflows/weather-query.yml
src/disney_weather/
  cli.py
  config.py
  models.py
  provider.py
  reporting.py
  service.py
  storage.py
docs/
  index.html
  config.js
  assets/
    app.js
    styles.css
  generated/
data/
reports/
tests/
examples/
```
