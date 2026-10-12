import { useCallback, useEffect, useRef, useState } from "react";
import { runOptimization, type RunHandle } from "../api";
import type {
  OptimizationRequest,
  RunErrorKind,
  RunOutcome,
  RunStatus,
  StepOut,
} from "../types";

const SLOW_STEP_MS = 15_000;

export interface RestoredRun {
  steps: StepOut[];
  outcome: RunOutcome | null;
  request: OptimizationRequest | null;
  failed: boolean;
}

export function useOptimization() {
  const [steps, setSteps] = useState<StepOut[]>([]);
  const [status, setStatus] = useState<RunStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [errorKind, setErrorKind] = useState<RunErrorKind | null>(null);
  const [outcome, setOutcome] = useState<RunOutcome | null>(null);
  const [slowStep, setSlowStep] = useState(false);
  // Request + timing of the most recent run, retained for the data export.
  const [lastRequest, setLastRequest] = useState<OptimizationRequest | null>(
    null,
  );
  const [wallClockMs, setWallClockMs] = useState<number | null>(null);
  const handleRef = useRef<RunHandle | null>(null);
  const startRef = useRef<number>(0);
  const clearOnNextStepRef = useRef(false);
  const slowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearSlowTimer = useCallback(() => {
    if (slowTimerRef.current) {
      clearTimeout(slowTimerRef.current);
      slowTimerRef.current = null;
    }
  }, []);

  const armSlowTimer = useCallback(() => {
    clearSlowTimer();
    slowTimerRef.current = setTimeout(() => setSlowStep(true), SLOW_STEP_MS);
  }, [clearSlowTimer]);

  const run = useCallback(
    (request: OptimizationRequest) => {
      handleRef.current?.dispose();
      clearOnNextStepRef.current = true;
      startRef.current = performance.now();

      setError(null);
      setErrorKind(null);
      setOutcome(null);
      setSlowStep(false);
      setLastRequest(request);
      setWallClockMs(null);
      setStatus("running");
      armSlowTimer();

      const finish = () => {
        clearSlowTimer();
        setSlowStep(false);
        setWallClockMs(performance.now() - startRef.current);
        if (clearOnNextStepRef.current) {
          clearOnNextStepRef.current = false;
          setSteps([]);
        }
      };

      handleRef.current = runOptimization(request, {
        onStep: (step) => {
          setSlowStep(false);
          armSlowTimer();
          if (clearOnNextStepRef.current) {
            clearOnNextStepRef.current = false;
            setSteps([step]);
          } else {
            setSteps((prev) => [...prev, step]);
          }
        },
        onEnd: (out) => {
          finish();
          setOutcome(out);
          setStatus("done");
        },
        onError: (detail, kind) => {
          finish();
          setError(detail);
          setErrorKind(kind);
          setStatus("error");
        },
      });
    },
    [armSlowTimer, clearSlowTimer],
  );

  const abort = useCallback(() => {
    handleRef.current?.stop();
  }, []);

  const restoreRun = useCallback(
    (restored: RestoredRun) => {
      handleRef.current?.dispose();
      handleRef.current = null;
      clearOnNextStepRef.current = false;
      clearSlowTimer();
      setSlowStep(false);
      setSteps(restored.steps);
      setStatus(restored.failed ? "error" : "done");
      setError(null);
      setErrorKind(null);
      setOutcome(restored.failed ? null : restored.outcome);
      setLastRequest(restored.request);
      setWallClockMs(null);
    },
    [clearSlowTimer],
  );

  useEffect(
    () => () => {
      handleRef.current?.dispose();
      clearSlowTimer();
    },
    [clearSlowTimer],
  );

  return {
    steps,
    status,
    error,
    errorKind,
    outcome,
    slowStep,
    lastRequest,
    wallClockMs,
    run,
    abort,
    restoreRun,
  };
}
