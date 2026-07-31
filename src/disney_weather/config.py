from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True, slots=True)
class Settings:
    latitude: float = 28.3772
    longitude: float = -81.5707
    timezone: str = "America/New_York"
    location_name: str = "Walt Disney World Resort, Orlando"
    max_window_days: int = 15
    forecast_horizon_days: int = 16
    seasonal_horizon_days: int = 210
    climate_reference_years: int = 10
    data_dir: Path = Path("data")
    reports_dir: Path = Path("reports")
    web_generated_dir: Path = Path("docs/generated")
    forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    seasonal_url: str = "https://seasonal-api.open-meteo.com/v1/seasonal"
    request_timeout_seconds: float = 45.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            latitude=float(os.getenv("WEATHER_LATITUDE", "28.3772")),
            longitude=float(os.getenv("WEATHER_LONGITUDE", "-81.5707")),
            timezone=os.getenv("WEATHER_TIMEZONE", "America/New_York"),
            location_name=os.getenv(
                "WEATHER_LOCATION_NAME", "Walt Disney World Resort, Orlando"
            ),
            max_window_days=int(os.getenv("WEATHER_MAX_WINDOW_DAYS", "15")),
            forecast_horizon_days=int(os.getenv("WEATHER_FORECAST_HORIZON_DAYS", "16")),
            seasonal_horizon_days=int(os.getenv("WEATHER_SEASONAL_HORIZON_DAYS", "210")),
            climate_reference_years=int(os.getenv("WEATHER_CLIMATE_YEARS", "10")),
            data_dir=Path(os.getenv("WEATHER_DATA_DIR", "data")),
            reports_dir=Path(os.getenv("WEATHER_REPORTS_DIR", "reports")),
            web_generated_dir=Path(os.getenv("WEATHER_WEB_GENERATED_DIR", "docs/generated")),
            forecast_url=os.getenv(
                "WEATHER_FORECAST_URL", "https://api.open-meteo.com/v1/forecast"
            ),
            archive_url=os.getenv(
                "WEATHER_ARCHIVE_URL", "https://archive-api.open-meteo.com/v1/archive"
            ),
            seasonal_url=os.getenv(
                "WEATHER_SEASONAL_URL", "https://seasonal-api.open-meteo.com/v1/seasonal"
            ),
            request_timeout_seconds=float(os.getenv("WEATHER_TIMEOUT_SECONDS", "45")),
        )
