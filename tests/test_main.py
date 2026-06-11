"""main(FastAPI health/metrics) 테스트 — fastapi 미설치 환경에서는 skip."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")


def test_health_and_metrics_routes() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
