import type {
  LossFunctionInfo,
  LossMode,
  LossValidateResponse,
  OptimizationRequest,
  RunErrorKind,
  RunOutcome,
  SessionData,
  SessionSummary,
  StepOut,
} from "./types";

const BASE = "/api";

export interface ServerHealth {
  slots_free: number;
  max_concurrent: number;
}

export async function fetchHealth(): Promise<ServerHealth> {
  const res = await fetch("/health");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchLossFunctions(): Promise<LossFunctionInfo[]> {
  const res = await fetch(`${BASE}/optimization/loss-functions`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchOptimizers(): Promise<string[]> {
  const res = await fetch(`${BASE}/optimization/optimizers`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function validateLossSource(source: string): Promise<LossValidateResponse> {
  const res = await fetch(`${BASE}/optimization/loss/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface RunHandle {
  /** Ask the server to stop after the current step (sends a stop frame). */
  stop: () => void;
  /** Tear down the socket and detach handlers (no further callbacks fire). */
  dispose: () => void;
}

interface RunHandlers {
  onStep: (step: StepOut) => void;
  onEnd: (outcome: RunOutcome, converged: boolean, finalParams: Record<string, number>) => void;
  onError: (detail: string, kind: RunErrorKind) => void;
}


export async function createSession(payload: {
  loss_mode: LossMode;
  loss_name: string;
  request: string;
}): Promise<SessionData> {
  const res = await fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getSession(id: string): Promise<SessionData> {
  const res = await fetch(`${BASE}/sessions/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function patchSession(
  id: string,
  payload: { steps?: StepOut[]; status?: string; outcome?: string; name?: string },
  ownerToken?: string,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (ownerToken) headers["X-Owner-Token"] = ownerToken;
  await fetch(`${BASE}/sessions/${id}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(payload),
  });
}

export async function deleteSession(id: string, ownerToken: string): Promise<void> {
  await fetch(`${BASE}/sessions/${id}`, {
    method: "DELETE",
    headers: { "X-Owner-Token": ownerToken },
  });
}

export async function getSessions(limit = 50): Promise<SessionSummary[]> {
  const res = await fetch(`${BASE}/sessions?limit=${limit}`);
  if (!res.ok) return [];
  return res.json();
}

/** Open a WebSocket, run the optimization, and stream frames to the handlers. */
export function runOptimization(request: OptimizationRequest, handlers: RunHandlers): RunHandle {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${window.location.host}${BASE}/optimization/ws`);
  let settled = false; // true once an end/error frame arrived — suppresses the close→connection_lost fallback

  ws.onopen = () => ws.send(JSON.stringify(request));
  ws.onmessage = (ev) => {
    let m: { type?: string; [k: string]: unknown };
    try {
      m = JSON.parse(ev.data as string);
    } catch {
      return; // ignore malformed frames
    }
    if (m.type === "step") {
      handlers.onStep(m as unknown as StepOut);
    } else if (m.type === "end") {
      settled = true;
      handlers.onEnd(m.outcome as RunOutcome, m.converged as boolean, m.final_params as Record<string, number>);
    } else if (m.type === "error") {
      settled = true;
      handlers.onError(String(m.detail ?? "Optimization failed."), (m.kind as RunErrorKind) ?? "compute_error");
    }
    // "start" frames carry no UI state beyond what status already conveys.
  };
  ws.onclose = () => {
    if (!settled) {
      settled = true;
      handlers.onError("Connection lost. The run may have stopped on the server.", "connection_lost");
    }
  };

  return {
    stop: () => {
      // Any frame signals stop; the server replies with end{stopped} and closes.
      if (ws.readyState === WebSocket.OPEN) ws.send("stop");
      else ws.close();
    },
    dispose: () => {
      settled = true; // suppress the close→connection_lost fallback
      ws.onmessage = null;
      ws.onclose = null;
      try {
        ws.close();
      } catch {
        /* noop */
      }
    },
  };
}
