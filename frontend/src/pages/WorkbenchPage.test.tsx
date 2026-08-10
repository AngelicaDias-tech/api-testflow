import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom'
import WorkbenchPage from './WorkbenchPage'
import * as api from '../lib/api'
import type { ProbeResult, RequestDef, Rule } from '../types'

/**
 * Regressão do bug: "voltar da tela de resultado apaga o JSON da API e
 * força o usuário a clicar em Testar API de novo". A causa era guardar a
 * última resposta em useState local de WorkbenchPage — useState reseta
 * sempre que o componente desmonta (o que acontece ao navegar para a tela
 * de execução). A resposta agora vive no cache do React Query (chave
 * ['probe', requestId], ver WorkbenchPage.tsx), que sobrevive à
 * desmontagem/remontagem do componente. Só mockamos app/lib/api — os
 * componentes filhos (ResponseViewer, ManualBusinessRules, etc.) são
 * renderizados de verdade para provar que a UI real continua mostrando a
 * resposta.
 */
vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    getRequest: vi.fn(),
    listRules: vi.fn(),
    probeRequest: vi.fn(),
    createRule: vi.fn(),
    createRulesBulk: vi.fn(),
    deleteRule: vi.fn(),
    executeTests: vi.fn(),
  }
})

const mockReq: RequestDef = {
  id: 'req-1',
  project_id: 'proj-1',
  name: 'Hello-World AI scope test',
  method: 'GET',
  url: 'https://api.github.com/repos/octocat/Hello-World',
  headers: {},
  query_params: {},
  body: null,
  body_type: 'none',
  auth: { type: 'none' },
  is_mutating: false,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  last_status_code: null,
  last_response_time_ms: null,
  last_probed_at: null,
}

const mockProbe: ProbeResult = {
  status_code: 200,
  headers: { 'x-request-id': 'abc-123-xyz' },
  content_type: 'application/json',
  body_raw: '{"name":"Hello-World","stargazers_count":3755}',
  body_json: { name: 'Hello-World', stargazers_count: 3755 },
  json_valid: true,
  response_time_ms: 123,
  error: null,
  discovered_checks: [],
}

const approvedRule: Rule = {
  id: 'rule-1',
  request_id: 'req-1',
  source: 'custom',
  category: 'field',
  field: 'stargazers_count',
  operator: 'greater_than',
  expected: '100',
  description: 'stargazers_count greater_than 100',
  enabled: true,
  created_at: '2026-01-01T00:00:00',
}

function renderWorkbench() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/projects/proj-1/requests/req-1']}>
        <Routes>
          <Route path="/projects/:projectId/requests/:requestId" element={<WorkbenchPage />} />
          <Route
            path="/projects/:projectId/requests/:requestId/executions/:executionId"
            element={<Link to="/projects/proj-1/requests/req-1">← Voltar para a API</Link>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.getRequest).mockResolvedValue(mockReq)
  vi.mocked(api.listRules).mockResolvedValue([approvedRule])
  vi.mocked(api.probeRequest).mockResolvedValue(mockProbe)
  vi.mocked(api.executeTests).mockResolvedValue({
    id: 'exec-1',
    request_id: 'req-1',
    started_at: '',
    finished_at: '',
    duration_ms: 0,
    total: 1,
    passed: 1,
    failed: 0,
    skipped: 0,
    status: 'completed',
    error_message: null,
    results: [],
  })
})

describe('WorkbenchPage — persistência da resposta da API entre telas', () => {
  it('não chama a API sozinho: só depois de clicar em "Testar API" a resposta aparece', async () => {
    renderWorkbench()
    await screen.findByText(mockReq.name)

    expect(api.probeRequest).not.toHaveBeenCalled()
    expect(screen.queryByText('HTTP 200')).not.toBeInTheDocument()
  })

  it('chama a API e guarda a resposta (JSON, status code, headers, campos mapeados) ao clicar em "Testar API"', async () => {
    const user = userEvent.setup()
    renderWorkbench()
    await screen.findByText(mockReq.name)

    await user.click(screen.getByRole('button', { name: /testar api/i }))

    await screen.findByText('HTTP 200')
    expect(api.probeRequest).toHaveBeenCalledTimes(1)
    // status code
    expect(screen.getByText('HTTP 200')).toBeInTheDocument()
    // headers
    expect(screen.getByText(/abc-123-xyz/)).toBeInTheDocument()
    // campos mapeados (construtor manual de regras lista os campos reais)
    expect(screen.getByText('valor atual: 3755')).toBeInTheDocument()
  })

  it('preserva a resposta ao navegar para o resultado e voltar, sem nenhuma nova chamada HTTP', async () => {
    const user = userEvent.setup()
    renderWorkbench()
    await screen.findByText(mockReq.name)

    await user.click(screen.getByRole('button', { name: /testar api/i }))
    await screen.findByText('HTTP 200')
    expect(api.probeRequest).toHaveBeenCalledTimes(1)

    // executa os testes -> navega para a tela de resultado (WorkbenchPage desmonta)
    await user.click(screen.getByRole('button', { name: /executar testes/i }))
    await screen.findByText('← Voltar para a API')
    expect(api.executeTests).toHaveBeenCalledTimes(1)

    // volta para a tela da API (WorkbenchPage remonta do zero)
    await user.click(screen.getByText('← Voltar para a API'))
    await screen.findByText(mockReq.name)

    // a resposta continua disponível imediatamente, sem precisar clicar em "Testar API" de novo
    expect(screen.getByText('HTTP 200')).toBeInTheDocument()
    expect(screen.getByText(/abc-123-xyz/)).toBeInTheDocument()
    expect(screen.getByText('valor atual: 3755')).toBeInTheDocument()

    // e nenhuma nova chamada HTTP foi feita só por causa da navegação
    expect(api.probeRequest).toHaveBeenCalledTimes(1)
  })
})
