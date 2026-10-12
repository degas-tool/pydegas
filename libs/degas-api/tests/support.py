from typing import Any

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession


WS_PATH = "/api/optimization/ws"

THERMOSTAT = (
    "array[3] T;\n"
    "currT = 16;\n"
    "for i in range(3) {\n"
    "T[i] = currT;\n"
    "if currT > _tOff { heat = -0.5; } else { heat = 0.5; } end if;\n"
    "currT = currT + heat + gauss(0., 0.1);\n"
    "} end for;"
)

RUN_REQUEST: dict[str, Any] = {
    "program": THERMOSTAT,
    "program_language": "soga_highlevel",
    "compile_seed": 0,
    "optimizer": "Adam",
    "optimizer_kwargs": {"lr": 0.1},
    "initial_params": {"tOff": 16.0},
    "loss_function": "l2_distance",
    "loss_kwargs": {"trajectories": [[16.0, 15.5, 15.0]], "indices": [0, 1, 2]},
    "n_steps": 3,
    "tolerance": None,
}

L2_SOURCE = (
    "loss l2(trajectories: traj_set, distribution: dist, indices: index_list) =\n"
    "    sum( (trajectories[:, indices] - distribution.mean[indices]) ^ 2 )\n"
)


def collect_frames(ws: WebSocketTestSession) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    while True:
        frame = ws.receive_json()
        frames.append(frame)
        if frame["type"] in ("end", "error"):
            return frames


def run_frames(client: TestClient, request: Any) -> list[dict[str, Any]]:
    with client.websocket_connect(WS_PATH) as ws:
        ws.send_json(request)
        return collect_frames(ws)
