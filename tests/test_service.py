from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from disney_weather.config import Settings
from disney_weather.models import DailyWeather, ForecastSnapshot
from disney_weather.provider import WeatherProvider
from disney_weather.service import WeatherQueryService, parse_daily
from disney_weather.storage import JsonRepository


JsonObject = dict[str, Any]


def payload_for(start_date: date, end_date: date, *, year_sensitive: bool = False) -> JsonObject:
    dates: list[str] = []
    maximums: list[float] = []
    minimums: list[float] = []
    rain: list[float] = []
    codes: list[int] = []
    current = start_date
    while current <= end_date:
        dates.append(current.isoformat())
        adjustment = float(current.year % 10) if year_sensitive else 0.0
        maximums.append(28.0 + adjustment)
        minimums.append(18.0 + adjustment)
        rain.append(float(current.day % 3))
        codes.append(61 if current.day % 3 else 0)
        current += timedelta(days=1)
    return {
        "latitude": 28.37,
        "longitude": -81.57,
        "daily": {
            "time": dates,
            "temperature_2m_max": maximums,
            "temperature_2m_min": minimums,
            "precipitation_sum": rain,
            "weather_code": codes,
        },
    }


class FakeProvider(WeatherProvider):
    def __init__(self) -> None:
        self.historical_calls = 0

    def fetch_forecast(self, start_date: date, end_date: date) -> JsonObject:
        return payload_for(start_date, end_date)

    def fetch_historical(self, start_date: date, end_date: date) -> JsonObject:
        self.historical_calls += 1
        return payload_for(start_date, end_date)

    def fetch_climate_sample(self, start_date: date, end_date: date) -> JsonObject:
        return payload_for(start_date, end_date, year_sensitive=True)

    def fetch_seasonal(self, forecast_days: int) -> JsonObject:
        assert forecast_days == 210
        return {
            "daily": {
                "time": ["2026-11-01", "2026-11-02", "2026-11-03"],
                "temperature_2m_max_member01": [27.0, 28.0, 29.0],
                "temperature_2m_max_member02": [29.0, 30.0, 31.0],
                "temperature_2m_min_member01": [17.0, 18.0, 19.0],
                "temperature_2m_min_member02": [19.0, 20.0, 21.0],
                "precipitation_sum_member01": [0.0, 2.0, 4.0],
                "precipitation_sum_member02": [2.0, 4.0, 6.0],
            }
        }


def build_service(tmp_path: Path) -> tuple[WeatherQueryService, FakeProvider]:
    settings = Settings(
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        web_generated_dir=tmp_path / "docs" / "generated",
        climate_reference_years=3,
    )
    provider = FakeProvider()
    repository = JsonRepository(
        settings.data_dir, settings.reports_dir, settings.web_generated_dir
    )
    return WeatherQueryService(settings, provider, repository), provider


def test_parse_daily_handles_optional_values() -> None:
    payload = {
        "daily": {
            "time": ["2026-08-01"],
            "temperature_2m_max": [33.2],
            "temperature_2m_min": [24.1],
            "precipitation_sum": [4.5],
            "weather_code": [61],
        }
    }
    result = parse_daily(payload, 0)
    assert result.date == date(2026, 8, 1)
    assert result.temperature_max_c == 33.2
    assert result.precipitation_sum_mm == 4.5
    assert result.wind_speed_max_kmh is None


def test_rejects_windows_longer_than_fifteen_days(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    with pytest.raises(ValueError, match="máximo 15 días"):
        service.validate_window(date(2026, 11, 1), date(2026, 11, 16))


def test_historical_2025_uses_historical_weather_dataset(tmp_path: Path) -> None:
    service, provider = build_service(tmp_path)
    result = service.query_historical(
        date(2025, 11, 1),
        date(2025, 11, 3),
        datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    assert result.dataset == "historical-weather-best-match"
    assert provider.historical_calls == 1
    assert len(result.daily) == 3


def test_future_builds_seasonal_and_climate_reference(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    result = service.query_future(
        date(2026, 11, 1),
        date(2026, 11, 3),
        climate_years=3,
        now_utc=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    assert result.live_forecast == []
    assert len(result.seasonal_estimate) == 3
    assert result.seasonal_estimate[0].temperature_max_mean_c == 28.0
    assert len(result.climate_reference) == 3
    assert result.climate_reference[0].sample_years == 3
    assert result.climate_reference_years == [2023, 2024, 2025]


def test_compare_saved_snapshot_with_historical(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    snapshot = ForecastSnapshot(
        location_name="Walt Disney World Resort, Orlando",
        latitude=28.3772,
        longitude=-81.5707,
        timezone="America/New_York",
        requested_start=date(2025, 11, 1),
        requested_end=date(2025, 11, 2),
        captured_at_utc=datetime(2025, 10, 25, tzinfo=timezone.utc),
        daily=[
            DailyWeather(
                date=date(2025, 11, 1),
                temperature_max_c=30,
                temperature_min_c=20,
                precipitation_sum_mm=1,
            ),
            DailyWeather(
                date=date(2025, 11, 2),
                temperature_max_c=29,
                temperature_min_c=19,
                precipitation_sum_mm=0,
            ),
        ],
    )
    service.repository.save_forecast(snapshot)
    reports = service.compare_saved_forecasts(
        date(2025, 11, 1),
        date(2025, 11, 2),
        datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    assert len(reports) == 1
    assert len(reports[0].daily) == 2
    assert reports[0].daily[0].lead_days == 7
