from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any, Iterable

from .config import Settings
from .models import (
    ClimateDailyReference,
    ComparisonReport,
    DailyComparison,
    DailyWeather,
    ForecastSnapshot,
    FutureOutlook,
    MetricError,
    PeriodWeather,
    SeasonalDailyEstimate,
)
from .provider import WeatherProvider
from .storage import JsonRepository


JsonObject = dict[str, Any]


def _value(values: JsonObject, key: str, index: int) -> Any:
    series = values.get(key)
    if not isinstance(series, list) or index >= len(series):
        return None
    return series[index]


def _required_float(values: JsonObject, key: str, index: int) -> float:
    value = _value(values, key, index)
    if not isinstance(value, int | float):
        raise ValueError(f"Dato requerido ausente: daily.{key}[{index}]")
    return float(value)


def _optional_float(values: JsonObject, key: str, index: int) -> float | None:
    value = _value(values, key, index)
    return float(value) if isinstance(value, int | float) else None


def _optional_int(values: JsonObject, key: str, index: int) -> int | None:
    value = _value(values, key, index)
    return int(value) if isinstance(value, int | float) else None


def parse_daily(payload: JsonObject, index: int) -> DailyWeather:
    daily_value = payload.get("daily")
    if not isinstance(daily_value, dict):
        raise ValueError("Respuesta sin datos diarios")
    daily: JsonObject = daily_value
    raw_date = _value(daily, "time", index)
    if not isinstance(raw_date, str):
        raise ValueError(f"Fecha diaria ausente en índice {index}")
    return DailyWeather(
        date=date.fromisoformat(raw_date),
        temperature_max_c=_required_float(daily, "temperature_2m_max", index),
        temperature_min_c=_required_float(daily, "temperature_2m_min", index),
        apparent_temperature_max_c=_optional_float(
            daily, "apparent_temperature_max", index
        ),
        apparent_temperature_min_c=_optional_float(
            daily, "apparent_temperature_min", index
        ),
        precipitation_sum_mm=_optional_float(daily, "precipitation_sum", index) or 0.0,
        rain_sum_mm=_optional_float(daily, "rain_sum", index),
        precipitation_hours=_optional_float(daily, "precipitation_hours", index),
        precipitation_probability_max_pct=_optional_float(
            daily, "precipitation_probability_max", index
        ),
        wind_speed_max_kmh=_optional_float(daily, "wind_speed_10m_max", index),
        wind_gusts_max_kmh=_optional_float(daily, "wind_gusts_10m_max", index),
        sunshine_duration_seconds=_optional_float(daily, "sunshine_duration", index),
        weather_code=_optional_int(daily, "weather_code", index),
    )


def parse_daily_list(payload: JsonObject) -> list[DailyWeather]:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ValueError("Respuesta sin bloque daily")
    times = daily.get("time")
    if not isinstance(times, list):
        raise ValueError("Respuesta sin daily.time")
    return [parse_daily(payload, index) for index in range(len(times))]


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("No se puede calcular un percentil sin valores")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _date_range(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _safe_date(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))


def _series_values(daily: JsonObject, base_key: str, index: int) -> list[float]:
    keys = [
        key
        for key in daily
        if key == base_key or key.startswith(f"{base_key}_member")
    ]
    values: list[float] = []
    for key in keys:
        value = _value(daily, key, index)
        if isinstance(value, int | float):
            values.append(float(value))
    return values


