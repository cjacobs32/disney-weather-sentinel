# Arquitectura técnica

## Principios

1. Costo monetario nulo como restricción de diseño, no como optimización posterior.
2. Ejecución bajo demanda; ningún recolector permanente es necesario.
3. Separación explícita entre pronóstico, tendencia y climatología.
4. Capturas inmutables para comparaciones reproducibles.
5. Degradación controlada: si falla la API estacional, la consulta futura conserva la referencia climática.
6. Sin credenciales en el navegador.

## Flujos

### Consulta histórica

```text
Usuario → frontend o workflow manual
        → Historical Weather API con selección automática del mejor histórico disponible
        → resumen + tabla + JSON/Markdown

Referencia climática multianual
        → ERA5-Land para mantener consistencia entre años
```

### Consulta futura

```text
Fecha dentro de 16 días ───────────────→ pronóstico diario
Fecha entre 16 días y ~7 meses ───────→ tendencia de ensamble
Todas las fechas ─────────────────────→ referencia de años anteriores
                                         ↓
                               perspectiva consolidada
```

### Captura y comparación

```text
Antes del período
  pronóstico vigente → snapshot con timestamp → almacenamiento local o Git

Después del período
  snapshot + histórico → errores diarios → métricas agregadas
```

## Persistencia

Los nombres incluyen período y timestamp para evitar sobrescrituras accidentales. Las capturas son append-only. Los históricos o perspectivas pueden repetirse porque representan consultas efectuadas en momentos diferentes.

## Seguridad

- El frontend solo accede a endpoints públicos sin autenticación.
- No existe PAT, API key ni secreto en JavaScript.
- GitHub Actions usa exclusivamente el `GITHUB_TOKEN` efímero del workflow.
- Los permisos del workflow se limitan a `contents: write`.
- No se usan eventos peligrosos como `pull_request_target`.

## Disponibilidad

La aplicación estática continúa funcionando aunque GitHub Actions no se ejecute. La consulta depende de la disponibilidad de Open-Meteo. Las capturas locales continúan accesibles sin GitHub, pero la comparación necesita acceso a la API histórica.

## Escalabilidad

La carga esperada es mínima: una consulta futura de 10 años realiza aproximadamente 12 solicitudes — una de pronóstico, una estacional y diez históricas. Esto está muy por debajo de los límites normales del proveedor para uso individual no comercial.

## Decisiones descartadas

### Base de datos cloud

No aporta valor para períodos de 15 días y agrega credenciales, políticas de suspensión y dependencia de un free tier comercial.

### Backend para el frontend

No es necesario porque Open-Meteo admite consultas públicas desde el navegador. Agregarlo obligaría a mantener hosting y autenticación.

### Disparar Actions desde GitHub Pages

Requeriría exponer o gestionar un token de GitHub, o construir un servicio OAuth intermedio. Se descarta para evitar una superficie de seguridad innecesaria. La persistencia en Git se inicia desde la interfaz oficial de Actions.

### Cron activo por defecto

No coincide con el caso de uso. El ejemplo opcional se entrega fuera del directorio de workflows para garantizar que esté desactivado.
