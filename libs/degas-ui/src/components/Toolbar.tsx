import { useMemo, useState } from "react";
import { EXAMPLES, type Example } from "../examples";
import type {
  LossFunctionInfo,
  LossMode,
  LossParamInfo,
  OptimizationRequest,
  RunStatus,
} from "../types";

function toNumber(s: string): number {
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}

function toInt(s: string): number {
  const n = parseInt(s, 10);
  return isNaN(n) ? 0 : n;
}

const SELECT: React.CSSProperties = {
  background: "var(--btn-bg)",
  border: "1px solid var(--btn-border)",
  borderRadius: 6,
  color: "var(--text-primary)",
  fontSize: 12,
  padding: "4px 6px",
  cursor: "pointer",
  fontFamily: "inherit",
};

const INPUT: React.CSSProperties = {
  ...SELECT,
  cursor: "text",
  width: 72,
  textAlign: "right",
};

const LABEL: React.CSSProperties = {
  fontSize: 11,
  color: "var(--text-muted)",
  whiteSpace: "nowrap",
};

const GROUP_LABEL: React.CSSProperties = {
  fontSize: 10,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  fontWeight: 600,
  color: "var(--text-muted)",
  whiteSpace: "nowrap",
  minWidth: 96,
};

const ROW: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  flexWrap: "wrap",
};

const TIP = {
  optimizer:
    "torch.optim optimizer used to update the parameters each step (Adam, AdamW, SGD, RMSprop, Adagrad, LBFGS). ",
  lr: "Learning rate handed to the torch optimizer.",
  steps:
    "Maximum number of gradient-descent steps. Each step recomputes the output distribution, evaluates the loss, and updates the parameters; the run stops early if it converges.",
  tol: "Convergence threshold on loss change: the run is flagged converged when the loss moves by less than this between every step in the patience window. Empty disables early stopping.",
  patience:
    "Number of consecutive steps whose loss must stay within tol before the run is flagged converged.",
  smoothEps:
    "Smoothing width applied by smooth() to conditional branches so gradients can flow through them.",
  loss: "Objective minimized over the program's output distribution. Switch to 'custom' to view/edit each definition in the loss editor.",
  initialParam:
    "Initial value of this optimized parameter. Each _par becomes a grad-tracked tensor the optimizer updates from this starting point.",
};

const LOSS_ARG_TIP: Record<string, string> = {
  trajectories:
    "Observed trajectory data (CSV): one row per trajectory, columns selected by 'indices'. Compared against the model's output marginals.",
  indices:
    "Indices of the output variables to score against the data (0-based). Auto-filled from the uploaded CSV's columns.",
  target:
    "Constant value the output mean trace is driven toward (signal_error).",
  time_steps:
    "Number of time steps signal_error sums over (indices 1…time_steps-1). Must not exceed the program's variable count.",
};

const DSL_TYPE_TIP: Record<string, string> = {
  traj_set: "Trajectory matrix (CSV) bound to this traj_set parameter.",
  index_list: "Comma-separated integer indices bound to this index_list parameter.",
  scalar: "Scalar value bound to this parameter.",
  int: "Integer value bound to this parameter.",
};

interface CsvUploadProps {
  shape: [number, number] | null; // [rows, cols] after a file is loaded
  disabled: boolean;
  onLoad: (rows: number[][], cols: number) => void;
}

function CsvUpload({ shape, disabled, onLoad }: CsvUploadProps) {
  const [dragging, setDragging] = useState(false);

  function processFile(file: File) {
    const reader = new FileReader();
    reader.onload = (ev) => {
      const rows = (ev.target?.result as string)
        .trim()
        .split("\n")
        .filter((l) => l.trim())
        .map((l) => l.split(",").map((s) => parseFloat(s.trim())));
      if (rows.length === 0 || rows[0].length === 0) return;
      onLoad(rows, rows[0].length);
    };
    reader.readAsText(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    processFile(file);
    e.target.value = "";
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
      onDragEnter={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      style={{
        ...SELECT,
        position: "relative",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        padding: "4px 10px",
        whiteSpace: "nowrap",
        display: "inline-flex",
        alignItems: "center",
        userSelect: "none",
        outline: dragging ? "2px dashed var(--text-primary)" : "none",
        outlineOffset: 2,
      }}
    >
      {!disabled && (
        <input
          type="file"
          accept=".csv,.txt"
          onChange={handleChange}
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0,
            cursor: "pointer",
            width: "100%",
            height: "100%",
          }}
        />
      )}
      {shape ? `${shape[0]} × ${shape[1]} ✓` : dragging ? "drop CSV" : "drag / click"}
    </div>
  );
}

