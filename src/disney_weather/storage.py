from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import json
from pydantic import BaseModel

from .models import ComparisonReport, ForecastSnapshot, FutureOutlook, PeriodWeather


class JsonRepository:
    def __init__(self, data_dir: Path, reports_dir: Path, web_generated_dir: Path) -> None:
        self.data_dir = data_dir
        self.reports_dir = reports_dir
        self.web_generated_dir = web_generated_dir
        self.historical_dir = data_dir / "queries" / "historical"
        self.future_dir = data_dir / "queries" / "future"
        self.forecast_dir = data_dir / "forecast_snapshots"
        self.comparison_dir = data_dir / "comparisons"
        for directory in (
            self.historical_dir,
            self.future_dir,
            self.forecast_dir,
            self.comparison_dir,
            self.reports_dir,
            self.web_generated_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _stamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    @staticmethod
    def _range(start_date: date, end_date: date) -> str:
        return f"{start_date.isoformat()}_{end_date.isoformat()}"

    @staticmethod
    def _write_model(path: Path, model: BaseModel) -> Path:
        path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        value: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
        return value

    def save_historical(self, result: PeriodWeather) -> Path:
        name = (
            f"historical_{self._range(result.requested_start, result.requested_end)}"
            f"__{self._stamp(result.retrieved_at_utc)}.json"
        )
        return self._write_model(self.historical_dir / name, result)

    def save_future(self, result: FutureOutlook) -> Path:
        name = (
            f"future_{self._range(result.requested_start, result.requested_end)}"
            f"__{self._stamp(result.generated_at_utc)}.json"
        )
        return self._write_model(self.future_dir / name, result)

    def save_forecast(self, snapshot: ForecastSnapshot) -> Path:
        name = (
            f"forecast_{self._range(snapshot.requested_start, snapshot.requested_end)}"
            f"__{self._stamp(snapshot.captured_at_utc)}.json"
        )
        return self._write_model(self.forecast_dir / name, snapshot)

    def save_comparison(self, report: ComparisonReport) -> Path:
        name = (
            f"comparison_{self._range(report.requested_start, report.requested_end)}"
            f"__forecast_{self._stamp(report.snapshot_captured_at_utc)}.json"
        )
        return self._write_model(self.comparison_dir / name, report)

    def load_forecasts(self) -> list[ForecastSnapshot]:
        return [
            ForecastSnapshot.model_validate(self._read_json(path))
            for path in sorted(self.forecast_dir.glob("forecast_*.json"))
        ]

    def write_report(self, name: str, content: str) -> Path:
        path = self.reports_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def publish_latest(self, model: BaseModel, markdown: str) -> None:
        self._write_model(self.web_generated_dir / "latest.json", model)
        (self.web_generated_dir / "latest.md").write_text(markdown, encoding="utf-8")
        metadata = {
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "query_type": model.model_dump().get("query_type", "unknown"),
            "latest_json": "latest.json",
            "latest_markdown": "latest.md",
        }
        (self.web_generated_dir / "catalog.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
