"""Placeholder scaffold tests for the health surface and app factory."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_healthz_returns_ok() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"status": "ok", "service": "rasoi-radar-api"}


def test_api_v1_ping() -> None:
    resp = client.get("/api/v1/ping")
    assert resp.status_code == 200
    assert resp.json()["message"] == "pong"


def test_unknown_route_is_problem_json() -> None:
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 404
    assert "title" in body
