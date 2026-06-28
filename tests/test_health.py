from fastapi.testclient import TestClient
from src.main import app
from src import health

client = TestClient(app)


async def _ok():
    return {"status": "ok"}


async def _down():
    return {"status": "error", "message": "boom"}


def test_live_is_public_and_200():
    r = client.get('/health/live')
    assert r.status_code == 200 and r.json()['alive'] is True


def test_ready_200_when_dependencies_ok(monkeypatch):
    monkeypatch.setattr(health, 'check_postgres', _ok)
    monkeypatch.setattr(health, 'check_redis', _ok)
    r = client.get('/health/ready')
    assert r.status_code == 200
    assert r.json()['ready'] is True


def test_ready_503_when_dependency_down(monkeypatch):
    monkeypatch.setattr(health, 'check_postgres', _down)
    monkeypatch.setattr(health, 'check_redis', _ok)
    r = client.get('/health/ready')
    assert r.status_code == 503
    assert r.json()['ready'] is False
