# Changelog

## 1.6.0 — Consulta completa de todas las fechas

- Nueva ejecución manual `availability-all` que recorre todas las ventanas del viaje en orden de prioridad.
- GitHub Actions permite elegir `all_windows` o `single_window`.
- Una sola ejecución conserva un resultado individual por cada fecha y genera un resumen agregado.
- El modo seguro sigue desactivando Telegram y evita modificar el circuito productivo.
- La ejecución programada conserva la estrategia de bajo consumo existente.

## 1.5.6 — Menor tarifa nocturna reservable

- Selecciona la menor tarifa por noche publicada en la tarjeta exacta del hotel.
- Excluye importes de ahorro como `Save $X Avg/Night`.
- Diferencia tarifa estándar de tarifa promocional vigente.
- Añade regresión con el artifact real 30837979208.
- El dashboard publica backend `1.5.6`.


## 1.5.5 — Asociación estricta de tarjetas y saneamiento de precios

- Corrige el artifact real `availability-30825047889`: el candidato agregado de toda la lista ya no puede reemplazar la tarjeta individual de un hotel.
- Prioriza la tarjeta que contiene el enlace oficial exacto del resort y descarta contenedores con múltiples hoteles.
- Un hotel `UNAVAILABLE_CONFIRMED` o `UNKNOWN` nunca conserva precios aunque el DOM contenga importes de otras tarjetas.
- Una tarjeta que mezcla indisponibilidad explícita y precio queda `UNKNOWN` por evidencia contradictoria.
- El histórico conserva la observación operativa, pero solo genera puntos de precio para `AVAILABLE_CONFIRMED`.
- Los registros históricos contaminados de versiones anteriores dejan de alimentar gráficos, mínimos y precios actuales sin borrar el historial.
- Agrega una prueba de regresión basada en los 43 candidatos reales del run `30825047889`.
- El dashboard publica backend `1.5.5`.

## 1.5.4 — Evidencia funcional de disponibilidad y precios

- Evita confirmar disponibilidad cuando solo se encuentra el nombre del hotel.
- Incorpora estados `AVAILABLE_CONFIRMED`, `UNAVAILABLE_CONFIRMED` y `UNKNOWN`.
- Los estados `UNKNOWN` no generan apariciones, desapariciones ni alertas.
- Extrae por separado total de estadía y tarifa por noche.
- Conserva observaciones de validación degradadas sin tocar Telegram ni el circuito productivo.
- Las validaciones manuales guardan captura, HTML, texto visible y candidatos del parser.
- El dashboard publica backend `1.5.4`.
- Amplía selectores de tarjetas de hoteles.

# 1.5.2 - 2026-08-02

- Agrega selección manual de perfil y prioridad de ventana al workflow de disponibilidad.
- Incorpora modo de validación técnica para perfiles TEST sin Telegram ni impacto en el circuito o rotación productivos.
- Corrige la versión publicada en dashboard.json.
- Añade pruebas de selección y validación de parámetros manuales.

# Changelog

## 1.5.1 - 2026-08-02

- Corrige la clasificación de fechas futuras todavía fuera de la ventana de venta.
- Evita reportar `FAILED_STRUCTURAL` cuando Disney rechaza una fecha futura con el formato oficial `MM/DD/YYYY`.
- Devuelve `NOT_OPEN` con salud `HEALTHY` para la vigilancia de apertura.
- Amplía el calendario para overlays globales y Web Components, en inglés y español.
- Navega meses hasta el objetivo y detecta el límite real del calendario.
- Agrega selectores españoles de inputs, botones y mensajes de fecha no procesable.
- Evita informar una línea base silenciosa cuando la corrida terminó con falla técnica.
- Agrega 3 pruebas; total backend: 62 pruebas aprobadas.

## 1.5.0 - 2026-08-02

- Completa el centro de configuración con destino, catálogo de hoteles, días, horarios y Telegram por viaje.
- Conserva compatibilidad automática con perfiles v1.4 sin los campos nuevos.
- Ejecuta cron en cuatro franjas y filtra cada viaje según hora local de Buenos Aires.
- Mantiene las ejecuciones manuales fuera del filtro horario.
- Registra una observación append-only por cada resultado de disponibilidad de una consulta saludable.
- Genera series por viaje, fecha, hotel, habitación y paquete.
- Publica precio anterior, actual, variación, mínimo, máximo y puntos en `dashboard.json`.
- Extrae tipo de habitación cuando Disney lo expone de forma estructurable.
- Permite desactivar Telegram por viaje sin perder el evento ni el histórico.
- Incorpora catálogo de 30 hoteles de Walt Disney World con nombres amigables.
- Agrega pruebas de programación e histórico; total backend: 59 pruebas aprobadas.

