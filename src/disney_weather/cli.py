from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from .config import Settings
from .provider import OpenMeteoProvider
from .reporting import (
    render_comparison,
    render_forecast,
    render_future,
    render_historical,
)
from .service import WeatherQueryService
from .storage import JsonRepository


def build_service() -> WeatherQueryService:
    settings = Settings.from_env()
    repository = JsonRepository(
        settings.data_dir, settings.reports_dir, settings.web_generated_dir
    )
    provider = OpenMeteoProvider(settings)
    return WeatherQueryService(settings, provider, repository)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Usá el formato YYYY-MM-DD") from exc


def _report_name(operation: str, start_date: date, end_date: date) -> str:
    return f"{operation}_{start_date}_{end_date}.md"


def _write_and_publish(
    service: WeatherQueryService,
    operation: str,
    start_date: date,
    end_date: date,
    model: BaseModel,
    markdown: str,
) -> Path:
    path = service.repository.write_report(
        _report_name(operation, start_date, end_date), markdown
    )
    service.repository.write_report("latest.md", markdown)
    service.repository.publish_latest(model, markdown)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consultas meteorológicas manuales para Disney Orlando"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("historical", "future", "capture", "compare"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--start", required=True, type=_parse_date)
        command_parser.add_argument("--end", required=True, type=_parse_date)
        if command == "future":
            command_parser.add_argument("--climate-years", type=int, default=10)

    args = parser.parse_args()
    service = build_service()
    start_date: date = args.start
    end_date: date = args.end

    if args.command == "historical":
        result = service.query_historical(start_date, end_date)
        markdown = render_historical(result)
        path = _write_and_publish(
            service, "historical", start_date, end_date, result, markdown
        )
        print(f"historical_ok days={len(result.daily)} report={path}")
        return

    if args.command == "future":
        result = service.query_future(
            start_date, end_date, climate_years=args.climate_years
        )
        markdown = render_future(result)
        path = _write_and_publish(
            service, "future", start_date, end_date, result, markdown
        )
        print(
            "future_ok "
            f"live_days={len(result.live_forecast)} "
            f"seasonal_days={len(result.seasonal_estimate)} report={path}"
        )
        return

    if args.command == "capture":
        result = service.capture_forecast(start_date, end_date)
        markdown = render_forecast(result)
        path = _write_and_publish(
            service, "capture", start_date, end_date, result, markdown
        )
        print(f"capture_ok days={len(result.daily)} report={path}")
        return

    reports = service.compare_saved_forecasts(start_date, end_date)
    if not reports:
        raise RuntimeError("No se generaron comparaciones")
    for index, report in enumerate(reports, start=1):
        markdown = render_comparison(report)
        name = (
            f"comparison_{start_date}_{end_date}__"
            f"{report.snapshot_captured_at_utc:%Y%m%dT%H%M%SZ}.md"
        )
        path = service.repository.write_report(name, markdown)
        if index == len(reports):
            service.repository.write_report("latest.md", markdown)
            service.repository.publish_latest(report, markdown)
        print(f"comparison_ok rows={len(report.daily)} report={path}")


if __name__ == "__main__":
    main()
