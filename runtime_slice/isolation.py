from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BacktestBoundary:
    output_root: Path
    live_dependencies_enabled: bool = False
    secrets_available: bool = False
    production_execution: bool = False

    def __post_init__(self) -> None:
        if self.live_dependencies_enabled or self.secrets_available or self.production_execution:
            raise ValueError("backtest boundary cannot enable live dependencies, secrets, or production execution")

    def write_result(self, name: str, content: str) -> Path:
        root = self.output_root.resolve()
        target = (root / name).resolve()
        if root not in target.parents:
            raise ValueError("result path escapes isolated output root")
        root.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target


class IsolationGuard:
    FORBIDDEN_IMPORTS = tuple(
        name for name in ("redis", "pymysql", "mariadb", "clickhouse_driver", "ccxt", "requests", "boto3")
    )

    @classmethod
    def assert_source_safe(cls, source: str) -> None:
        lowered = source.lower()
        for name in cls.FORBIDDEN_IMPORTS:
            if f"import {name}" in lowered or f"from {name}" in lowered:
                raise AssertionError(f"forbidden external import: {name}")

    @staticmethod
    def assert_no_production_mode(mode: str, secrets: dict[str, Any]) -> None:
        if mode.lower() not in {"backtest", "mock", "sandbox"}:
            raise AssertionError("production execution mode is forbidden")
        if secrets:
            raise AssertionError("secrets are forbidden in local-only backtest")
