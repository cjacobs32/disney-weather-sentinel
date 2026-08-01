from __future__ import annotations

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
from .provider import JsonObject, WeatherProvider
from .storage import JsonRepository


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
        precipitation_sum_mm=_optional_float(daily, "precipitation_sum", index),
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


def _noaa_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"T", "M", "NULL", "NAN"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _noaa_attribute_parts(value: object) -> tuple[str, str, str, str]:
    text = "" if value is None else str(value)
    parts = (text.split(",") + ["", "", "", ""])[:4]
    return parts[0], parts[1], parts[2], parts[3]


def parse_noaa_row(row: JsonObject) -> DailyWeather:
    raw_date = row.get("DATE")
    if not isinstance(raw_date, str):
        raise ValueError("Fila NOAA sin DATE")

    precipitation_raw = row.get("PRCP")
    precipitation_attr = row.get("PRCP_ATTRIBUTES")
    measurement_flag, precipitation_quality, _, _ = _noaa_attribute_parts(
        precipitation_attr
    )
    trace = str(precipitation_raw).strip().upper() == "T" or measurement_flag == "T"
    precipitation = 0.0 if trace else _noaa_float(precipitation_raw)

    quality_flags: dict[str, str] = {}
    source_attributes: dict[str, str] = {}
    for variable in ("TMAX", "TMIN", "PRCP", "AWND", "WSF2", "WSF5"):
        attribute = row.get(f"{variable}_ATTRIBUTES")
        if attribute is not None:
            source_attributes[variable] = str(attribute)
            _, quality_flag, _, _ = _noaa_attribute_parts(attribute)
            if quality_flag:
                quality_flags[variable] = quality_flag
    if precipitation_quality:
        quality_flags["PRCP"] = precipitation_quality

    average_wind_ms = _noaa_float(row.get("AWND"))
    fastest_values_ms = [
        value
        for value in (_noaa_float(row.get("WSF2")), _noaa_float(row.get("WSF5")))
        if value is not None
    ]
    fastest_wind_ms = max(fastest_values_ms) if fastest_values_ms else None

    return DailyWeather(
        date=date.fromisoformat(raw_date[:10]),
        temperature_max_c=_noaa_float(row.get("TMAX")),
        temperature_min_c=_noaa_float(row.get("TMIN")),
        precipitation_sum_mm=precipitation,
        precipitation_trace=trace,
        wind_speed_mean_kmh=(average_wind_ms * 3.6 if average_wind_ms is not None else None),
        wind_speed_max_kmh=(fastest_wind_ms * 3.6 if fastest_wind_ms is not None else None),
        quality_flags=quality_flags,
        source_attributes=source_attributes,
    )


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


def _year_chunks(start_date: date, end_date: date) -> Iterable[tuple[date, date]]:
    current = start_date
    while current <= end_date:
        chunk_end = min(end_date, date(current.year, 12, 31))
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def _safe_month_day(year: int, month: int, day: int) -> date:
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


def _series_values(daily: JsonObject, base_key: str, index: int) -> list[float]:
    keys = [key for key in daily if key == base_key or key.startswith(f"{base_key}_member")]
    values: list[float] = []
    for key in keys:
        value = _value(daily, key, index)
        if isinstance(value, int | float):
            values.append(float(value))
    return values


