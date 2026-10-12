from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from degas_api.settings import app_settings
from tests.support import L2_SOURCE, RUN_REQUEST, WS_PATH, collect_frames, run_frames


STEP_KEYS = {"type", "step", "loss", "params", "elapsed_ms", "dist"}


def assert_setup_error(frames: list[dict[str, Any]], *fragments: str) -> None:
    assert len(frames) == 1, frames
    error = frames[0]
    assert error["type"] == "error"
    assert error["kind"] == "setup_error"
    for fragment in fragments:
        assert fragment in error["detail"]


def test_run_streams_start_steps_and_end(client: TestClient) -> None:
    frames = run_frames(client, RUN_REQUEST)

    assert frames[0] == {"type": "start", "n_steps": 3}
    steps = frames[1:-1]
    assert [frame["step"] for frame in steps] == [0, 1, 2]
    for frame in steps:
        assert set(frame) == STEP_KEYS
        assert set(frame["params"]) == {"tOff"}
        assert frame["dist"]["var_list"]
        assert len(frame["dist"]["mean"]) == len(frame["dist"]["var_list"])
    assert frames[-1] == {
        "type": "end",
        "outcome": "not_converged",
        "converged": False,
        "final_params": steps[-1]["params"],
    }


def test_run_without_dist_summary(client: TestClient) -> None:
    frames = run_frames(client, {**RUN_REQUEST, "n_steps": 1, "return_dist_summary": False})

    assert frames[1]["type"] == "step"
    assert frames[1]["dist"] is None


def test_run_reports_convergence(client: TestClient) -> None:
    frames = run_frames(client, {**RUN_REQUEST, "n_steps": 10, "tolerance": 1e9, "patience": 1})

    steps = [frame for frame in frames if frame["type"] == "step"]
    assert len(steps) == 2
    assert frames[-1]["outcome"] == "converged"
    assert frames[-1]["converged"] is True


def test_run_timeout(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_settings.optimization_limits, "max_run_seconds", 0)

    frames = run_frames(client, {**RUN_REQUEST, "n_steps": 50})

    assert [frame["type"] for frame in frames] == ["start", "step", "end"]
    assert frames[-1]["outcome"] == "run_timeout"


def test_run_with_custom_loss(client: TestClient) -> None:
    request = {
        **RUN_REQUEST,
        "loss_function": None,
        "loss_kwargs": {},
        "loss_source": L2_SOURCE,
        "loss_bindings": {"trajectories": [[16.0, 15.5, 15.0]], "indices": [0, 1, 2]},
    }

    frames = run_frames(client, request)

    assert frames[-1]["type"] == "end"
    assert frames[-1]["outcome"] == "not_converged"


def test_non_finite_step_is_a_compute_error(client: TestClient) -> None:
    request = {
        **RUN_REQUEST,
        "loss_function": None,
        "loss_kwargs": {},
        "loss_source": (
            "loss bad(distribution: dist, indices: index_list) =\n"
            "    sum( log( distribution.mean[indices] - distribution.mean[indices] ) )\n"
        ),
        "loss_bindings": {"indices": [0, 1]},
    }

    frames = run_frames(client, request)

    assert frames[0]["type"] == "start"
    assert frames[-1]["type"] == "error"
    assert frames[-1]["kind"] == "compute_error"
    assert "non-finite" in frames[-1]["detail"]
    assert all(frame["type"] != "step" for frame in frames)


@pytest.mark.parametrize("send", ["text", "bytes"])
def test_any_client_frame_stops_the_run(client: TestClient, send: str) -> None:
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_json({**RUN_REQUEST, "n_steps": 500})
        assert ws.receive_json() == {"type": "start", "n_steps": 500}
        if send == "text":
            ws.send_text("stop")
        else:
            ws.send_bytes(b"\x00")
        frames = collect_frames(ws)

    end = frames[-1]
    assert end["type"] == "end"
    assert end["outcome"] == "stopped"
    assert all(frame["type"] == "step" for frame in frames[:-1])
    if frames[:-1]:
        assert end["final_params"] == frames[-2]["params"]


