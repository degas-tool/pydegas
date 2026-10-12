import type { OptimizationRequest, StepOut } from "./types";

export interface ExportBundle {
  schema_version: 1;
  exported_at: string;
  // Terminal outcome or error kind from the run (see the run-outcome taxonomy).
  outcome: string;
  error: string | null;
  timing: {
    engine_compute_ms: number;
    wall_clock_ms: number | null;
    n_steps: number;
  };
  config: {
    program: string;
    program_language: string;
    optimizer: string;
    optimizer_kwargs: Record<string, unknown>;
    n_steps: number;
    tolerance: number | null;
    patience: number | null;
    smooth_eps: number | null;
    pruning?: string;
    initial_params: Record<string, number>;
    loss:
      | { mode: "builtin"; name: string; kwargs: Record<string, unknown> }
      | { mode: "custom"; source: string; bindings: Record<string, unknown> };
  };
  final_params: Record<string, number>;
  steps: Omit<StepOut, "dist">[];
}

export function buildExportBundle(args: {
  steps: StepOut[];
  request: OptimizationRequest;
  outcome: string;
  error: string | null;
  wallClockMs: number | null;
}): ExportBundle {
  const { steps, request, outcome, error, wallClockMs } = args;

  const engineComputeMs = steps.reduce((sum, s) => sum + (s.elapsed_ms ?? 0), 0);
  const finalParams = steps.at(-1)?.params ?? request.initial_params;

  const loss: ExportBundle["config"]["loss"] = request.loss_source
    ? {
        mode: "custom",
        source: request.loss_source,
        bindings: request.loss_bindings ?? {},
      }
    : {
        mode: "builtin",
        name: request.loss_function ?? "",
        kwargs: request.loss_kwargs ?? {},
      };

  return {
    schema_version: 1,
    exported_at: new Date().toISOString(),
    outcome,
    error,
    timing: {
      engine_compute_ms: engineComputeMs,
      wall_clock_ms: wallClockMs,
      n_steps: steps.length,
    },
    config: {
      program: request.program,
      program_language: request.program_language,
      optimizer: request.optimizer,
      optimizer_kwargs: request.optimizer_kwargs ?? {},
      n_steps: request.n_steps,
      tolerance: request.tolerance ?? null,
      patience: request.patience ?? null,
      smooth_eps: request.smooth_eps ?? null,
      pruning: request.pruning,
      initial_params: request.initial_params,
      loss,
    },
    final_params: finalParams,
    steps: steps.map(({ step, loss: stepLoss, params, elapsed_ms }) => ({
      step,
      loss: stepLoss,
      params,
      elapsed_ms,
    })),
  };
}

export function downloadBundle(bundle: ExportBundle, filename?: string): void {
  const name =
    filename ?? `degas-run-${bundle.exported_at.replace(/[:.]/g, "-")}.json`;
  const blob = new Blob([JSON.stringify(bundle, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
