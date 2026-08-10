export interface Project {
  id: string
  name: string
  description: string | null
  created_at: string
}

export interface AuthDef {
  type: 'none' | 'bearer' | 'basic' | 'api_key' | 'custom'
  token?: string
  username?: string
  password?: string
  // api_key/key_name também são reaproveitados pelo tipo 'custom' (header
  // personalizado: mesmo formato nome+valor, sempre enviado como header).
  api_key?: string
  key_name?: string
  location?: 'header' | 'query'
}

export interface RequestDef {
  id: string
  project_id: string
  name: string
  method: string
  url: string
  headers: Record<string, string>
  query_params: Record<string, string>
  body: string | null
  body_type: string
  auth: AuthDef
  is_mutating: boolean
  created_at: string
  updated_at: string
  last_status_code: number | null
  last_response_time_ms: number | null
  last_probed_at: string | null
}

export interface ImportPreview {
  name?: string | null
  method: string
  url: string
  headers: Record<string, string>
  query_params: Record<string, string>
  body: string | null
  body_type: string
  auth: AuthDef
  warnings: string[]
}

export interface Check {
  id: string
  source: 'auto' | 'custom' | 'ai_suggested'
  category: string
  field: string | null
  operator: string
  expected: unknown
  description: string
  enabled?: boolean
  confidence?: number
  raw_text?: string
  // regra condicional sobre lista (ex: "clientes PREMIUM devem estar ativos") — opcional
  array_path?: string | null
  condition_field?: string | null
  condition_operator?: string | null
  condition_expected?: unknown
}

export interface ProbeResult {
  status_code: number | null
  headers: Record<string, string>
  content_type: string
  body_raw: string
  body_json: unknown
  json_valid: boolean
  response_time_ms: number
  error: string | null
  discovered_checks: Check[]
}

export interface Rule {
  id: string
  request_id: string
  source: string
  category: string
  field: string | null
  operator: string
  expected: string | null
  description: string
  enabled: boolean
  created_at: string
  array_path?: string | null
  condition_field?: string | null
  condition_operator?: string | null
  condition_expected?: string | null
}

export interface TestResult {
  id: string
  execution_id: string
  rule_id: string | null
  node_id: string
  name: string
  source: string
  category: string
  field: string | null
  operator: string | null
  expected: string | null
  actual: string | null
  outcome: 'passed' | 'failed' | 'skipped' | 'error'
  message: string | null
  duration_ms: number | null
}

export interface Execution {
  id: string
  request_id: string
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  total: number
  passed: number
  failed: number
  skipped: number
  status: string
  error_message: string | null
  results: TestResult[]
}

export interface ExecutionSummary {
  id: string
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  total: number
  passed: number
  failed: number
  skipped: number
  status: string
}

export interface NegativeCase {
  id: string
  title: string
  description: string
  method: string
  expected_status: number
  is_mutating: boolean
  requires_confirmation: boolean
  safe_to_auto_run: boolean
}

// Função 1 ("Gerar regras"): sintaxe técnica explícita, determinística —
// uma linha que não bate com um campo real vira `errors`, nunca uma regra
// inventada.
export interface GenerateRulesResult {
  rules: Check[]
  errors: string[]
}

// Função 2 ("Sugerir cenários"): valores de exemplo para UMA regra já
// estruturada — só informativo, pytest é quem decide de fato quando/se o
// usuário optar por rodar um desses valores.
export interface Scenario {
  value: unknown
  expected_outcome: 'PASS' | 'FAIL'
  description: string
}

export const OPERATORS = [
  { value: 'equals', label: 'igual a (equals)' },
  { value: 'not_equals', label: 'diferente de (not_equals)' },
  { value: 'contains', label: 'contém (contains)' },
  { value: 'not_contains', label: 'não contém (not_contains)' },
  { value: 'starts_with', label: 'começa com (starts_with)' },
  { value: 'ends_with', label: 'termina com (ends_with)' },
  { value: 'greater_than', label: 'maior que (greater_than)' },
  { value: 'greater_than_or_equal', label: 'maior ou igual (greater_than_or_equal)' },
  { value: 'less_than', label: 'menor que (less_than)' },
  { value: 'less_than_or_equal', label: 'menor ou igual (less_than_or_equal)' },
  { value: 'matches_regex', label: 'corresponde a regex (matches_regex)' },
  { value: 'exists', label: 'existe (exists)' },
  { value: 'not_exists', label: 'não existe (not_exists)' },
  { value: 'type_is', label: 'tipo é (type_is)' },
  { value: 'is_email_format', label: 'formato de email (is_email_format)' },
] as const
