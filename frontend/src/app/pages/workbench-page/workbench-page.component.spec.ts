import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router'
import { WorkbenchPageComponent } from './workbench-page.component'
import { ApiService } from '../../core/services/api.service'
import { ProbeStoreService } from '../../core/services/probe-store.service'
import type { ProbeResult, RequestDef, Rule } from '../../core/models'

/**
 * Regressão do bug "voltar da tela de resultado apaga o JSON da API e
 * força o usuário a clicar em Testar API de novo" — porta 1:1 das
 * garantias já testadas no React (WorkbenchPage.test.tsx):
 * 1. a API é chamada só quando o usuário clica em "Testar API";
 * 2. a resposta é armazenada (ProbeStoreService, ver core/services);
 * 3. destruir e recriar o componente (equivalente a navegar para o
 *    resultado e voltar, já que são rotas/componentes diferentes) não
 *    apaga a resposta;
 * 4. nenhuma nova chamada HTTP é feita só por causa disso.
 */

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

function buildFixture(apiMock: Partial<ApiService>): ComponentFixture<WorkbenchPageComponent> {
  TestBed.configureTestingModule({
    imports: [WorkbenchPageComponent],
    providers: [
      { provide: ApiService, useValue: apiMock },
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { paramMap: convertToParamMap({ projectId: 'proj-1', requestId: 'req-1' }) } },
      },
      provideRouter([]),
    ],
  })
  const fixture = TestBed.createComponent(WorkbenchPageComponent)
  fixture.detectChanges()
  return fixture
}

describe('WorkbenchPageComponent — persistência da resposta da API entre telas', () => {
  let apiMock: {
    getRequest: jest.Mock
    listRules: jest.Mock
    probeRequest: jest.Mock
    executeTests: jest.Mock
    listScenarios: jest.Mock
    listDatasets: jest.Mock
  }

  beforeEach(() => {
    apiMock = {
      getRequest: jest.fn().mockResolvedValue(mockReq),
      listRules: jest.fn().mockResolvedValue([approvedRule]),
      probeRequest: jest.fn().mockResolvedValue(mockProbe),
      executeTests: jest.fn(),
      listScenarios: jest.fn().mockResolvedValue([]),
      listDatasets: jest.fn().mockResolvedValue([]),
    }
  })

  it('não chama a API sozinho ao carregar a tela', async () => {
    const fixture = buildFixture(apiMock)
    await fixture.whenStable()
    expect(apiMock.probeRequest).not.toHaveBeenCalled()
    expect(fixture.componentInstance.probe()).toBeNull()
  })

  it('chama a API e guarda a resposta ao clicar em "Testar API"', async () => {
    const fixture = buildFixture(apiMock)
    await fixture.whenStable()

    await fixture.componentInstance.testarApi(false)
    fixture.detectChanges()

    expect(apiMock.probeRequest).toHaveBeenCalledTimes(1)
    expect(fixture.componentInstance.probe()).toEqual(mockProbe)
  })

  it('preserva a resposta ao destruir e recriar o componente (equivalente a navegar para o resultado e voltar), sem nenhuma nova chamada HTTP', async () => {
    const fixture = buildFixture(apiMock)
    await fixture.whenStable()
    await fixture.componentInstance.testarApi(false)
    expect(apiMock.probeRequest).toHaveBeenCalledTimes(1)

    // Simula sair da tela (navegar para o resultado) e voltar: o
    // ProbeStoreService é providedIn:'root', então a MESMA instância do
    // TestBed.inject sobrevive; um novo componente é criado do zero, como
    // aconteceria de verdade ao trocar de rota.
    fixture.destroy()
    const secondFixture = TestBed.createComponent(WorkbenchPageComponent)
    secondFixture.detectChanges()
    await secondFixture.whenStable()

    expect(secondFixture.componentInstance.probe()).toEqual(mockProbe)
    expect(apiMock.probeRequest).toHaveBeenCalledTimes(1)
  })

  it('injeta sempre a mesma instância de ProbeStoreService (base da persistência)', () => {
    buildFixture(apiMock)
    const a = TestBed.inject(ProbeStoreService)
    const b = TestBed.inject(ProbeStoreService)
    expect(a).toBe(b)
  })
})
