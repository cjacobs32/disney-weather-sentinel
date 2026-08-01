from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from disney_weather.config import Settings
from disney_weather.models import DailyWeather, ForecastSnapshot
from disney_weather.provider import JsonObject, JsonRows, WeatherProvider
from disney_weather.service import WeatherQueryService, parse_daily, parse_noaa_row
from disney_weather.storage import JsonRepository


def open_meteo_payload(
    start_date: date, end_date: date, *, year_sensitive: bool = False
) -> JsonObject:
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


def noaa_rows(start_date: date, end_date: date) -> JsonRows:
    rows: JsonRows = []
    current = start_date
    while current <= end_date:
        rows.append(
            {
                "DATE": current.isoformat(),
                "STATION": "USW00012815",
                "NAME": "ORLANDO INTERNATIONAL AIRPORT, FL US",
                "TMAX": "30.0",
                "TMIN": "20.0",
                "PRCP": "1.2",
                "PRCP_ATTRIBUTES": ",,W,",
                "AWND": "3.0",
                "WSF2": "8.0",
            }
        )
        current += timedelta(days=1)
    return rows


class FakeProvider(WeatherProvider):
    def __init__(self) -> None:
        self.historical_calls: list[tuple[date, date]] = []

    def fetch_forecast(self, start_date: date, end_date: date) -> JsonObject:
        return open_meteo_payload(start_date, end_date)

    def fetch_historical(self, start_date: date, end_date: date) -> JsonRows:
        self.historical_calls.append((start_date, end_date))
        return noaa_rows(start_date, end_date)

    def fetch_climate_sample(self, start_date: date, end_date: date) -> JsonObject:
        return open_meteo_payload(start_date, end_date, year_sensitive=True)

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


def test_parse_daily_keeps_missing_precipitation_as_missing() -> None:
    payload = {
        "daily": {
            "time": ["2026-08-01"],
            "temperature_2m_max": [33.2],
            "temperature_2m_min": [24.1],
            "precipitation_sum": [None],
        }
    }
    result = parse_daily(payload, 0)
    assert result.precipitation_sum_mm is None


def test_noaa_trace_and_missing_are_not_confused_with_zero() -> None:
    trace = parse_noaa_row(
        {
            "DATE": "2025-11-01",
            "TMAX": "30",
            "TMIN": "20",
            "PRCP": "0",
            "PRCP_ATTRIBUTES": "T,,W,",
        }
    )
    missing = parse_noaa_row(
        {"DATE": "2025-11-02", "TMAX": "30", "TMIN": "20", "PRCP": ""}
    )
    assert trace.precipitation_trace is True
    assert trace.precipitation_sum_mm == 0.0
    assert missing.precipitation_trace is False
    assert missing.precipitation_sum_mm is None


def test_arbitrary_long_window_is_allowed() -> None:
    service = WeatherQueryService.__new__(WeatherQueryService)
    service.validate_window(date(2020, 1, 1), date(2026, 12, 31))


def test_historical_uses_noaa_and_chunks_by_calendar_year(tmp_path: Path) -> None:
    service, provider = build_service(tmp_path)
    result = service.query_historical(
        date(2024, 12, 30),
        date(2025, 1, 2),
        datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    assert result.provider == "noaa-ncei"
    assert result.dataset == "GHCN-Daily Daily Summaries"
    assert result.station_id == "USW00012815"
    assert provider.historical_calls == [
        (date(2024, 12, 30), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 1, 2)),
    ]
    assert result.returned_days == 4


def test_historical_before_station_record_reports_missing_dates(tmp_path: Path) -> None:
    service, provider = build_service(tmp_path)
    result = service.query_historical(
        date(1951, 12, 30),
        date(1952, 1, 2),
        datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    assert provider.historical_calls == [(date(1952, 1, 1), date(1952, 1, 2))]
    assert result.requested_days == 4
    assert result.returned_days == 2
    assert result.missing_dates == [date(1951, 12, 30), date(1951, 12, 31)]


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
    assert result.climate_reference_years == [2023, 2024, 2025]


def test_compare_saved_snapshot_with_noaa_observation(tmp_path: Path) -> None:
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
    assert reports[0].actual_station_id == "USW00012815"
    assert reports[0].daily[0].lead_days == 7


def test_historical_report_highlights_rain_days_without_counting_trace_twice() -> None:
    from disney_weather.models import PeriodWeather
    from disney_weather.reporting import render_historical

    result = PeriodWeather(
        location_name="Walt Disney World Resort, Orlando",
        latitude=28.3772,
        longitude=-81.5707,
        timezone="America/New_York",
        station_id="USW00012815",
        station_name="ORLANDO INTERNATIONAL AIRPORT, FL US",
        station_latitude=28.41822,
        station_longitude=-81.32413,
        station_distance_from_target_km=24.5,
        station_record_start=date(1952, 1, 1),
        requested_start=date(2025, 11, 1),
        requested_end=date(2025, 11, 4),
        retrieved_at_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        coverage_start=date(2025, 11, 1),
        coverage_end=date(2025, 11, 4),
        requested_days=4,
        returned_days=4,
        daily=[
            DailyWeather(date=date(2025, 11, 1), precipitation_sum_mm=0.0),
            DailyWeather(date=date(2025, 11, 2), precipitation_sum_mm=1.5),
            DailyWeather(date=date(2025, 11, 3), precipitation_sum_mm=8.0),
            DailyWeather(
                date=date(2025, 11, 4),
                precipitation_sum_mm=0.0,
                precipitation_trace=True,
            ),
        ],
    )

    report = render_historical(result)
    assert "Días con lluvia medible:** 2 de 4" in report
    assert "Días sin lluvia:** 1" in report
    assert "Días con traza:** 1" in report
    assert "1 leves · 1 moderados · 0 intensos" in report
