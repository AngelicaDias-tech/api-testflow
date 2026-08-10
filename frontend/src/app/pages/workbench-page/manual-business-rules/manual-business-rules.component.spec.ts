import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ManualBusinessRulesComponent } from './manual-business-rules.component'
import type { ProbeResult } from '../../../core/models'

const probe: ProbeResult = {
  status_code: 200,
  headers: {},
  content_type: 'application/json',
  body_raw: '{}',
  body_json: { name: 'Hello-World', private: false, stargazers_count: 3755, owner: { login: 'octocat' } },
  json_valid: true,
  response_time_ms: 10,
  error: null,
  discovered_checks: [],
}

describe('ManualBusinessRulesComponent — fluxo manual (não depende de IA)', () => {
  let fixture: ComponentFixture<ManualBusinessRulesComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ManualBusinessRulesComponent] })
    fixture = TestBed.createComponent(ManualBusinessRulesComponent)
    fixture.componentInstance.probe = probe
    fixture.detectChanges()
  })

  it('descobre os campos reais achatados do JSON (lupa/busca opera sobre a lista real)', () => {
    const fields = fixture.componentInstance.fields()
    expect(fields).toEqual(expect.arrayContaining(['name', 'private', 'stargazers_count', 'owner', 'owner.login']))
  })

  it('a busca filtra visualmente sem apagar a seleção (rascunho) já feita', () => {
    const c = fixture.componentInstance
    c.onToggle('stargazers_count', { target: { checked: true } } as unknown as Event)
    c.search.set('owner')

    expect(c.visibleFields()).not.toContain('stargazers_count')
    expect(c.isChecked('stargazers_count')).toBe(true)
  })

  it('operadores oferecidos respeitam o tipo real do campo (booleano != numérico)', () => {
    const c = fixture.componentInstance
    expect(c.operatorsFor('private')).toEqual(['equals', 'not_equals', 'exists', 'not_exists'])
    expect(c.operatorsFor('stargazers_count')).toContain('greater_than')
  })

  it('gera o payload da regra igual ao fluxo original: expected=null para operadores sem valor, description formatada', () => {
    const c = fixture.componentInstance
    const emitted: unknown[] = []
    c.addRules.subscribe((rules) => emitted.push(rules))

    c.onToggle('stargazers_count', { target: { checked: true } } as unknown as Event)
    c.updateOperator('stargazers_count', 'greater_than')
    c.updateExpected('stargazers_count', '100')
    c.handleAdd()

    expect(emitted).toEqual([
      [
        {
          source: 'custom',
          category: 'field',
          field: 'stargazers_count',
          operator: 'greater_than',
          expected: '100',
          description: 'stargazers_count greater_than 100',
          enabled: true,
        },
      ],
    ])
    // limpa os rascunhos depois de aprovar, igual ao React
    expect(c.readyCount()).toBe(0)
  })

  it('não inclui no payload uma regra ainda sem valor esperado (operador que precisa de valor)', () => {
    const c = fixture.componentInstance
    c.onToggle('name', { target: { checked: true } } as unknown as Event)
    expect(c.readyCount()).toBe(0)
  })
})
