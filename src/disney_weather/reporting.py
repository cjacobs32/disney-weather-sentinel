from __future__ import annotations

from statistics import mean

from .models import ComparisonReport, ForecastSnapshot, FutureOutlook, PeriodWeather


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
    return "—" if value is None else f"{value:.{digits}f}"


def _condition(code: int | None) -> str:
    return "—" if code is None else WEATHER_CODES.get(code, f"Código {code}")


def render_historical(result: PeriodWeather) -> str:
    average_max = mean(day.temperature_max_c for day in result.daily)
    average_min = mean(day.temperature_min_c for day in result.daily)
    precipitation = sum(day.precipitation_sum_mm for day in result.daily)
    rainy_days = sum(day.precipitation_sum_mm >= 0.1 for day in result.daily)
    lines = [
        "# Disney Weather Sentinel — Histórico del período",
        "",
        f"- **Período:** {result.requested_start} al {result.requested_end}",
        f"- **Ubicación:** {result.location_name}",
        f"- **Fuente:** {result.provider} / {result.dataset}",
        f"- **Promedio de máximas:** {average_max:.1f} °C",
        f"- **Promedio de mínimas:** {average_min:.1f} °C",
        f"- **Precipitación acumulada:** {precipitation:.1f} mm",
        f"- **Días con precipitación:** {rainy_days} de {len(result.daily)}",
        "",
        "| Fecha | Condición | Máx. °C | Mín. °C | Lluvia mm | Horas precip. | Viento km/h |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for day in result.daily:
        lines.append(
            f"| {day.date} | {_condition(day.weather_code)} | "
            f"{day.temperature_max_c:.1f} | {day.temperature_min_c:.1f} | "
            f"{day.precipitation_sum_mm:.1f} | {_fmt(day.precipitation_hours)} | "
            f"{_fmt(day.wind_speed_max_kmh)} |"
        )
    lines.extend(
        [
            "",
            "> El histórico es una referencia meteorológica modelada; no es una medición de una estación dentro de Walt Disney World.",
            "",
        ]
    )
    return "\n".join(lines)


def render_forecast(snapshot: ForecastSnapshot) -> str:
    lines = [
        "# Disney Weather Sentinel — Captura de pronóstico",
        "",
        f"- **Período:** {snapshot.requested_start} al {snapshot.requested_end}",
        f"- **Capturado:** {snapshot.captured_at_utc.isoformat()}",
        f"- **Ubicación:** {snapshot.location_name}",
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
            f"| {day.date} | {_condition(day.weather_code)} | "
            f"{day.temperature_max_c:.1f} | {day.temperature_min_c:.1f} | "
            f"{day.precipitation_sum_mm:.1f} | {probability} | "
            f"{_fmt(day.wind_speed_max_kmh)} |"
        )
    lines.extend(
        [
            "",
            "> Esta captura es inmutable y permite comparar posteriormente el pronóstico con lo ocurrido.",
            "",
        ]
    )
    return "\n".join(lines)


def render_future(result: FutureOutlook) -> str:
    lines = [
        "# Disney Weather Sentinel — Perspectiva futura",
        "",
        f"- **Período solicitado:** {result.requested_start} al {result.requested_end}",
        f"- **Pronóstico diario disponible hasta:** {result.forecast_available_through}",
        f"- **Años de referencia climática:** {', '.join(map(str, result.climate_reference_years))}",
        "",
    ]
    if result.live_forecast:
        lines.extend(
            [
                "## Pronóstico meteorológico vigente",
                "",
                "| Fecha | Máx. °C | Mín. °C | Lluvia mm | Prob. precip. |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for day in result.live_forecast:
            probability = (
                "—"
                if day.precipitation_probability_max_pct is None
                else f"{day.precipitation_probability_max_pct:.0f}%"
            )
            lines.append(
                f"| {day.date} | {day.temperature_max_c:.1f} | "
                f"{day.temperature_min_c:.1f} | {day.precipitation_sum_mm:.1f} | "
                f"{probability} |"
            )
        lines.append("")

    if result.seasonal_estimate:
        lines.extend(
            [
                "## Tendencia estacional por ensamble",
                "",
                "| Fecha | Máx. media (P10–P90) | Mín. media (P10–P90) | Lluvia media / P90 |",
                "|---|---:|---:|---:|",
            ]
        )
        for day in result.seasonal_estimate:
            lines.append(
                f"| {day.date} | {_fmt(day.temperature_max_mean_c)} "
                f"({_fmt(day.temperature_max_p10_c)}–{_fmt(day.temperature_max_p90_c)}) °C | "
                f"{_fmt(day.temperature_min_mean_c)} "
                f"({_fmt(day.temperature_min_p10_c)}–{_fmt(day.temperature_min_p90_c)}) °C | "
                f"{_fmt(day.precipitation_mean_mm)} / {_fmt(day.precipitation_p90_mm)} mm |"
            )
        lines.append("")

    lines.extend(
        [
            "## Referencia climática de años anteriores",
            "",
            "| Fecha objetivo | Máx. media (P10–P90) | Mín. media (P10–P90) | Lluvia media / P90 | Frecuencia lluvia |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for day in result.climate_reference:
        lines.append(
            f"| {day.date} | {day.temperature_max_mean_c:.1f} "
            f"({day.temperature_max_p10_c:.1f}–{day.temperature_max_p90_c:.1f}) °C | "
            f"{day.temperature_min_mean_c:.1f} "
            f"({day.temperature_min_p10_c:.1f}–{day.temperature_min_p90_c:.1f}) °C | "
            f"{day.precipitation_mean_mm:.1f} / {day.precipitation_p90_mm:.1f} mm | "
            f"{day.rain_frequency_pct:.0f}% |"
        )
    lines.extend(["", "## Lectura correcta", ""])
    lines.extend(f"- {note}" for note in result.notes)
    lines.append("")
    return "\n".join(lines)


def render_comparison(report: ComparisonReport) -> str:
    max_mae = mean(row.temperature_max_error_c.absolute for row in report.daily)
    min_mae = mean(row.temperature_min_error_c.absolute for row in report.daily)
    rain_mae = mean(row.precipitation_error_mm.absolute for row in report.daily)
    rain_accuracy = 100 * mean(1.0 if row.rain_event_correct else 0.0 for row in report.daily)
    lines = [
        "# Disney Weather Sentinel — Pronóstico versus realidad",
        "",
        f"- **Período:** {report.requested_start} al {report.requested_end}",
        f"- **Pronóstico capturado:** {report.snapshot_captured_at_utc.isoformat()}",
        f"- **Fuente de realidad:** {report.actual_dataset}",
        f"- **MAE máxima:** {max_mae:.2f} °C",
        f"- **MAE mínima:** {min_mae:.2f} °C",
        f"- **MAE precipitación:** {rain_mae:.2f} mm",
        f"- **Acierto de evento de lluvia:** {rain_accuracy:.1f}%",
        "",
        "| Fecha | Anticipación | Máx. pron./real | Mín. pron./real | Lluvia pron./real | Acierto lluvia |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for row in report.daily:
        lines.append(
            f"| {row.target_date} | {row.lead_days} días | "
            f"{row.forecast.temperature_max_c:.1f}/{row.actual.temperature_max_c:.1f} °C | "
            f"{row.forecast.temperature_min_c:.1f}/{row.actual.temperature_min_c:.1f} °C | "
            f"{row.forecast.precipitation_sum_mm:.1f}/{row.actual.precipitation_sum_mm:.1f} mm | "
            f"{'Sí' if row.rain_event_correct else 'No'} |"
        )
    lines.append("")
    return "\n".join(lines)