## 1.4.0 - 2026-08-02

- Activa `AVAILABILITY_LIMITED` como siguiente etapa productiva.
- Vigila la primera ventana real hasta que Disney abra ventas.
- Excluye perfiles TEST de disponibilidad productiva.
- Rota automáticamente todas las ventanas después de la apertura.
- Envía una única alerta de apertura y evita una ráfaga inicial de hoteles/precios.
- Corrige la línea base de precios y el rearme de nuevos mínimos históricos.
- Cierra Fase 0 como `APROBADO` en el contrato del dashboard.
- Actualiza Telegram para apertura de ventas.
- Agrega 55 pruebas automatizadas en total.

## 1.3.5 - 2026-08-02

- Aísla el contenido funcional de cada oferta y excluye navegación, pie de página y promociones relacionadas.
- Corrige la clasificación de categoría y audiencia, incluyendo residentes de Florida y ofertas generales.
- Extrae rangos de fechas con sintaxis española (`del 17 de mayo al 3 de octubre de 2026`).
- Limita porcentajes y precios al encabezado, descripción y bloques funcionales de ahorro.
- Agrega estado semántico por oferta y evita calcular relevancia cuando faltan datos esenciales.
- Reemplaza silenciosamente la línea base al migrar al parser 1.3.5.
- Actualiza backend, collector y parser a 1.3.5.

## 1.3.4 - 2026-08-02

- Corrige la mezcla de enlaces históricos/internos que producía lecturas variables de 80 y 29 candidatos.
- Prioriza tarjetas visibles del índice y payloads estructurados individuales.
- Agrega verificación DOM estable en una misma carga.
- Excluye bundles JavaScript de la extracción de promociones.
- Actualiza backend y collector a 1.3.4.

## 1.3.3 - 2026-08-02

- Fija el índice productivo en la ruta oficial `es-us` para evitar respuestas geográficas ambiguas del endpoint sin locale.
- Amplía el reconocimiento del total declarado por Disney a variantes de texto adicionales.
- Cuando Disney no expone el total, exige dos lecturas independientes con el mismo conjunto de al menos dos ofertas.
- Distingue integridad por total declarado (`DECLARED_COUNT`) e integridad por conjunto repetido (`STABLE_REPEATED_SET`).
- Mantiene el rechazo de líneas base de una sola oferta sin total verificable.
- Actualiza `dashboard.json` y el estado persistido a backend/collector 1.3.3.

## 1.3.2 - 2026-08-02

- Valida la cantidad de ofertas declarada por Disney contra la cantidad de enlaces extraídos.
- Amplía la recolección a enlaces DOM, atributos de navegación, HTML renderizado y respuestas de red.
- Expande contenido diferido y botones de carga adicional antes de cerrar el índice.
- Evita establecer líneas base parciales.
- Migra silenciosamente la línea base incompleta creada por v1.3.1, sin generar falsas altas por Telegram.
- Guarda captura y HTML cuando la recolección del índice es incompleta.
- Reintenta con Chrome los detalles que fallen por HTTP.
- Actualiza `dashboard.json` con versión backend 1.3.2.

## 1.3.1 - 2026-08-02

- Corrige el monitor de promociones cuando el índice oficial entrega un HTML inicial sin las tarjetas renderizadas.
- Agrega fallback controlado con Playwright y Chrome del sistema para renderizar el índice y los detalles oficiales.
- Migra el workflow de promociones a `windows-latest`, coherente con el runtime validado en Fase 0.
- Agrega evidencia diagnóstica de promociones ante fallas de renderizado.
- Mantiene la primera línea base silenciosa y la persistencia previa sin sobrescribir historial.

