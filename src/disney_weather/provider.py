from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import httpx

from .config import Settings


JsonObject = dict[str, Any]
JsonRows = list[JsonObject]


class WeatherProvider(ABC):
    @abstractmethod
    def fetch_forecast(self, start_date: date, end_date: date) -> JsonObject:
        raise NotImplementedError

    @abstractmethod
    def fetch_historical(self, start_date: date, end_date: date) -> JsonRows:
        raise NotImplementedError

    @abstractmethod
    def fetch_climate_sample(self, start_date: date, end_date: date) -> JsonObject:
        raise NotImplementedError

    @abstractmethod
    def fetch_seasonal(self, forecast_days: int) -> JsonObject:
        raise NotImplementedError


class OpenMeteoProvider(WeatherProvider):
    """Client for NOAA observations and Open-Meteo forecasts, without API keys."""

    FORECAST_DAILY_FIELDS = ",".join(
        [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "precipitation_sum",
            "rain_sum",
            "precipitation_hours",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "sunshine_duration",
        ]
    )
    ARCHIVE_DAILY_FIELDS = ",".join(
        [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
        ]
    )
    SEASONAL_DAILY_FIELDS = ",".join(
        ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]
    )
    NOAA_DATA_TYPES = "TMAX,TMIN,PRCP,AWND,WSF2,WSF5"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _request_json(
        self, url: str, params: dict[str, str | int | float]
    ) -> Any:
        headers = {
            "User-Agent": "Disney-Weather-Sentinel/4.0",
            "Accept": "application/json",
        }
        with httpx.Client(
            timeout=self.settings.request_timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def _get_open_meteo(
        self, url: str, params: dict[str, str | int | float]
    ) -> JsonObject:
        payload = self._request_json(url, params)
        if not isinstance(payload, dict):
            raise RuntimeError("Open-Meteo devolvió un formato inesperado")
        if "daily" not in payload:
            reason = payload.get("reason", "Respuesta sin bloque daily")
            raise RuntimeError(f"Open-Meteo no devolvió datos diarios: {reason}")
        return payload

    def _common_params(self) -> dict[str, str | int | float]:
        return {
            "latitude": self.settings.latitude,
            "longitude": self.settings.longitude,
            "timezone": self.settings.timezone,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }

    def fetch_forecast(self, start_date: date, end_date: date) -> JsonObject:
        params = self._common_params()
        params.update(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily": self.FORECAST_DAILY_FIELDS,
                "models": "best_match",
            }
        )
        return self._get_open_meteo(self.settings.forecast_url, params)

    def fetch_historical(self, start_date: date, end_date: date) -> JsonRows:
        params: dict[str, str | int | float] = {
            "dataset": "daily-summaries",
            "stations": self.settings.noaa_station_id,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dataTypes": self.NOAA_DATA_TYPES,
            "format": "json",
            "units": "metric",
            "includeAttributes": "true",
            "includeStationName": "true",
            "includeStationLocation": "true",
        }
        payload = self._request_json(self.settings.noaa_url, params)
        if isinstance(payload, dict) and payload.get("errorMessage"):
            raise RuntimeError(str(payload.get("errorMessage")))
        if not isinstance(payload, list):
            raise RuntimeError("NOAA/NCEI devolvió un formato inesperado")
        return [row for row in payload if isinstance(row, dict)]

    def fetch_climate_sample(self, start_date: date, end_date: date) -> JsonObject:
        params = self._common_params()
        params.update(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily": self.ARCHIVE_DAILY_FIELDS,
                "models": "era5_land",
            }
        )
        return self._get_open_meteo(self.settings.archive_url, params)

    def fetch_seasonal(self, forecast_days: int) -> JsonObject:
        params = self._common_params()
        params.update(
            {"daily": self.SEASONAL_DAILY_FIELDS, "forecast_days": forecast_days}
        )
        return self._get_open_meteo(self.settings.seasonal_url, params)