def _metric(forecast: float | None, actual: float | None) -> MetricError | None:
    if forecast is None or actual is None:
        return None
    signed = forecast - actual
    return MetricError(absolute=abs(signed), signed=signed)


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

    def query_historical(
        self,
        start_date: date,
        end_date: date,
        now_utc: datetime | None = None,
    ) -> PeriodWeather:
        self.validate_window(start_date, end_date)
        retrieved_at = now_utc or datetime.now(timezone.utc)
        if end_date >= retrieved_at.date():
            raise ValueError("Las observaciones históricas solo admiten fechas ya finalizadas")

        effective_start = max(start_date, self.settings.noaa_station_record_start)
        rows_by_date: dict[date, DailyWeather] = {}
        if effective_start <= end_date:
            for chunk_start, chunk_end in _year_chunks(effective_start, end_date):
                for raw_row in self.provider.fetch_historical(chunk_start, chunk_end):
                    parsed = parse_noaa_row(raw_row)
                    rows_by_date[parsed.date] = parsed

        daily = [rows_by_date[key] for key in sorted(rows_by_date)]
        requested_dates = list(_date_range(start_date, end_date))
        missing_dates = [value for value in requested_dates if value not in rows_by_date]
        result = PeriodWeather(
            location_name=self.settings.location_name,
            latitude=self.settings.latitude,
            longitude=self.settings.longitude,
            timezone=self.settings.timezone,
            station_id=self.settings.noaa_station_id,
            station_name=self.settings.noaa_station_name,
            station_latitude=self.settings.noaa_station_latitude,
            station_longitude=self.settings.noaa_station_longitude,
            station_distance_from_target_km=self.settings.noaa_station_distance_km,
            station_record_start=self.settings.noaa_station_record_start,
            requested_start=start_date,
            requested_end=end_date,
            retrieved_at_utc=retrieved_at,
            coverage_start=daily[0].date if daily else None,
            coverage_end=daily[-1].date if daily else None,
            requested_days=len(requested_dates),
            returned_days=len(daily),
            missing_dates=missing_dates,
            daily=daily,
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

    def _build_climate_reference(
        self, start_date: date, end_date: date, years_count: int, last_year: int
    ) -> tuple[list[ClimateDailyReference], list[int]]:
        target_dates = list(_date_range(start_date, end_date))
        samples_by_month_day: dict[tuple[int, int], list[DailyWeather]] = defaultdict(list)
        used_years: list[int] = []
        requested_month_days = {(target.month, target.day) for target in target_dates}

        for sample_year in range(last_year - years_count + 1, last_year + 1):
            sample_days: list[DailyWeather] = []
            for chunk_start, chunk_end in _year_chunks(
                date(sample_year, 1, 1), date(sample_year, 12, 31)
            ):
                sample_days.extend(
                    parse_daily_list(self.provider.fetch_climate_sample(chunk_start, chunk_end))
                )
            contributed = False
            for sample in sample_days:
                key = (sample.date.month, sample.date.day)
                if key in requested_month_days:
                    samples_by_month_day[key].append(sample)
                    contributed = True
            if contributed:
                used_years.append(sample_year)

        reference: list[ClimateDailyReference] = []
        for target in target_dates:
            rows = samples_by_month_day.get((target.month, target.day), [])
            maximums = [row.temperature_max_c for row in rows if row.temperature_max_c is not None]
            minimums = [row.temperature_min_c for row in rows if row.temperature_min_c is not None]
            rain = [row.precipitation_sum_mm for row in rows if row.precipitation_sum_mm is not None]
            if not maximums or not minimums or not rain:
                continue
            reference.append(
                ClimateDailyReference(
                    date=target,
                    sample_years=min(len(maximums), len(minimums), len(rain)),
                    temperature_max_mean_c=mean(maximums),
                    temperature_max_p10_c=_percentile(maximums, 0.1),
                    temperature_max_p90_c=_percentile(maximums, 0.9),
                    temperature_min_mean_c=mean(minimums),
                    temperature_min_p10_c=_percentile(minimums, 0.1),
                    temperature_min_p90_c=_percentile(minimums, 0.9),
                    precipitation_mean_mm=mean(rain),
                    precipitation_p90_mm=_percentile(rain, 0.9),
                    rain_frequency_pct=100.0 * sum(value >= 0.1 for value in rain) / len(rain),
                )
            )
        return reference, used_years

    def _parse_seasonal(
        self, payload: JsonObject, start_date: date, end_date: date
    ) -> list[SeasonalDailyEstimate]:
        daily_value = payload.get("daily")
        if not isinstance(daily_value, dict):
            return []
        daily: JsonObject = daily_value
        times = daily.get("time")
        if not isinstance(times, list):
            return []
        output: list[SeasonalDailyEstimate] = []
        for index, raw_date in enumerate(times):
            if not isinstance(raw_date, str):
                continue
            target = date.fromisoformat(raw_date)
            if target < start_date or target > end_date:
                continue
            maximums = _series_values(daily, "temperature_2m_max", index)
            minimums = _series_values(daily, "temperature_2m_min", index)
            rain = _series_values(daily, "precipitation_sum", index)
            members = max(len(maximums), len(minimums), len(rain), 1)
            output.append(
                SeasonalDailyEstimate(
                    date=target,
                    members=members,
                    temperature_max_mean_c=mean(maximums) if maximums else None,
                    temperature_max_p10_c=_percentile(maximums, 0.1) if maximums else None,
                    temperature_max_p90_c=_percentile(maximums, 0.9) if maximums else None,
                    temperature_min_mean_c=mean(minimums) if minimums else None,
                    temperature_min_p10_c=_percentile(minimums, 0.1) if minimums else None,
                    temperature_min_p90_c=_percentile(minimums, 0.9) if minimums else None,
                    precipitation_mean_mm=mean(rain) if rain else None,
                    precipitation_p90_mm=_percentile(rain, 0.9) if rain else None,
                )
            )
        return output

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
        live_end = min(end_date, forecast_end)
        if start_date <= live_end:
            live_forecast = parse_daily_list(
                self.provider.fetch_forecast(start_date, live_end)
            )

        requested_years = climate_years or self.settings.climate_reference_years
        if requested_years < 3 or requested_years > 30:
            raise ValueError("La referencia climática debe usar entre 3 y 30 años")
        climate_reference, sample_years = self._build_climate_reference(
            start_date, end_date, requested_years, today.year - 1
        )

        notes = [
            "El selector no impone un límite artificial al rango.",
            "Solo los días dentro del horizonte operativo tienen pronóstico diario.",
            "Fuera de esa ventana se muestran tendencia estacional y referencia climática cuando están disponibles.",
        ]
        seasonal_estimate: list[SeasonalDailyEstimate] = []
        seasonal_end = today + timedelta(days=self.settings.seasonal_horizon_days - 1)
        seasonal_start = max(start_date, forecast_end + timedelta(days=1))
        if seasonal_start <= min(end_date, seasonal_end):
            try:
                payload = self.provider.fetch_seasonal(self.settings.seasonal_horizon_days)
                seasonal_estimate = self._parse_seasonal(
                    payload, seasonal_start, min(end_date, seasonal_end)
                )
            except Exception as exc:  # noqa: BLE001
                notes.append(
                    "La API estacional no estuvo disponible; se conserva la referencia climática. "
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
            if snapshot.requested_start <= end_date and snapshot.requested_end >= start_date
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
                forecast_rain = (
                    forecast.precipitation_sum_mm >= 0.1
                    if forecast.precipitation_sum_mm is not None
                    else None
                )
                actual_rain = (
                    actual.precipitation_sum_mm >= 0.1
                    if actual.precipitation_sum_mm is not None
                    else None
                )
                rows.append(
                    DailyComparison(
                        target_date=forecast.date,
                        forecast_captured_at_utc=snapshot.captured_at_utc,
                        lead_days=(forecast.date - snapshot.captured_at_utc.date()).days,
                        forecast=forecast,
                        actual=actual,
                        temperature_max_error_c=_metric(
                            forecast.temperature_max_c, actual.temperature_max_c
                        ),
                        temperature_min_error_c=_metric(
                            forecast.temperature_min_c, actual.temperature_min_c
                        ),
                        precipitation_error_mm=_metric(
                            forecast.precipitation_sum_mm, actual.precipitation_sum_mm
                        ),
                        rain_event_forecast=forecast_rain,
                        rain_event_actual=actual_rain,
                        rain_event_correct=(
                            forecast_rain == actual_rain
                            if forecast_rain is not None and actual_rain is not None
                            else None
                        ),
                    )
                )
            if not rows:
                continue
            report = ComparisonReport(
                location_name=self.settings.location_name,
                requested_start=max(start_date, snapshot.requested_start),
                requested_end=min(end_date, snapshot.requested_end),
                generated_at_utc=generated_at,
                snapshot_captured_at_utc=snapshot.captured_at_utc,
                actual_dataset=historical.dataset,
                actual_station_id=historical.station_id,
                actual_station_name=historical.station_name,
                actual_station_distance_from_target_km=historical.station_distance_from_target_km,
                daily=rows,
            )
            self.repository.save_comparison(report)
            reports.append(report)
        return reports
