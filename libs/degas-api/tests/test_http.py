from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydegas.optimize.losses import LOSS_REGISTRY
from pydegas.optimize.runner import OPTIMIZER_REGISTRY

from degas_api.server import create_app
from degas_api.settings import app_settings
from tests.support import L2_SOURCE


def test_health_reports_all_slots_free_without_limiter(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["slots_free"] == body["max_concurrent"] == 2
    assert isinstance(body["unix"], float)


def test_response_headers(client: TestClient) -> None:
    response = client.get("/health", headers={"DeGAS-Request-Id": "req_test"})

    assert response.headers["DeGAS-Request-Id"] == "req_test"
    assert response.headers["DeGAS-Api-Version"]
    assert float(response.headers["DeGAS-Request-Duration-ms"]) >= 0
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_generated_request_id(client: TestClient) -> None:
    assert client.get("/health").headers["DeGAS-Request-Id"].startswith("req_")


def test_root_redirects_to_docs(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_loss_functions(client: TestClient) -> None:
    response = client.get("/api/optimization/loss-functions")

    assert response.status_code == 200
    losses = {item["name"]: item for item in response.json()}
    assert set(losses) == set(LOSS_REGISTRY)
    assert [p["name"] for p in losses["l2_distance"]["params"]] == [
        "trajectories",
        "indices",
    ]
    assert losses["l2_distance"]["definition"].startswith("loss l2_distance")


def test_optimizers(client: TestClient) -> None:
    response = client.get("/api/optimization/optimizers")

    assert response.json() == list(OPTIMIZER_REGISTRY)


def test_pruning_strategies(client: TestClient) -> None:
    response = client.get("/api/optimization/pruning-strategies")

    assert response.json() == ["classic", "ranking", "kmeans"]


def test_validate_loss_returns_params(client: TestClient) -> None:
    response = client.post("/api/optimization/loss/validate", json={"source": L2_SOURCE})

    assert response.status_code == 200
    assert response.json() == {
        "errors": [],
        "params": [
            {"name": "trajectories", "type": "traj_set"},
            {"name": "indices", "type": "index_list"},
        ],
    }


def test_validate_loss_returns_errors(client: TestClient) -> None:
    response = client.post("/api/optimization/loss/validate", json={"source": "loss broken( ="})

    body = response.json()
    assert response.status_code == 200
    assert body["errors"]
    assert body["params"] == []


def test_validate_loss_rejects_oversized_source(client: TestClient) -> None:
    response = client.post("/api/optimization/loss/validate", json={"source": "x" * 20_001})

    assert response.status_code == 422


def test_trusted_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_settings, "allowed_hosts", ["localhost"])

    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 400
        assert client.get("/health", headers={"host": "localhost"}).status_code == 200


@pytest.fixture
def static_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>index</html>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    (static / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("secret")
    monkeypatch.setattr(app_settings, "static_dir", str(static))
    return TestClient(create_app())


def test_static_dir_serves_ui(static_client: TestClient) -> None:
    with static_client as client:
        assert client.get("/").text == "<html>index</html>"
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/favicon.svg").text == "<svg/>"
        assert client.get("/some/client/route").text == "<html>index</html>"


@pytest.mark.parametrize("path", ["/..%2Fsecret.txt", "/nested%2F..%2F..%2Fsecret.txt"])
def test_static_dir_does_not_serve_files_outside_it(static_client: TestClient, path: str) -> None:
    with static_client as client:
        response = client.get(path)

    assert "secret" not in response.text


def test_static_dir_does_not_answer_unknown_api_paths(static_client: TestClient) -> None:
    with static_client as client:
        assert client.get("/api/does-not-exist").status_code == 404