## 1.3.0 - Motor de Promociones productivo
- Cierra Fase 0 y cambia el modo inicial a `PROMOTIONS_ONLY`.
- Agrega clasificación por tipo, audiencia, fechas, hoteles, ahorro y puntaje de relevancia.
- Incorpora línea base silenciosa para evitar alertar todas las promociones existentes.
- Confirma retiros solo después de dos ausencias saludables consecutivas.
- Mejora los mensajes de Telegram con condiciones funcionales de la oferta.
- Genera `data/current/dashboard.json` consolidado después de cada ejecución.
- Mantiene compatibilidad del frontend mediante fallback a archivos por perfil.
- Deja Fase 0 únicamente bajo ejecución manual.
- Agrega preferencias de promociones por viaje y 36 pruebas backend.

## 1.2.10 - Notificación Telegram por cada corrida de Fase 0
- Agrega `phase0.notifyEveryRun` para habilitar o deshabilitar el seguimiento operativo desde configuración.
- Envía un único resumen por cada corrida efectivamente ejecutada, con número de corrida, resultado, salud, observaciones, duración y acumulado de la tanda.
- Incluye enlace directo a la ejecución de GitHub Actions cuando está disponible.
- Evita duplicar alertas técnicas y de cierre cuando el resumen por corrida está habilitado.
- Mantiene las corridas omitidas por espaciado o por configuración sin notificación.

## 1.2.9 - Fase 0 neutral para componentes deshabilitados
- La Fase 0 respeta `promotionsEnabled=false` del perfil de prueba y no clasifica como falla una fuente que fue deshabilitada explícitamente.
- Mantiene la validación de disponibilidad como objetivo principal de la tanda técnica.
- Mejora la extracción de enlaces de promociones para rutas relativas y enlaces modernos del índice oficial.
- Conserva diagnósticos explícitos para distinguir componente omitido de componente fallido.

## 1.2.8 - Botón de búsqueda en Web Components
- Reconoce los controles reales `wdpr-button` usados por Disney en Resorts.
- Agrega fallback por rol accesible para `Find Resorts` y `Check Availability`.
- Evita intentar clic sobre controles con `aria-disabled=true` o atributo `disabled`.
- Registra el selector o rol exacto utilizado para iniciar la búsqueda.

## 1.2.6 - Compatibilidad de identidad HTTP/Chrome
- La ejecución real ahora usa el mismo User-Agent de Chrome normal que aprobó el diagnóstico v1.2.4.
- El User-Agent se deriva de la versión real de Google Chrome instalada en el runner Windows.
- Se elimina el token `HeadlessChrome` de la navegación para evitar la negociación HTTP/2 incompatible observada.
- Las consultas HTTP reemplazan automáticamente el User-Agent técnico heredado `DisneySentinel/1.0` por uno de navegador compatible.
- No se agregan proxies, stealth, resolución de CAPTCHA ni bypasses de controles.

## 1.2.5

- Fase 0 y disponibilidad migradas a `windows-latest`.
- Uso explícito de Google Chrome instalado en el runner mediante `channel: chrome`.
- Eliminada la descarga de Chromium en esos workflows.
- Espera adicional de DOM y contenido para páginas Disney que entregan el documento de forma diferida.
- Diagnóstico de navegador registrado en cada corrida.
- Control manual migrado a Windows para que la opción `availability` use el mismo runtime validado.

## 1.2.0 — 2026-07-30

### Agregado

- Frontend visual independiente `disney-sentinel-dashboard`.
- Diseño responsive para escritorio y móvil.
- PWA instalable desde Safari/Chrome.
- Dashboard de resumen, viajes, disponibilidad, promociones, operación y actividad.
- CRUD completo de viajes desde el frontend.
- Control de variables `ENABLE_*` y `TELEGRAM_DRY_RUN`.
- Cambio de modo y configuración de Fase 0.
- Ejecución manual de workflows.
- Lectura de ejecuciones de GitHub Actions y alertas pendientes.
- Token de sesión y persistencia cifrada opcional con PBKDF2 + AES-GCM.
- Control de concurrencia mediante SHA de GitHub Contents API.
- Workflow `sync-config-reports.yml`.
- Modo demostración.

### Conservado

- GitHub Issue Forms como fallback.
- Compatibilidad completa con `config/trips.json` v1.1.
- Estado seguro y monitores desactivados.

## 1.1.0 — 2026-07-30

- Registro multi-viaje, Issue Forms, cambio rápido de fechas y apertura de ventas por ventana.