class WeatherQueryService:
    def __init__(
        self,
        settings: Settings,
        provider: WeatherProvider,
        repository: JsonRepository,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.repository = repository

    def validate_window(self, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise ValueError("La fecha hasta no puede ser anterior a la fecha desde")
        days = (end_date - start_date).days + 1
        if days > self.settings.max_window_days:
            raise ValueError(
                f"El período puede tener como máximo {self.settings.max_window_days} días"
            )

    def query_historical(
        self,
        start_date: date,
        end_date: date,
        now_utc: datetime | None = None,
    ) -> PeriodWeather:
        self.validate_window(start_date, end_date)
        today = (now_utc or datetime.now(timezone.utc)).date()
        if end_date >= today:
            raise ValueError("La consulta histórica solo admite fechas anteriores a hoy")
        payload = self.provider.fetch_historical(start_date, end_date)
        result = PeriodWeather(
            dataset="historical-weather-best-match",
            location_name=self.settings.location_name,
            latitude=float(payload.get("latitude", self.settings.latitude)),
            longitude=float(payload.get("longitude", self.settings.longitude)),
            timezone=self.settings.timezone,
            requested_start=start_date,
            requested_end=end_date,
            retrieved_at_utc=now_utc or datetime.now(timezone.utc),
            daily=parse_daily_list(payload),
        )
        self.repository.save_historical(result)
        return result

    def capture_forecast(
        self,
        start_date: date,
        end_date: date,
        now_utc: datetime | None = None,
    ) -> ForecastSnapshot:
        self.validate_window(start_date, end_date)
        captured_at = now_utc or datetime.now(timezone.utc)
        today = captured_at.date()
        available_end = today + timedelta(days=self.settings.forecast_horizon_days - 1)
        if start_date < today or end_date > available_end:
            raise ValueError(
                "La captura solo admite fechas dentro del pronóstico diario disponible: "
                f"{today} a {available_end}"
            )
        payload = self.provider.fetch_forecast(start_date, end_date)
        snapshot = ForecastSnapshot(
            location_name=self.settings.location_name,
            latitude=float(payload.get("latitude", self.settings.latitude)),
            longitude=float(payload.get("longitude", self.settings.longitude)),
            timezone=self.settings.timezone,
            requested_start=start_date,
            requested_end=end_date,
            captured_at_utc=captured_at,
            daily=parse_daily_list(payload),
        )
        self.repository.save_forecast(snapshot)
        return snapshot

    def query_future(
        self,
        start_date: date,
        end_date: date,
        *,
        climate_years: int | None = None,
        now_utc: datetime | None = None,
    ) -> FutureOutlook:
        self.validate_window(start_date, end_date)
        generated_at = now_utc or datetime.now(timezone.utc)
        today = generated_at.date()
        if start_date < today:
            raise ValueError("La perspectiva futura no admite fechas anteriores a hoy")

        forecast_end = today + timedelta(days=self.settings.forecast_horizon_days - 1)
        live_forecast: list[DailyWeather] = []
        live_start = max(start_date, today)
        live_end = min(end_date, forecast_end)
        if live_start <= live_end:
            live_forecast = parse_daily_list(
                self.provider.fetch_forecast(live_start, live_end)
            )

        requested_years = climate_years or self.settings.climate_reference_years
        if requested_years < 3 or requested_years > 30:
            raise ValueError("La referencia climática debe usar entre 3 y 30 años")
        climate_reference, sample_years = self._build_climate_reference(
            start_date, end_date, requested_years, today.year - 1
        )

        notes = [
            "Hasta 16 días se muestra un pronóstico meteorológico diario vigente.",
            "Fuera de esa ventana, la tendencia estacional es probabilística y no predice el tiempo exacto de cada día.",
            "La referencia climática resume cómo se comportaron esas mismas fechas en años anteriores.",
        ]
        seasonal_estimate: list[SeasonalDailyEstimate] = []
        seasonal_end = today + timedelta(days=self.settings.seasonal_horizon_days - 1)
        if start_date <= seasonal_end:
            try:
                payload = self.provider.fetch_seasonal(
                    self.settings.seasonal_horizon_days
                )
                seasonal_estimate = self._parse_seasonal(
                    payload,
                    max(start_date, forecast_end + timedelta(days=1)),
                    min(end_date, seasonal_end),
                )
            except Exception as exc:  # noqa: BLE001 - keep climate fallback operational
                notes.append(
                    "La API estacional no estuvo disponible; el reporte conserva la referencia climática. "
                    f"Detalle técnico: {type(exc).__name__}."
                )

        result = FutureOutlook(
            location_name=self.settings.location_name,
            latitude=self.settings.latitude,
            longitude=self.settings.longitude,
            timezone=self.settings.timezone,
            requested_start=start_date,
            requested_end=end_date,
            generated_at_utc=generated_at,
            forecast_available_through=forecast_end,
            live_forecast=live_forecast,
            seasonal_estimate=seasonal_estimate,
            climate_reference_years=sample_years,
            climate_reference=climate_reference,
            notes=notes,
        )
        self.repository.save_future(result)
        return result

    def compare_saved_forecasts(
        self,
        start_date: date,
        end_date: date,
        now_utc: datetime | None = None,
    ) -> list[ComparisonReport]:
        self.validate_window(start_date, end_date)
        generated_at = now_utc or datetime.now(timezone.utc)
        if end_date >= generated_at.date():
            raise ValueError("Solo se pueden comparar fechas que ya finalizaron")

        snapshots = [
            snapshot
            for snapshot in self.repository.load_forecasts()
            if snapshot.requested_start <= end_date
            and snapshot.requested_end >= start_date
        ]
        if not snapshots:
            raise ValueError("No hay capturas guardadas que coincidan con el período")

        historical = self.query_historical(start_date, end_date, generated_at)
        actual_by_date = {day.date: day for day in historical.daily}
        reports: list[ComparisonReport] = []
        for snapshot in snapshots:
            rows: list[DailyComparison] = []
            for forecast in snapshot.daily:
                if not (start_date <= forecast.date <= end_date):
                    continue
                actual = actual_by_date.get(forecast.date)
                if actual is None:
                    continue
                rows.append(self._comparison_row(snapshot, forecast, actual))
            if not rows:
                continue
            report = ComparisonReport(
                location_name=self.settings.location_name,
                requested_start=max(start_date, snapshot.requested_start),
                requested_end=min(end_date, snapshot.requested_end),
                generated_at_utc=generated_at,
                snapshot_captured_at_utc=snapshot.captured_at_utc,
                actual_dataset=historical.dataset,
                daily=rows,
            )
            self.repository.save_comparison(report)
            reports.append(report)
        return reports

    def _build_climate_reference(
        self,
        target_start: date,
        target_end: date,
        years_count: int,
        last_year: int,
    ) -> tuple[list[ClimateDailyReference], list[int]]:
        values_by_target: dict[date, list[DailyWeather]] = defaultdict(list)
        used_years: list[int] = []
        year_span = target_end.year - target_start.year
        for sample_start_year in range(last_year - years_count + 1, last_year + 1):
            sample_start = _safe_date(
                sample_start_year, target_start.month, target_start.day
            )
            sample_end = _safe_date(
                sample_start_year + year_span, target_end.month, target_end.day
            )
            payload = self.provider.fetch_climate_sample(sample_start, sample_end)
            sample_days = parse_daily_list(payload)
            by_month_day = {(day.date.month, day.date.day): day for day in sample_days}
            contributed = False
            for target in _date_range(target_start, target_end):
                sample = by_month_day.get((target.month, target.day))
                if sample is not None:
                    values_by_target[target].append(sample)
                    contributed = True
            if contributed:
                used_years.append(sample_start_year)

        result: list[ClimateDailyReference] = []
        for target in _date_range(target_start, target_end):
            rows = values_by_target[target]
            if not rows:
                raise RuntimeError(f"No se obtuvo referencia climática para {target}")
            max_values = [row.temperature_max_c for row in rows]
            min_values = [row.temperature_min_c for row in rows]
            rain_values = [row.precipitation_sum_mm for row in rows]
            result.append(
                ClimateDailyReference(
                    date=target,
                    sample_years=len(rows),
                    temperature_max_mean_c=round(mean(max_values), 2),
                    temperature_max_p10_c=round(_percentile(max_values, 0.10), 2),
                    temperature_max_p90_c=round(_percentile(max_values, 0.90), 2),
                    temperature_min_mean_c=round(mean(min_values), 2),
                    temperature_min_p10_c=round(_percentile(min_values, 0.10), 2),
                    temperature_min_p90_c=round(_percentile(min_values, 0.90), 2),
                    precipitation_mean_mm=round(mean(rain_values), 2),
                    precipitation_p90_mm=round(_percentile(rain_values, 0.90), 2),
                    rain_frequency_pct=round(
                        100 * mean(1.0 if value >= 0.1 else 0.0 for value in rain_values),
                        1,
                    ),
                )
            )
        return result, used_years

    def _parse_seasonal(
        self, payload: JsonObject, start_date: date, end_date: date
    ) -> list[SeasonalDailyEstimate]:
        if start_date > end_date:
            return []
        daily_value = payload.get("daily")
        if not isinstance(daily_value, dict):
            return []
        daily: JsonObject = daily_value
        times = daily.get("time")
        if not isinstance(times, list):
            return []
        estimates: list[SeasonalDailyEstimate] = []
        for index, raw_time in enumerate(times):
            if not isinstance(raw_time, str):
                continue
            target = date.fromisoformat(raw_time)
            if not (start_date <= target <= end_date):
                continue
            maximums = _series_values(daily, "temperature_2m_max", index)
            minimums = _series_values(daily, "temperature_2m_min", index)
            precipitation = _series_values(daily, "precipitation_sum", index)
            member_count = max(len(maximums), len(minimums), len(precipitation), 1)
            estimates.append(
                SeasonalDailyEstimate(
                    date=target,
                    members=member_count,
                    temperature_max_mean_c=(
                        round(mean(maximums), 2) if maximums else None
                    ),
                    temperature_max_p10_c=(
                        round(_percentile(maximums, 0.10), 2) if maximums else None
                    ),
                    temperature_max_p90_c=(
                        round(_percentile(maximums, 0.90), 2) if maximums else None
                    ),
                    temperature_min_mean_c=(
                        round(mean(minimums), 2) if minimums else None
                    ),
                    temperature_min_p10_c=(
                        round(_percentile(minimums, 0.10), 2) if minimums else None
                    ),
                    temperature_min_p90_c=(
                        round(_percentile(minimums, 0.90), 2) if minimums else None
                    ),
                    precipitation_mean_mm=(
                        round(mean(precipitation), 2) if precipitation else None
                    ),
                    precipitation_p90_mm=(
                        round(_percentile(precipitation, 0.90), 2)
                        if precipitation
                        else None
                    ),
                )
            )
        return estimates

    @staticmethod
    def _comparison_row(
        snapshot: ForecastSnapshot,
        forecast: DailyWeather,
        actual: DailyWeather,
    ) -> DailyComparison:
        capture_date = snapshot.captured_at_utc.date()
        return DailyComparison(
            target_date=forecast.date,
            forecast_captured_at_utc=snapshot.captured_at_utc,
            lead_days=(forecast.date - capture_date).days,
            forecast=forecast,
            actual=actual,
            temperature_max_error_c=WeatherQueryService._error(
                forecast.temperature_max_c, actual.temperature_max_c
            ),
            temperature_min_error_c=WeatherQueryService._error(
                forecast.temperature_min_c, actual.temperature_min_c
            ),
            precipitation_error_mm=WeatherQueryService._error(
                forecast.precipitation_sum_mm, actual.precipitation_sum_mm
            ),
            rain_event_forecast=forecast.precipitation_sum_mm >= 0.1,
            rain_event_actual=actual.precipitation_sum_mm >= 0.1,
            rain_event_correct=(forecast.precipitation_sum_mm >= 0.1)
            == (actual.precipitation_sum_mm >= 0.1),
        )

    @staticmethod
    def _error(forecast: float, actual: float) -> MetricError:
        signed = round(forecast - actual, 2)
        return MetricError(absolute=abs(signed), signed=signed)
