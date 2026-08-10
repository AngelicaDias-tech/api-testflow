import type {
  Check,
  Execution,
  ExecutionSummary,
  GenerateRulesResult,
  ImportPreview,
  NegativeCase,
  ProbeResult,
  Project,
  RequestDef,
  Rule,
  Scenario,
} from '../types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// Projects
export const listProjects = () => request<Project[]>('/projects')
export const createProject = (name: string, description?: string) =>
  request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name, description }) })
export const deleteProject = (id: string) => request<void>(`/projects/${id}`, { method: 'DELETE' })

// Import
export const importCurl = (curl_command: string) =>
  request<ImportPreview>('/import/curl', { method: 'POST', body: JSON.stringify({ curl_command }) })
export const importBruno = (bru_content: string) =>
  request<ImportPreview>('/import/bruno', { method: 'POST', body: JSON.stringify({ bru_content }) })

// Requests
export const listRequests = (projectId: string) => request<RequestDef[]>(`/requests?project_id=${projectId}`)
export const getRequest = (id: string) => request<RequestDef>(`/requests/${id}`)
export const createRequest = (payload: Partial<RequestDef> & { project_id: string; name: string; url: string }) =>
  request<RequestDef>('/requests', { method: 'POST', body: JSON.stringify(payload) })
export const updateRequest = (id: string, payload: Partial<RequestDef>) =>
  request<RequestDef>(`/requests/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
export const deleteRequest = (id: string) => request<void>(`/requests/${id}`, { method: 'DELETE' })
export const probeRequest = (id: string, confirm = false) =>
  request<ProbeResult>(`/requests/${id}/probe?confirm=${confirm}`, { method: 'POST' })

// Rules
export const listRules = (requestId: string) => request<Rule[]>(`/requests/${requestId}/rules`)
export const createRule = (requestId: string, rule: Partial<Check>) =>
  request<Rule>(`/requests/${requestId}/rules`, { method: 'POST', body: JSON.stringify(rule) })
export const createRulesBulk = (requestId: string, rules: Partial<Check>[]) =>
  request<Rule[]>(`/requests/${requestId}/rules/bulk`, { method: 'POST', body: JSON.stringify({ rules }) })
export const updateRule = (requestId: string, ruleId: string, payload: Partial<Rule>) =>
  request<Rule>(`/requests/${requestId}/rules/${ruleId}`, { method: 'PUT', body: JSON.stringify(payload) })
export const deleteRule = (requestId: string, ruleId: string) =>
  request<void>(`/requests/${requestId}/rules/${ruleId}`, { method: 'DELETE' })

// Executions
export const executeTests = (requestId: string, confirm = false) =>
  request<Execution>(`/requests/${requestId}/execute?confirm=${confirm}`, { method: 'POST' })
export const listExecutions = (requestId: string) => request<ExecutionSummary[]>(`/requests/${requestId}/executions`)
export const getExecution = (executionId: string) => request<Execution>(`/executions/${executionId}`)

// AI
export const aiStatus = () => request<{ name: string; available: boolean }>('/ai/status')
export const aiSuggestFromResponse = (response_ctx: unknown, discovered_checks: Check[]) =>
  request<{ summary: string; suggestions: Check[] }>('/ai/suggest-from-response', {
    method: 'POST',
    body: JSON.stringify({ response_ctx, discovered_checks }),
  })
export const aiSuggestNegativeCases = (requestId: string) =>
  request<NegativeCase[]>(`/ai/requests/${requestId}/suggest-negative-cases`, { method: 'POST' })
export const aiExplainFailure = (resultId: string) =>
  request<{ explanation: string }>(`/ai/results/${resultId}/explain`, { method: 'POST' })
export const aiAnswerQuestion = (question: string, response_ctx: unknown) =>
  request<{ answer: string }>('/ai/answer-question', {
    method: 'POST',
    body: JSON.stringify({ question, response_ctx }),
  })
// Função 1: sintaxe técnica explícita, uma regra por linha — determinístico.
export const aiGenerateRules = (text: string, response_ctx?: unknown) =>
  request<GenerateRulesResult>('/ai/generate-rules', { method: 'POST', body: JSON.stringify({ text, response_ctx }) })
// Função 2: cenários de valor para uma regra já estruturada.
export const aiSuggestScenarios = (check: Partial<Check>) =>
  request<{ scenarios: Scenario[] }>('/ai/suggest-scenarios', { method: 'POST', body: JSON.stringify({ check }) })