interface Props {
  program: string;
  lossMode: LossMode;
  lossSource: string;
  lossName: string;
  onLossNameChange: (name: string) => void;
  dslParams: LossParamInfo[];
  dslErrors: string[];
  onLossModeChange: (mode: LossMode) => void;
  lossFunctions: LossFunctionInfo[];
  optimizers: string[];
  status: RunStatus;
  onRun: (req: OptimizationRequest) => void;
  onAbort: () => void;
  onSelectExample: (ex: Example) => void;
}

export function Toolbar({
  program,
  lossMode,
  lossSource,
  lossName,
  onLossNameChange,
  dslParams,
  dslErrors,
  onLossModeChange,
  lossFunctions,
  optimizers,
  status,
  onRun,
  onAbort,
  onSelectExample,
}: Props) {
  const firstExample = EXAMPLES[0];

  const [selectedExample, setSelectedExample] = useState(firstExample.label);
  const [optimizer, setOptimizer] = useState(firstExample.optimizer);
  const [lossKwargs, setLossKwargs] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(firstExample.loss_kwargs).map(([k, v]) => [k, String(v)]),
    ),
  );
  const [paramValues, setParamValues] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(firstExample.initial_params).map(([k, v]) => [
        k,
        String(v),
      ]),
    ),
  );
  const [nSteps, setNSteps] = useState(String(firstExample.n_steps));
  const [lr, setLr] = useState("0.2");
  const [tolerance, setTolerance] = useState("1e-8");
  const [patience, setPatience] = useState("30");
  const [smoothEps, setSmoothEps] = useState("0.001");

  // shape of the most recently uploaded trajectory, keyed by param name
  const [trajShapes, setTrajShapes] = useState<
    Record<string, [number, number]>
  >({});

  const [dslBindings, setDslBindings] = useState<Record<string, string>>({});
  const [dslTrajShapes, setDslTrajShapes] = useState<Record<string, [number, number]>>({});

  const [lastProgram, setLastProgram] = useState(program);
  if (program !== lastProgram) {
    setLastProgram(program);
    const matched = EXAMPLES.find((ex) => ex.program.trim() === program.trim());
    setSelectedExample(matched ? matched.label : "Custom");
    const names = [...new Set(
      [...program.matchAll(/_([a-zA-Z][a-zA-Z0-9]*)/g)].map((m) => m[1])
    )];
    const next: Record<string, string> = {};
    for (const name of names) next[name] = paramValues[name] ?? "0";
    setParamValues(next);
  }

  const selectedLossInfo = useMemo(
    () => lossFunctions.find((l) => l.name === lossName) ?? null,
    [lossFunctions, lossName],
  );

  function handleExampleChange(label: string) {
    const ex = EXAMPLES.find((e) => e.label === label);
    if (!ex) return;
    setSelectedExample(label);
    setOptimizer(ex.optimizer);
    onLossNameChange(ex.loss_function);
    setLossKwargs(
      Object.fromEntries(
        Object.entries(ex.loss_kwargs).map(([k, v]) => [k, String(v)]),
      ),
    );
    setParamValues(
      Object.fromEntries(
        Object.entries(ex.initial_params).map(([k, v]) => [k, String(v)]),
      ),
    );
    setNSteps(String(ex.n_steps));
    setTrajShapes({});
    onSelectExample(ex);
  }

  function handleTrajLoad(
    paramName: string,
    indicesParamName: string | undefined,
    rows: number[][],
    cols: number,
  ) {
    const json = JSON.stringify(rows);
    setLossKwargs((prev) => {
      const next = { ...prev, [paramName]: json };
      // auto-fill indices as 0…cols-1 if the indices field is empty
      if (indicesParamName && !prev[indicesParamName]) {
        next[indicesParamName] = Array.from({ length: cols }, (_, i) => i).join(
          ", ",
        );
      }
      return next;
    });
    setTrajShapes((prev) => ({ ...prev, [paramName]: [rows.length, cols] }));
  }

  function buildRequest(): OptimizationRequest {
    const trimmedTol = tolerance.trim();
    const tolNum = trimmedTol === "" ? null : parseFloat(trimmedTol);

    const trimmedEps = smoothEps.trim();
    const epsNum = trimmedEps === "" ? null : parseFloat(trimmedEps);

    const base = {
      program,
      program_language: "soga_highlevel" as const,
      compile_seed: 0,
      optimizer,
      optimizer_kwargs: { lr: toNumber(lr) },
      initial_params: Object.fromEntries(
        Object.entries(paramValues).map(([k, v]) => [k, toNumber(v)]),
      ),
      n_steps: toInt(nSteps),
      tolerance: tolNum !== null && isNaN(tolNum) ? null : tolNum,
      patience: toInt(patience) || 30,
      smooth_eps: epsNum !== null && isNaN(epsNum) ? null : epsNum,
      return_dist_summary: true,
    };

    if (lossMode === "custom") {
      const parsedBindings: Record<string, unknown> = {};
      for (const p of dslParams) {
        const raw = dslBindings[p.name] ?? "";
        if (p.type === "traj_set") {
          try { parsedBindings[p.name] = JSON.parse(raw); } catch { /* skip */ }
        } else if (p.type === "index_list") {
          parsedBindings[p.name] = raw.split(",").map((s) => toInt(s.trim())).filter((n) => !isNaN(n));
        } else if (p.type === "scalar") {
          parsedBindings[p.name] = toNumber(raw);
        } else if (p.type === "int") {
          parsedBindings[p.name] = toInt(raw);
        } else {
          try { parsedBindings[p.name] = JSON.parse(raw); } catch { parsedBindings[p.name] = raw; }
        }
      }
      return { ...base, loss_kwargs: {}, loss_source: lossSource, loss_bindings: parsedBindings };
    }

    const parsedLossKwargs: Record<string, unknown> = {};
    const schemaParams = selectedLossInfo?.params ?? [];
    if (schemaParams.length > 0) {
      for (const p of schemaParams) {
        const raw = lossKwargs[p.name] ?? "";
        if (p.type === "float") parsedLossKwargs[p.name] = toNumber(raw);
        else if (p.type === "int") parsedLossKwargs[p.name] = toInt(raw);
        else if (p.type === "int[]")
          parsedLossKwargs[p.name] = raw.split(",").map((s) => toInt(s.trim()));
        else {
          try { parsedLossKwargs[p.name] = JSON.parse(raw); } catch { /* leave out */ }
        }
      }
    } else {
      for (const [k, v] of Object.entries(lossKwargs)) {
        const n = toNumber(v);
        if (!isNaN(n)) parsedLossKwargs[k] = n;
      }
    }
    return { ...base, loss_function: lossName, loss_kwargs: parsedLossKwargs };
  }

  const running = status === "running";
  const params = selectedLossInfo?.params ?? [];
  const canRun = lossMode === "builtin" || dslErrors.length === 0;
  const hasLossArgs = (lossMode === "builtin" ? params.length : dslParams.length) > 0;

  // find the name of the indices param that accompanies a trajectories param
  function indicesParamFor(trajParamName: string): string | undefined {
    const idx = params.findIndex((p) => p.name === trajParamName);
    return params.slice(idx + 1).find((p) => p.type === "int[]")?.name;
  }

  return (
    <div
      style={{
        borderTop: "1px solid var(--border)",
        padding: "10px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        background: "var(--bg-surface)",
      }}
    >
      <div style={{ ...ROW, justifyContent: "space-between" }}>
        <div style={ROW}>
          <select
            style={SELECT}
            value={selectedExample}
            onChange={(e) => handleExampleChange(e.target.value)}
          >
            {selectedExample === "Custom" && (
              <option value="Custom" disabled>Custom</option>
            )}
            {EXAMPLES.map((ex) => (
              <option key={ex.label}>{ex.label}</option>
            ))}
          </select>

          <div style={{ width: 1, height: 16, background: "var(--border)" }} />

          <span style={LABEL} title={TIP.optimizer}>optimizer</span>
          <select
            style={SELECT}
            value={optimizer}
            onChange={(e) => setOptimizer(e.target.value)}
            disabled={running}
            title={TIP.optimizer}
          >
            {optimizers.length === 0 ? (
              <option>Adam</option>
            ) : (
              optimizers.map((o) => <option key={o}>{o}</option>)
            )}
          </select>

          <button
            type="button"
            style={{
              ...SELECT,
              background: lossMode === "custom" ? "#6699cc22" : undefined,
              borderColor: lossMode === "custom" ? "#6699cc" : undefined,
              color: lossMode === "custom" ? "#6699cc" : undefined,
              cursor: running ? "not-allowed" : "pointer",
            }}
            onClick={() => onLossModeChange(lossMode === "custom" ? "builtin" : "custom")}
            disabled={running}
            title={lossMode === "custom" ? "Switch to built-in loss" : "Write a custom loss function"}
          >
            custom
          </button>

          {lossMode === "builtin" && (
            <>
              <span style={LABEL} title={TIP.loss}>loss</span>
              <select
                style={SELECT}
                value={lossName}
                onChange={(e) => onLossNameChange(e.target.value)}
                disabled={running}
                title={TIP.loss}
              >
                {lossFunctions.length === 0 ? (
                  <option>signal_error</option>
                ) : (
                  lossFunctions.map((l) => <option key={l.name}>{l.name}</option>)
                )}
              </select>
            </>
          )}
        </div>

        <div style={ROW}>
          <span style={LABEL} title={TIP.lr}>lr</span>
          <input
            type="text"
            inputMode="decimal"
            style={{ ...INPUT, width: 56 }}
            value={lr}
            onChange={(e) => setLr(e.target.value)}
            disabled={running}
          />

          <span style={LABEL} title={TIP.steps}>
            steps{optimizer === 'LBFGS' && (
              <span title="LBFGS runs up to 20 inner iterations per step" style={{ color: '#fac863', marginLeft: 3 }}>⚠</span>
            )}
          </span>
          <input
            type="number"
            style={{ ...INPUT, width: 56 }}
            value={nSteps}
            min={1}
            onChange={(e) => setNSteps(e.target.value)}
            disabled={running}
          />

          <span
            style={LABEL}
            title={TIP.tol}
          >tol</span>
          <input
            type="text"
            style={{ ...INPUT, width: 56 }}
            value={tolerance}
            placeholder="off"
            onChange={(e) => setTolerance(e.target.value)}
            disabled={running}
          />

          <span
            style={LABEL}
            title={TIP.patience}
          >patience</span>
          <input
            type="number"
            style={{ ...INPUT, width: 48 }}
            value={patience}
            min={1}
            onChange={(e) => setPatience(e.target.value)}
            disabled={running}
          />

          <span
            style={LABEL}
            title={TIP.smoothEps}
          >smooth_eps</span>
          <input
            type="text"
            inputMode="decimal"
            style={{ ...INPUT, width: 56 }}
            value={smoothEps}
            placeholder="0.001"
            onChange={(e) => setSmoothEps(e.target.value)}
            disabled={running}
          />

          <button
            type="button"
            onClick={running ? onAbort : () => onRun(buildRequest())}
            title={running ? "Stop" : canRun ? "Run" : "Fix loss errors before running"}
            disabled={!running && !canRun}
            style={{
              width: 34,
              height: 34,
              borderRadius: "50%",
              border: "none",
              background: running ? "#c0392b" : canRun ? "#6699cc" : "#555",
              color: "#fff",
              fontSize: 14,
              cursor: running ? "pointer" : canRun ? "pointer" : "not-allowed",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              transition: "background 0.15s",
              opacity: !running && !canRun ? 0.5 : 1,
            }}
          >
            {running ? "■" : "▶"}
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {hasLossArgs && (
          <div style={{ ...ROW, gap: 12 }}>
            <span style={GROUP_LABEL}>loss arguments</span>
        {lossMode === "builtin" && params.map((p) => (
          <div key={p.name} style={ROW}>
            <span style={LABEL} title={LOSS_ARG_TIP[p.name]}>{p.name}</span>
            {p.type === "float[][]" ? (
              <CsvUpload
                shape={trajShapes[p.name] ?? null}
                disabled={running}
                onLoad={(rows, cols) =>
                  handleTrajLoad(p.name, indicesParamFor(p.name), rows, cols)
                }
              />
            ) : p.type === "int[]" ? (
              <input
                style={{ ...INPUT, width: 140 }}
                placeholder="0, 1, 2…"
                value={lossKwargs[p.name] ?? ""}
                onChange={(e) =>
                  setLossKwargs((prev) => ({ ...prev, [p.name]: e.target.value }))
                }
                disabled={running}
              />
            ) : (
              <input
                type="number"
                style={INPUT}
                value={lossKwargs[p.name] ?? (p.default != null ? String(p.default) : "")}
                onChange={(e) =>
                  setLossKwargs((prev) => ({ ...prev, [p.name]: e.target.value }))
                }
                disabled={running}
              />
            )}
          </div>
        ))}

        {lossMode === "custom" && dslParams.map((p) => (
          <div key={p.name} style={ROW}>
            <span style={LABEL} title={p.type ? DSL_TYPE_TIP[p.type] : undefined}>{p.name}</span>
            {p.type === "traj_set" ? (
              <CsvUpload
                shape={dslTrajShapes[p.name] ?? null}
                disabled={running}
                onLoad={(rows, cols) => {
                  setDslBindings((prev) => ({ ...prev, [p.name]: JSON.stringify(rows) }));
                  setDslTrajShapes((prev) => ({ ...prev, [p.name]: [rows.length, cols] }));
                }}
              />
            ) : p.type === "index_list" ? (
              <input
                style={{ ...INPUT, width: 140 }}
                placeholder="0, 1, 2…"
                value={dslBindings[p.name] ?? ""}
                onChange={(e) =>
                  setDslBindings((prev) => ({ ...prev, [p.name]: e.target.value }))
                }
                disabled={running}
              />
            ) : p.type === "scalar" ? (
              <input
                type="text"
                inputMode="decimal"
                style={INPUT}
                value={dslBindings[p.name] ?? ""}
                onChange={(e) =>
                  setDslBindings((prev) => ({ ...prev, [p.name]: e.target.value }))
                }
                disabled={running}
              />
            ) : p.type === "int" ? (
              <input
                type="number"
                style={INPUT}
                step={1}
                value={dslBindings[p.name] ?? ""}
                onChange={(e) =>
                  setDslBindings((prev) => ({ ...prev, [p.name]: e.target.value }))
                }
                disabled={running}
              />
            ) : (
              <input
                style={{ ...INPUT, width: 120 }}
                placeholder="JSON"
                value={dslBindings[p.name] ?? ""}
                onChange={(e) =>
                  setDslBindings((prev) => ({ ...prev, [p.name]: e.target.value }))
                }
                disabled={running}
              />
            )}
          </div>
        ))}

          </div>
        )}

        {Object.keys(paramValues).length > 0 && (
          <div style={{ ...ROW, gap: 12 }}>
            <span style={GROUP_LABEL}>initial parameters</span>
        {Object.keys(paramValues).map((name) => (
          <div key={name} style={ROW}>
            <span style={{ ...LABEL, color: "#f99157" }} title={TIP.initialParam}>_{name}</span>
            <input
              type="number"
              style={INPUT}
              value={paramValues[name]}
              onChange={(e) =>
                setParamValues((prev) => ({ ...prev, [name]: e.target.value }))
              }
              disabled={running}
            />
          </div>
        ))}
          </div>
        )}
      </div>
    </div>
  );
}
