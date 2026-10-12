import { useCallback, useEffect, useRef, useState } from 'react'
import { runOptimization, type RunHandle } from '../api'
import type { OptimizationRequest, RunErrorKind, RunOutcome, RunStatus, StepOut } from '../types'

const SLOW_STEP_MS = 15_000

export function useOptimization() {
  const [steps, setSteps] = useState<StepOut[]>([])
  const [status, setStatus] = useState<RunStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [errorKind, setErrorKind] = useState<RunErrorKind | null>(null)
  const [outcome, setOutcome] = useState<RunOutcome | null>(null)
  const [slowStep, setSlowStep] = useState(false)
  // Request + timing of the most recent run, retained for the data export.
  const [lastRequest, setLastRequest] = useState<OptimizationRequest | null>(null)
  const [wallClockMs, setWallClockMs] = useState<number | null>(null)
  const handleRef = useRef<RunHandle | null>(null)
  const startRef = useRef<number>(0)
  const clearOnNextStepRef = useRef(false)
  const slowTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function clearSlowTimer() {
    if (slowTimerRef.current) {
      clearTimeout(slowTimerRef.current)
      slowTimerRef.current = null
    }
  }

  function armSlowTimer() {
    clearSlowTimer()
    slowTimerRef.current = setTimeout(() => setSlowStep(true), SLOW_STEP_MS)
  }

  const run = useCallback((request: OptimizationRequest) => {
    handleRef.current?.dispose()
    clearOnNextStepRef.current = true
    startRef.current = performance.now()

    setError(null)
    setErrorKind(null)
    setOutcome(null)
    setSlowStep(false)
    setLastRequest(request)
    setWallClockMs(null)
    setStatus('running')
    armSlowTimer()

    handleRef.current = runOptimization(request, {
      onStep: (step) => {
        setSlowStep(false)
        armSlowTimer()
        if (clearOnNextStepRef.current) {
          clearOnNextStepRef.current = false
          setSteps([step])
        } else {
          setSteps((prev) => [...prev, step])
        }
      },
      onEnd: (out) => {
        clearSlowTimer()
        setSlowStep(false)
        setOutcome(out)
        setWallClockMs(performance.now() - startRef.current)
        setStatus('done')
      },
      onError: (detail, kind) => {
        clearSlowTimer()
        setSlowStep(false)
        setError(detail)
        setErrorKind(kind)
        setWallClockMs(performance.now() - startRef.current)
        setStatus('error')
      },
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const abort = useCallback(() => {
    handleRef.current?.stop()
  }, [])

  const restoreSteps = useCallback((restoredSteps: StepOut[], restoredOutcome: RunOutcome | null = null) => {
    handleRef.current?.dispose()
    clearSlowTimer()
    setSlowStep(false)
    setSteps(restoredSteps)
    setStatus('done')
    setError(null)
    setErrorKind(null)
    setOutcome(restoredOutcome)
    setLastRequest(null)
    setWallClockMs(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => () => {
    handleRef.current?.dispose()
    clearSlowTimer()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { steps, status, error, errorKind, outcome, slowStep, lastRequest, wallClockMs, run, abort, restoreSteps }
}
