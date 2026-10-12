import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlmodel import Session

from degas_api.db import get_engine, init_db
from degas_api.lifespan import cleanup_expired_sessions
from degas_api.models.session import OptimizationSession
from degas_api.routers.sessions import degas_now


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    payload = {
        "loss_mode": "builtin",
        "loss_name": "l2_distance",
        "request": json.dumps({"n_steps": 3}),
        **overrides,
    }
    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def expire(session_id: str) -> None:
    with Session(get_engine()) as db:
        row = db.get(OptimizationSession, session_id)
        assert row is not None
        row.expires_at = degas_now() - timedelta(seconds=1)
        db.add(row)
        db.commit()


def test_create_session(client: TestClient) -> None:
    session = create(client)

    assert len(session["id"]) == 8
    assert session["owner_token"]
    assert session["status"] == "running"
    assert session["steps"] == []
    assert session["name"] is None
    assert session["outcome"] is None
    assert json.loads(session["request"]) == {"n_steps": 3}


def test_read_session_bumps_expiry(client: TestClient) -> None:
    session = create(client)

    response = client.get(f"/api/sessions/{session['id']}")

    assert response.status_code == 200
    body = response.json()
    assert "owner_token" not in body
    assert body["expires_at"] >= session["expires_at"]


def test_read_missing_or_expired_session(client: TestClient) -> None:
    session = create(client)
    expire(session["id"])

    assert client.get(f"/api/sessions/{session['id']}").status_code == 404
    assert client.get("/api/sessions/missing").status_code == 404


def test_list_sessions_newest_first_without_expired(client: TestClient) -> None:
    older = create(client, loss_name="older")
    newer = create(client, loss_name="newer")
    gone = create(client, loss_name="gone")
    expire(gone["id"])

    response = client.get("/api/sessions", params={"limit": 100})

    ids = [item["id"] for item in response.json()]
    assert ids.index(newer["id"]) < ids.index(older["id"])
    assert gone["id"] not in ids
    assert set(response.json()[0]) == {
        "id",
        "created_at",
        "loss_mode",
        "loss_name",
        "name",
        "status",
        "outcome",
    }


def test_list_sessions_honours_limit(client: TestClient) -> None:
    create(client)
    create(client)

    assert len(client.get("/api/sessions", params={"limit": 1}).json()) == 1


@pytest.mark.parametrize("limit", [-1, 0, 101])
def test_list_sessions_rejects_out_of_range_limit(client: TestClient, limit: int) -> None:
    response = client.get("/api/sessions", params={"limit": limit})

    assert response.status_code == 422


def test_patch_results_without_token(client: TestClient) -> None:
    session = create(client)
    steps = [{"step": 0, "loss": 1.5}]

    response = client.patch(
        f"/api/sessions/{session['id']}",
        json={"steps": steps, "status": "done", "outcome": "converged"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["steps"] == steps
    assert body["status"] == "done"
    assert body["outcome"] == "converged"


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Owner-Token": "wrong"}, {"X-Owner-Token": "t\u00f6ken".encode("latin-1")}],
    ids=["missing", "wrong", "non-ascii"],
)
def test_rename_needs_the_owner_token(client: TestClient, headers: dict[str, Any]) -> None:
    session = create(client)

    response = client.patch(f"/api/sessions/{session['id']}", json={"name": "mine"}, headers=headers)

    assert response.status_code == 403
    assert client.get(f"/api/sessions/{session['id']}").json()["name"] is None


def test_rename_and_clear_name_with_token(client: TestClient) -> None:
    session = create(client)
    url = f"/api/sessions/{session['id']}"
    headers = {"X-Owner-Token": session["owner_token"]}

    assert client.patch(url, json={"name": "  run 1 "}, headers=headers).json()["name"] == "run 1"
    assert client.patch(url, json={"name": "   "}, headers=headers).json()["name"] is None


def test_patch_missing_session(client: TestClient) -> None:
    assert client.patch("/api/sessions/missing", json={"status": "done"}).status_code == 404


@pytest.mark.parametrize("token", [None, "wrong"])
def test_delete_needs_the_owner_token(client: TestClient, token: str | None) -> None:
    session = create(client)
    headers = {"X-Owner-Token": token} if token else {}

    response = client.delete(f"/api/sessions/{session['id']}", headers=headers)

    assert response.status_code == 403
    assert client.get(f"/api/sessions/{session['id']}").status_code == 200


def test_delete_with_token(client: TestClient) -> None:
    session = create(client)
    url = f"/api/sessions/{session['id']}"

    response = client.delete(url, headers={"X-Owner-Token": session["owner_token"]})

    assert response.status_code == 204
    assert client.get(url).status_code == 404
    assert client.delete(url, headers={"X-Owner-Token": session["owner_token"]}).status_code == 404


def test_cleanup_removes_only_expired_sessions(client: TestClient) -> None:
    kept = create(client)
    gone = create(client)
    expire(gone["id"])

    assert cleanup_expired_sessions() >= 1

    with Session(get_engine()) as db:
        assert db.get(OptimizationSession, gone["id"]) is None
        assert db.get(OptimizationSession, kept["id"]) is not None


def test_init_db_tolerates_a_table_created_by_another_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = str(tmp_path / "race.db")
    init_db(path)
    monkeypatch.setattr(SQLiteDialect, "has_table", lambda *args, **kwargs: False)

    init_db(path)

    with Session(get_engine()) as db:
        assert db.get(OptimizationSession, "missing") is None
