import { Injectable, inject } from '@angular/core'
import { HttpClient, HttpErrorResponse } from '@angular/common/http'
import { firstValueFrom } from 'rxjs'
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
} from '../models'
import { ApiError } from './api-error'

const BASE = '/api'

/**
 * Porta 1:1 de frontend/src/lib/api.ts (React) para um serviço Angular
 * único injetável. Mesmos endpoints, mesmo contrato de erro (ApiError com
 * status + mensagem do campo "detail" do FastAPI) — nenhum endpoint novo,
 * nenhum removido, nenhuma lógica de negócio alterada.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient)

  private request<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
    const { method = 'GET', body } = options
    return firstValueFrom(
      this.http.request<T>(method, `${BASE}${path}`, {
        body,
        headers: { 'Content-Type': 'application/json' },
      }),
    ).catch((err: unknown) => {
      if (err instanceof HttpErrorResponse) {
        const detail = (err.error && typeof err.error === 'object' && 'detail' in err.error
          ? (err.error as { detail?: string }).detail
          : undefined) ?? err.statusText ?? err.message
        throw new ApiError(err.status, detail)
      }
      throw err
    })
  }

  // Projects
  listProjects = () => this.request<Project[]>('/projects')
  createProject = (name: string, description?: string) =>
    this.request<Project>('/projects', { method: 'POST', body: { name, description } })
  deleteProject = (id: string) => this.request<void>(`/projects/${id}`, { method: 'DELETE' })

  // Import
  importCurl = (curl_command: string) =>
    this.request<ImportPreview>('/import/curl', { method: 'POST', body: { curl_command } })
  importBruno = (bru_content: string) =>
    this.request<ImportPreview>('/import/bruno', { method: 'POST', body: { bru_content } })

  // Requests
  listRequests = (projectId: string) => this.request<RequestDef[]>(`/requests?project_id=${projectId}`)
  getRequest = (id: string) => this.request<RequestDef>(`/requests/${id}`)
  createRequest = (payload: Partial<RequestDef> & { project_id: string; name: string; url: string }) =>
    this.request<RequestDef>('/requests', { method: 'POST', body: payload })
  updateRequest = (id: string, payload: Partial<RequestDef>) =>
    this.request<RequestDef>(`/requests/${id}`, { method: 'PUT', body: payload })
  deleteRequest = (id: string) => this.request<void>(`/requests/${id}`, { method: 'DELETE' })
  probeRequest = (id: string, confirm = false) =>
    this.request<ProbeResult>(`/requests/${id}/probe?confirm=${confirm}`, { method: 'POST' })

  // Rules
  listRules = (requestId: string) => this.request<Rule[]>(`/requests/${requestId}/rules`)
  createRule = (requestId: string, rule: Partial<Check>) =>
    this.request<Rule>(`/requests/${requestId}/rules`, { method: 'POST', body: rule })
  createRulesBulk = (requestId: string, rules: Partial<Check>[]) =>
    this.request<Rule[]>(`/requests/${requestId}/rules/bulk`, { method: 'POST', body: { rules } })
  updateRule = (requestId: string, ruleId: string, payload: Partial<Rule>) =>
    this.request<Rule>(`/requests/${requestId}/rules/${ruleId}`, { method: 'PUT', body: payload })
  deleteRule = (requestId: string, ruleId: string) =>
    this.request<void>(`/requests/${requestId}/rules/${ruleId}`, { method: 'DELETE' })

  // Executions
  executeTests = (requestId: string, confirm = false) =>
    this.request<Execution>(`/requests/${requestId}/execute?confirm=${confirm}`, { method: 'POST' })
  listExecutions = (requestId: string) => this.request<ExecutionSummary[]>(`/requests/${requestId}/executions`)
  getExecution = (executionId: string) => this.request<Execution>(`/executions/${executionId}`)

  // AI
  aiStatus = () => this.request<{ name: string; available: boolean }>('/ai/status')
  aiSuggestFromResponse = (response_ctx: unknown, discovered_checks: Check[]) =>
    this.request<{ summary: string; suggestions: Check[] }>('/ai/suggest-from-response', {
      method: 'POST',
      body: { response_ctx, discovered_checks },
    })
  aiSuggestNegativeCases = (requestId: string) =>
    this.request<NegativeCase[]>(`/ai/requests/${requestId}/suggest-negative-cases`, { method: 'POST' })
  aiExplainFailure = (resultId: string) =>
    this.request<{ explanation: string }>(`/ai/results/${resultId}/explain`, { method: 'POST' })
  aiAnswerQuestion = (question: string, response_ctx: unknown) =>
    this.request<{ answer: string }>('/ai/answer-question', { method: 'POST', body: { question, response_ctx } })
  // Função 1: sintaxe técnica explícita, uma regra por linha — determinístico.
  aiGenerateRules = (text: string, response_ctx?: unknown) =>
    this.request<GenerateRulesResult>('/ai/generate-rules', { method: 'POST', body: { text, response_ctx } })
  // Função 2: cenários de valor para uma regra já estruturada.
  aiSuggestScenarios = (check: Partial<Check>) =>
    this.request<{ scenarios: Scenario[] }>('/ai/suggest-scenarios', { method: 'POST', body: { check } })
}
