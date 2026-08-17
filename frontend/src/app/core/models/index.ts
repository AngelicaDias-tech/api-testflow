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

// Request EFETIVAMENTE montado e enviado (melhoria 2) — sempre mascarado.
export interface SentRequest {
  method: string
  url: string
  query_params: Record<string, string>
  headers: Record<string, string>
  auth_type: string
  body: string | null
  body_type: string
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
  // detalhe técnico do erro (não é um segredo, mas fica escondido por
  // padrão na UI — só a mensagem amigável em `error` é exibida direto).
  error_detail?: string | null
  // explicação amigável do status_code (ex: o que um 401/404/500 costuma
  // significar) — null para 2xx/3xx, onde não há nada a explicar.
  status_message?: string | null
  discovered_checks: Check[]
  sent_request?: SentRequest | null
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
  scenario_id?: string | null
  row_index?: number | null
  variables_used?: Record<string, unknown> | null
  sent_request?: SentRequest | null
  results: TestResult[]
}

// Cenário de teste manual (painel "Cenários de Teste"): um conjunto nomeado
// de variáveis que alimenta os placeholders {{var}} da API na hora de
// executar, sem alterar a configuração original salva. Nome diferente de
// `Scenario` (acima) de propósito — aquele é o cenário de VALOR sugerido
// pela IA para uma regra ("Função 2"), um conceito diferente.
export interface TestScenario {
  id: string
  request_id: string
  name: string
  variables: Record<string, unknown>
  created_at: string
}

// Massa de teste via CSV — cada `rows[i]` alimenta os mesmos placeholders
// {{var}} que um TestScenario, só que em lote (ver core/services/api.service.ts).
export interface CsvImportPreview {
  columns: string[]
  rows: Record<string, unknown>[]
  errors: string[]
}

export interface TestDataSet {
  id: string
  request_id: string
  name: string
  columns: string[]
  rows: Record<string, unknown>[]
  created_at: string
}

export interface BatchExecutionRow {
  row_index: number
  variables: Record<string, unknown>
  execution_id: string
  outcome: 'passed' | 'failed' | 'error'
  total: number
  passed: number
  failed: number
}

// Exportar/Importar testes — o bundle é tratado como opaco pelo frontend
// (ele só baixa/lê o JSON e reenvia; quem valida a estrutura é o backend).
export interface ExportBundle {
  testflow_export_version: string
  exported_at: string
  project: { name: string; description: string | null }
  requests: unknown[]
}

export interface ImportSummary {
  project: Project
  requests_imported: number
  rules_imported: number
  scenarios_imported: number
  datasets_imported: number
  requests_needing_auth: string[]
  warnings: string[]
}

export interface BatchExecution {
  id: string
  request_id: string
  dataset_id: string
  started_at: string
  finished_at: string | null
  total_cases: number
  passed_cases: number
  failed_cases: number
  status: string
  rows: BatchExecutionRow[]
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