def test_kmax_at_limit_is_rejected_with_correct_wording(client: TestClient) -> None:
    frames = run_frames(client, {**RUN_REQUEST, "Kmax": 100})

    assert_setup_error(frames, "Kmax=100 must be below 100", "Kmax=null")
    assert "minimum" not in frames[0]["detail"]


def test_kmax_below_limit_and_null_are_accepted(client: TestClient) -> None:
    for kmax in (99, None):
        frames = run_frames(client, {**RUN_REQUEST, "n_steps": 1, "Kmax": kmax})
        assert frames[-1]["type"] == "end", frames


@pytest.mark.parametrize("kmax", [0, -3])
def test_non_positive_kmax_is_a_setup_error(client: TestClient, kmax: int) -> None:
    frames = run_frames(client, {**RUN_REQUEST, "Kmax": kmax})

    assert_setup_error(frames, "Invalid request: Kmax: Input should be greater than or equal to 1")


@pytest.mark.parametrize("n_steps", [0, -5])
def test_non_positive_n_steps_is_a_setup_error(client: TestClient, n_steps: int) -> None:
    frames = run_frames(client, {**RUN_REQUEST, "n_steps": n_steps})

    assert_setup_error(frames, "Invalid request: n_steps: Input should be greater than or equal to 1")


def test_n_steps_over_limit(client: TestClient) -> None:
    frames = run_frames(client, {**RUN_REQUEST, "n_steps": 501})

    assert frames == [
        {
            "type": "error",
            "kind": "setup_error",
            "detail": "n_steps=501 exceeds the maximum of 500.",
        }
    ]


def test_missing_builtin_loss_argument_is_a_setup_error(client: TestClient) -> None:
    request = {**RUN_REQUEST, "loss_kwargs": {"trajectories": [[16.0, 15.5, 15.0]]}}

    frames = run_frames(client, request)

    assert_setup_error(frames, "indices")


def test_unknown_optimizer_argument_is_a_setup_error(client: TestClient) -> None:
    frames = run_frames(client, {**RUN_REQUEST, "optimizer_kwargs": {"foo": 1}})

    assert_setup_error(frames, "foo")


def test_unknown_optimizer_is_a_setup_error(client: TestClient) -> None:
    frames = run_frames(client, {**RUN_REQUEST, "optimizer": "Nope"})

    assert_setup_error(frames, "Unknown optimizer name 'Nope'")


def test_program_syntax_error_is_a_setup_error(client: TestClient) -> None:
    request = {**RUN_REQUEST, "program": "this is not a program", "program_language": "soga"}

    frames = run_frames(client, request)

    assert len(frames) == 1
    assert frames[0]["kind"] == "setup_error"


@pytest.mark.parametrize(
    ("bindings", "fragment"),
    [
        ({"trajectories": [[16.0, 15.5, 15.0]], "indices": 2}, "binding 'indices' must be a list of integers."),
        ({"trajectories": [[16.0, 15.5, 15.0]], "indices": ["a"]}, "binding 'indices' must be a list of integers."),
        ({"trajectories": [16.0, 15.5], "indices": [0]}, "binding 'trajectories' must be a 2-D array."),
        ({"trajectories": 3, "indices": [0]}, "binding 'trajectories' must be a 2-D array."),
    ],
)
def test_malformed_custom_loss_bindings_are_setup_errors(
    client: TestClient, bindings: dict[str, Any], fragment: str
) -> None:
    request = {
        **RUN_REQUEST,
        "loss_function": None,
        "loss_kwargs": {},
        "loss_source": L2_SOURCE,
        "loss_bindings": bindings,
    }

    frames = run_frames(client, request)

    assert_setup_error(frames, fragment)


def test_malformed_builtin_trajectories_are_a_setup_error(client: TestClient) -> None:
    request = {**RUN_REQUEST, "loss_kwargs": {"trajectories": [1.0, 2.0], "indices": [0]}}

    frames = run_frames(client, request)

    assert_setup_error(frames, "trajectories must be a 2-D array.")


def test_oversized_trajectories_are_a_setup_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_settings.optimization_limits, "max_trajectory_rows", 1)
    request = {
        **RUN_REQUEST,
        "loss_kwargs": {"trajectories": [[16.0, 15.5, 15.0]] * 2, "indices": [0]},
    }

    frames = run_frames(client, request)

    assert_setup_error(frames, "trajectories exceeds the trajectory size limits.")


