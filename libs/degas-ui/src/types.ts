export type ParamType = 'float' | 'int' | 'float[][]' | 'int[]'

export interface LossParamDef {
  name: string
  type: ParamType
  required: boolean
  default?: number | null
}

export interface LossFunctionInfo {
  name: string
  params: LossParamDef[]
  definition?: string | null
}

export interface StepOut {
  step: number
  loss: number
  params: Record<string, number>
  elapsed_ms: number
  dist: { var_list: string[]; mean: number[] } | null
}

export type DslParamType = 'traj_set' | 'index_list' | 'scalar' | 'int' | null

export interface LossParamInfo {
  name: string
  type: DslParamType
}

export interface LossValidateResponse {
  errors: string[]
  params: LossParamInfo[]
}

export type LossMode = 'builtin' | 'custom'

export interface OptimizationRequest {
  program: string
  program_language: 'soga' | 'soga_highlevel'
  compile_seed: number
  loss_function?: string
  loss_kwargs: Record<string, unknown>
  loss_source?: string
  loss_bindings?: Record<string, unknown>
  optimizer: string
  optimizer_kwargs: Record<string, unknown>
  initial_params: Record<string, number>
  n_steps: number
  return_dist_summary: boolean
  tolerance?: number | null
  patience?: number
  smooth_eps?: number | null
  pruning?: 'classic' | 'ranking' | 'kmeans'
}

export type RunStatus = 'idle' | 'running' | 'done' | 'error'

export interface SessionData {
  id: string
  created_at: string
  expires_at: string
  loss_mode: LossMode
  loss_name: string
  name: string | null
  request: string  // serialised OptimizationRequest JSON
  steps: StepOut[]
  status: string
  outcome: string | null
  owner_token?: string  // only present in the create response
}

export interface SessionSummary {
  id: string
  created_at: string
  loss_mode: LossMode
  loss_name: string
  name: string | null
  status: string
  outcome: string | null
}

// Terminal outcome of a run that produced results (sent on the `end` frame).
// See docs/feedback-2026-06/08-run-outcome/taxonomy.md.
export type RunOutcome = 'converged' | 'not_converged' | 'stopped' | 'run_timeout'

// Failure modes (sent on the `error` frame, or derived client-side for a
// dropped socket), each rendered with a distinct message.
export type RunErrorKind =
  | 'setup_error'
  | 'compute_error'
  | 'rate_limited'
  | 'at_capacity'
  | 'connection_lost'
