from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .models import ComparisonReport, DailyWeather, ForecastSnapshot, FutureOutlook, PeriodWeather


WEATHER_CODES: dict[int, str] = {
    0: "Despejado",
    1: "Mayormente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con escarcha",
    51: "Llovizna leve",
    53: "Llovizna",
    55: "Llovizna intensa",
    61: "Lluvia leve",
    63: "Lluvia",
    65: "Lluvia intensa",
    80: "Chaparrones leves",
    81: "Chaparrones",
    82: "Chaparrones intensos",
    95: "Tormenta",
    96: "Tormenta con granizo leve",
    99: "Tormenta con granizo",
}


def _fmt(value: float | None, digits: int = 1) -> str:
    return "Sin dato" if value is None else f"{value:.{digits}f}"


def _mean(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    return mean(usable) if usable else None


def _sum(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    return sum(usable) if usable else None


def _condition(code: int | None) -> str:
    return "—" if code is None else WEATHER_CODES.get(code, f"Código {code}")


def _rain(day: DailyWeather) -> str:
    if day.precipitation_trace:
        return "Traza"
    return f"{day.precipitation_sum_mm:.1f}" if day.precipitation_sum_mm is not None else "Sin dato"


def _monthly_rows(days: list[DailyWeather]) -> list[str]:
    grouped: dict[str, list[DailyWeather]] = defaultdict(list)
    for day in days:
        grouped[day.date.strftime("%Y-%m")].append(day)
    output = [
        "| Mes | Días devueltos | Máx. media °C | Mín. media °C | Lluvia mm | Días lluvia | Trazas |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for month, rows in sorted(grouped.items()):
        measurable = [
            day.precipitation_sum_mm
            for day in rows
            if day.precipitation_sum_mm is not None
        ]
        output.append(
            f"| {month} | {len(rows)} | {_fmt(_mean([d.temperature_max_c for d in rows]))} | "
            f"{_fmt(_mean([d.temperature_min_c for d in rows]))} | {_fmt(sum(measurable) if measurable else None)} | "
            f"{sum(value >= 0.1 for value in measurable)} | {sum(d.precipitation_trace for d in rows)} |"
        )
    return output


def render_historical(result: PeriodWeather) -> str:
    average_max = _mean([day.temperature_max_c for day in result.daily])
    average_min = _mean([day.temperature_min_c for day in result.daily])
    measured_rain = [
        day.precipitation_sum_mm
        for day in result.daily
        if day.precipitation_sum_mm is not None
    ]
    precipitation = sum(measured_rain) if measured_rain else None
    rainy_days = sum(value >= 0.1 for value in measured_rain)
    trace_days = sum(day.precipitation_trace for day in result.daily)
    lines = [
        "# Disney Weather Sentinel — Observaciones oficiales",
        "",
        f"- **Período solicitado:** {result.requested_start} al {result.requested_end}",
        f"- **Destino de referencia:** {result.location_name}",
        f"- **Estación observadora:** {result.station_name} ({result.station_id})",
        f"- **Distancia aproximada a Disney:** {result.station_distance_from_target_km:.1f} km",
        f"- **Fuente:** NOAA / NCEI — {result.dataset}",
        f"- **Cobertura devuelta:** {result.returned_days} de {result.requested_days} días",
        f"- **Promedio de máximas observadas:** {_fmt(average_max)} °C",
        f"- **Promedio de mínimas observadas:** {_fmt(average_min)} °C",
        f"- **Precipitación observada acumulada:** {_fmt(precipitation)} mm",
        f"- **Días con lluvia medible:** {rainy_days}",
        f"- **Días con traza:** {trace_days}",
        "",
        "> Son observaciones de una estación física en Orlando International Airport. No son mediciones dentro de Walt Disney World; la lluvia puede variar localmente.",
        "",
    ]
    if result.missing_dates:
        lines.extend(
            [
                f"> **Cobertura incompleta:** faltan {len(result.missing_dates)} fechas. Los datos ausentes no fueron reemplazados por cero ni por un modelo.",
                "",
            ]
        )
    if len(result.daily) > 180:
        lines.extend(["## Resumen mensual", "", *_monthly_rows(result.daily), ""])
    else:
        lines.extend(
            [
                "| Fecha | Máx. °C | Mín. °C | Precipitación mm | Viento medio km/h | Viento máx. km/h | Calidad |",
                "|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for day in result.daily:
            quality = ", ".join(f"{key}:{value}" for key, value in day.quality_flags.items()) or "—"
            lines.append(
                f"| {day.date} | {_fmt(day.temperature_max_c)} | {_fmt(day.temperature_min_c)} | "
                f"{_rain(day)} | {_fmt(day.wind_speed_mean_kmh)} | {_fmt(day.wind_speed_max_kmh)} | {quality} |"
            )
        lines.append("")
    return "\n".join(lines)


def render_forecast(snapshot: ForecastSnapshot) -> str:
    lines = [
        "# Disney Weather Sentinel — Captura de pronóstico",
        "",
        f"- **Período:** {snapshot.requested_start} al {snapshot.requested_end}",
        f"- **Capturado:** {snapshot.captured_at_utc.isoformat()}",
        f"- **Ubicación pronosticada:** {snapshot.location_name}",
        "",
        "| Fecha | Condición | Máx. °C | Mín. °C | Lluvia mm | Prob. precip. | Viento km/h |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for day in snapshot.daily:
        probability = (
            "—"
            if day.precipitation_probability_max_pct is None
            else f"{day.precipitation_probability_max_pct:.0f}%"
        )
        lines.append(
            f"| {day.date} | {_condition(day.weather_code)} | {_fmt(day.temperature_max_c)} | "
            f"{_fmt(day.temperature_min_c)} | {_fmt(day.precipitation_sum_mm)} | {probability} | "
            f"{_fmt(day.wind_speed_max_kmh)} |"
        )
    return "\n".join(lines) + "\n"


def render_future(result: FutureOutlook) -> str:
    lines = [
        "# Disney Weather Sentinel — Perspectiva futura",
        "",
        f"- **Período solicitado:** {result.requested_start} al {result.requested_end}",
        f"- **Pronóstico diario disponible hasta:** {result.forecast_available_through}",
        f"- **Días con pronóstico diario:** {len(result.live_forecast)}",
        f"- **Días con tendencia estacional:** {len(result.seasonal_estimate)}",
        f"- **Días con referencia climática:** {len(result.climate_reference)}",
        "",
    ]
    if result.live_forecast:
        lines.extend(
            [
                "## Pronóstico diario vigente",
                "",
                "| Fecha | Condición | Máx. °C | Mín. °C | Lluvia mm | Prob. precip. |",
                "|---|---|---:|---:|---:|---:|",
            ]
        )
        for day in result.live_forecast:
            probability = (
                "—"
                if day.precipitation_probability_max_pct is None
                else f"{day.precipitation_probability_max_pct:.0f}%"
            )
            lines.append(
                f"| {day.date} | {_condition(day.weather_code)} | {_fmt(day.temperature_max_c)} | "
                f"{_fmt(day.temperature_min_c)} | {_fmt(day.precipitation_sum_mm)} | {probability} |"
            )
        lines.append("")
    if result.seasonal_estimate:
        lines.extend(
            [
                "## Tendencia estacional probabilística",
                "",
                "| Fecha | Máx. media P10–P90 | Mín. media P10–P90 | Lluvia media/P90 |",
                "|---|---:|---:|---:|",
            ]
        )
        for day in result.seasonal_estimate:
            lines.append(
                f"| {day.date} | {_fmt(day.temperature_max_mean_c)} "
                f"({_fmt(day.temperature_max_p10_c)}–{_fmt(day.temperature_max_p90_c)}) | "
                f"{_fmt(day.temperature_min_mean_c)} "
                f"({_fmt(day.temperature_min_p10_c)}–{_fmt(day.temperature_min_p90_c)}) | "
                f"{_fmt(day.precipitation_mean_mm)}/{_fmt(day.precipitation_p90_mm)} |"
            )
        lines.append("")
    lines.extend(
        [
            "> El rango seleccionado puede ser extenso, pero la disponibilidad de pronóstico depende del horizonte de los modelos. No se inventan días no cubiertos.",
            "",
        ]
    )
    return "\n".join(lines)


def render_comparison(report: ComparisonReport) -> str:
    max_errors = [
        row.temperature_max_error_c.absolute
        for row in report.daily
        if row.temperature_max_error_c is not None
    ]
    min_errors = [
        row.temperature_min_error_c.absolute
        for row in report.daily
        if row.temperature_min_error_c is not None
    ]
    rain_errors = [
        row.precipitation_error_mm.absolute
        for row in report.daily
        if row.precipitation_error_mm is not None
    ]
    rain_events = [row.rain_event_correct for row in report.daily if row.rain_event_correct is not None]
    lines = [
        "# Disney Weather Sentinel — Pronóstico vs. observación",
        "",
        f"- **Período:** {report.requested_start} al {report.requested_end}",
        f"- **Captura:** {report.snapshot_captured_at_utc.isoformat()}",
        f"- **Observación real:** {report.actual_station_name} ({report.actual_station_id})",
        f"- **Distancia a Disney:** {report.actual_station_distance_from_target_km:.1f} km",
        f"- **MAE máxima:** {_fmt(mean(max_errors) if max_errors else None, 2)} °C",
        f"- **MAE mínima:** {_fmt(mean(min_errors) if min_errors else None, 2)} °C",
        f"- **MAE precipitación:** {_fmt(mean(rain_errors) if rain_errors else None, 2)} mm",
        f"- **Acierto lluvia:** {_fmt(100 * sum(rain_events) / len(rain_events) if rain_events else None, 1)}%",
        "",
        "| Fecha | Anticipación | Máx. pron./obs. | Mín. pron./obs. | Lluvia pron./obs. | Acierto lluvia |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in report.daily:
        rain_correct = "Sin dato" if row.rain_event_correct is None else ("Sí" if row.rain_event_correct else "No")
        lines.append(
            f"| {row.target_date} | {row.lead_days} días | "
            f"{_fmt(row.forecast.temperature_max_c)}/{_fmt(row.actual.temperature_max_c)} °C | "
            f"{_fmt(row.forecast.temperature_min_c)}/{_fmt(row.actual.temperature_min_c)} °C | "
            f"{_fmt(row.forecast.precipitation_sum_mm)}/{_fmt(row.actual.precipitation_sum_mm)} mm | "
            f"{rain_correct} |"
        )
    lines.extend(
        [
            "",
            "> El pronóstico corresponde a las coordenadas de Walt Disney World y la observación a KMCO. La comparación de lluvia debe interpretarse con cautela por la variabilidad local.",
            "",
        ]
    )
    return "\n".join(lines)