def test_empty_loss_source_needs_a_loss_function(client: TestClient) -> None:
    request = {**RUN_REQUEST, "loss_function": None, "loss_source": ""}

    frames = run_frames(client, request)

    assert_setup_error(frames, "Invalid request: Either loss_function or loss_source must be provided.")


def test_validation_errors_are_listed_per_field(client: TestClient) -> None:
    request = {key: value for key, value in RUN_REQUEST.items() if key != "optimizer"}

    frames = run_frames(client, {**request, "n_steps": "many"})

    detail = frames[0]["detail"]
    assert detail.startswith("Invalid request: ")
    assert "optimizer: Field required" in detail
    assert "n_steps: Input should be a valid integer" in detail
    assert "errors.pydantic.dev" not in detail


def test_invalid_json_is_a_setup_error(client: TestClient) -> None:
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_text("{not json")
        frames = collect_frames(ws)

    assert_setup_error(frames, "Invalid request: ")


def test_binary_request_frame_is_a_setup_error(client: TestClient) -> None:
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_bytes(b"{}")
        frames = collect_frames(ws)

    assert_setup_error(frames, "Invalid request: the request must be sent as a JSON text message.")


class FakeLimiter:
    def __init__(self, *, allow: bool = True, slot: bool = True, fail: bool = False) -> None:
        self.allow = allow
        self.slot = slot
        self.fail = fail
        self.acquired = 0
        self.released = 0
        self.undone = 0

    async def check_rate_limit(self, client_ip: str) -> tuple[bool, int]:
        if self.fail:
            raise ConnectionError("redis is down")
        return self.allow, 7

    async def try_acquire_slot(self) -> bool:
        if self.slot:
            self.acquired += 1
        return self.slot

    async def release_slot(self) -> None:
        self.released += 1

    async def undo_rate_limit_entry(self, client_ip: str) -> None:
        self.undone += 1

    async def slots_free(self) -> int:
        return 1


def test_rate_limited(app: FastAPI, client: TestClient) -> None:
    app.state.orl_limiter = FakeLimiter(allow=False)

    frames = run_frames(client, RUN_REQUEST)

    assert frames == [
        {
            "type": "error",
            "kind": "rate_limited",
            "detail": "Too many optimization requests from this address.",
        }
    ]


def test_at_capacity_undoes_the_rate_limit_entry(app: FastAPI, client: TestClient) -> None:
    limiter = FakeLimiter(slot=False)
    app.state.orl_limiter = limiter

    frames = run_frames(client, RUN_REQUEST)

    assert len(frames) == 1
    assert frames[0]["kind"] == "at_capacity"
    assert limiter.undone == 1


def test_unavailable_limiter_is_a_setup_error(app: FastAPI, client: TestClient) -> None:
    app.state.orl_limiter = FakeLimiter(fail=True)

    frames = run_frames(client, RUN_REQUEST)

    assert_setup_error(frames, "rate limiter is unavailable")


@pytest.mark.parametrize(
    "request_patch",
    [{}, {"optimizer": "Nope"}, {"n_steps": 500}],
    ids=["finished", "setup-error", "stopped"],
)
def test_slot_is_released_after_every_admitted_run(
    app: FastAPI, client: TestClient, request_patch: dict[str, Any]
) -> None:
    limiter = FakeLimiter()
    app.state.orl_limiter = limiter

    with client.websocket_connect(WS_PATH) as ws:
        ws.send_json({**RUN_REQUEST, **request_patch})
        first = ws.receive_json()
        if first["type"] == "start" and request_patch.get("n_steps") == 500:
            ws.send_text("stop")
        if first["type"] == "start":
            collect_frames(ws)

    assert limiter.acquired == 1
    assert limiter.released == 1


def test_health_uses_the_limiter(app: FastAPI, client: TestClient) -> None:
    app.state.orl_limiter = FakeLimiter()

    assert client.get("/health").json()["slots_free"] == 1


def test_validate_loss_rate_limited(app: FastAPI, client: TestClient) -> None:
    app.state.orl_limiter = FakeLimiter(allow=False)

    response = client.post("/api/optimization/loss/validate", json={"source": L2_SOURCE})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
