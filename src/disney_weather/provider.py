from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import httpx

from .config import Settings


JsonObject = dict[str, Any]


class WeatherProvider(ABC):
    @abstractmethod
    def fetch_forecast(self, start_date: date, end_date: date) -> JsonObject:
        raise NotImplementedError

    @abstractmethod
    def fetch_historical(self, start_date: date, end_date: date) -> JsonObject:
        raise NotImplementedError

    @abstractmethod
    def fetch_climate_sample(self, start_date: date, end_date: date) -> JsonObject:
        raise NotImplementedError

    @abstractmethod
    def fetch_seasonal(self, forecast_days: int) -> JsonObject:
        raise NotImplementedError


class OpenMeteoProvider(WeatherProvider):
    """No-key Open-Meteo client. All endpoints are usable without a card."""

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
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "precipitation_sum",
            "rain_sum",
            "precipitation_hours",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "sunshine_duration",
        ]
    )

    SEASONAL_DAILY_FIELDS = ",".join(
        [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
        ]
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _get(self, url: str, params: dict[str, str | int | float]) -> JsonObject:
        headers = {"User-Agent": "Disney-Weather-Sentinel/2.0"}
        with httpx.Client(
            timeout=self.settings.request_timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload: JsonObject = response.json()
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
        return self._get(self.settings.forecast_url, params)

    def fetch_historical(self, start_date: date, end_date: date) -> JsonObject:
        """Return the best available historical-weather reconstruction.

        This intentionally uses the Historical Weather API, not the archive of old
        forecasts. Forecast archives answer "what was predicted"; this endpoint
        is the reference for "what happened".
        """
        params = self._common_params()
        params.update(
            {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily": self.ARCHIVE_DAILY_FIELDS,
            }
        )
        return self._get(self.settings.archive_url, params)

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
        return self._get(self.settings.archive_url, params)

    def fetch_seasonal(self, forecast_days: int) -> JsonObject:
        params = self._common_params()
        params.update(
            {
                "daily": self.SEASONAL_DAILY_FIELDS,
                "forecast_days": forecast_days,
            }
        )
        return self._get(self.settings.seasonal_url, params)
