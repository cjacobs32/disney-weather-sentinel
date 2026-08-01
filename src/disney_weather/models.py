from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DailyWeather(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    temperature_max_c: float | None = None
    temperature_min_c: float | None = None
    apparent_temperature_max_c: float | None = None
    apparent_temperature_min_c: float | None = None
    precipitation_sum_mm: float | None = None
    precipitation_trace: bool = False
    rain_sum_mm: float | None = None
    precipitation_hours: float | None = None
    precipitation_probability_max_pct: float | None = None
    wind_speed_mean_kmh: float | None = None
    wind_speed_max_kmh: float | None = None
    wind_gusts_max_kmh: float | None = None
    sunshine_duration_seconds: float | None = None
    weather_code: int | None = None
    quality_flags: dict[str, str] = Field(default_factory=dict)
    source_attributes: dict[str, str] = Field(default_factory=dict)


class PeriodWeather(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["4.0"] = "4.0"
    query_type: Literal["historical"] = "historical"
    provider: str = "noaa-ncei"
    dataset: str = "GHCN-Daily Daily Summaries"
    location_name: str
    latitude: float
    longitude: float
    timezone: str
    station_id: str
    station_name: str
    station_latitude: float
    station_longitude: float
    station_distance_from_target_km: float
    station_record_start: date
    requested_start: date
    requested_end: date
    retrieved_at_utc: datetime
    coverage_start: date | None = None
    coverage_end: date | None = None
    requested_days: int = Field(ge=1)
    returned_days: int = Field(ge=0)
    missing_dates: list[date] = Field(default_factory=list)
    daily: list[DailyWeather]


class ForecastSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["4.0"] = "4.0"
    query_type: Literal["forecast_snapshot"] = "forecast_snapshot"
    provider: str = "open-meteo"
    model: str = "best_match"
    location_name: str
    latitude: float
    longitude: float
    timezone: str
    requested_start: date
    requested_end: date
    captured_at_utc: datetime
    daily: list[DailyWeather]


class ClimateDailyReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    sample_years: int = Field(ge=1)
    temperature_max_mean_c: float
    temperature_max_p10_c: float
    temperature_max_p90_c: float
    temperature_min_mean_c: float
    temperature_min_p10_c: float
    temperature_min_p90_c: float
    precipitation_mean_mm: float
    precipitation_p90_mm: float
    rain_frequency_pct: float


class SeasonalDailyEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    members: int = Field(ge=1)
    temperature_max_mean_c: float | None = None
    temperature_max_p10_c: float | None = None
    temperature_max_p90_c: float | None = None
    temperature_min_mean_c: float | None = None
    temperature_min_p10_c: float | None = None
    temperature_min_p90_c: float | None = None
    precipitation_mean_mm: float | None = None
    precipitation_p90_mm: float | None = None


class FutureOutlook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["4.0"] = "4.0"
    query_type: Literal["future_outlook"] = "future_outlook"
    provider: str = "open-meteo"
    location_name: str
    latitude: float
    longitude: float
    timezone: str
    requested_start: date
    requested_end: date
    generated_at_utc: datetime
    forecast_available_through: date
    live_forecast: list[DailyWeather]
    seasonal_estimate: list[SeasonalDailyEstimate]
    climate_reference_years: list[int]
    climate_reference: list[ClimateDailyReference]
    notes: list[str]


class MetricError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    absolute: float
    signed: float


class DailyComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_date: date
    forecast_captured_at_utc: datetime
    lead_days: int
    forecast: DailyWeather
    actual: DailyWeather
    temperature_max_error_c: MetricError | None = None
    temperature_min_error_c: MetricError | None = None
    precipitation_error_mm: MetricError | None = None
    rain_event_forecast: bool | None = None
    rain_event_actual: bool | None = None
    rain_event_correct: bool | None = None


class ComparisonReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["4.0"] = "4.0"
    query_type: Literal["comparison"] = "comparison"
    provider: str = "open-meteo-vs-noaa-ncei"
    location_name: str
    requested_start: date
    requested_end: date
    generated_at_utc: datetime
    snapshot_captured_at_utc: datetime
    actual_dataset: str
    actual_station_id: str
    actual_station_name: str
    actual_station_distance_from_target_km: float
    daily: list[DailyComparison]
