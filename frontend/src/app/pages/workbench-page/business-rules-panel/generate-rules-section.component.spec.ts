import { ComponentFixture, TestBed } from '@angular/core/testing'
import { GenerateRulesSectionComponent } from './generate-rules-section.component'
import { ApiService } from '../../../core/services/api.service'
import type { Check } from '../../../core/models'

const rule = (id: string): Check => ({
  id,
  source: 'custom',
  category: 'field',
  field: 'stargazers_count',
  operator: 'greater_than',
  expected: 100,
  description: 'stargazers_count greater_than 100',
})

describe('GenerateRulesSectionComponent — Função 1 do Assistente de IA (Gerar regras)', () => {
  let fixture: ComponentFixture<GenerateRulesSectionComponent>
  let apiMock: { aiGenerateRules: jest.Mock }

  beforeEach(() => {
    apiMock = { aiGenerateRules: jest.fn() }
    TestBed.configureTestingModule({
      imports: [GenerateRulesSectionComponent],
      providers: [{ provide: ApiService, useValue: apiMock }],
    })
    fixture = TestBed.createComponent(GenerateRulesSectionComponent)
    fixture.detectChanges()
  })

  it('regras propostas vêm com o checkbox MARCADO por padrão — sem aprovar nada sozinho', async () => {
    apiMock.aiGenerateRules.mockResolvedValue({ rules: [rule('r1'), rule('r2')], errors: [] })
    const c = fixture.componentInstance
    c.text.set('stargazers_count > 100')

    await c.generate()
    fixture.detectChanges()

    expect(c.selected().has('r1')).toBe(true)
    expect(c.selected().has('r2')).toBe(true)
    // nada foi aprovado sozinho: addRules só emite quando approve() é chamado
    const emitted: unknown[] = []
    c.addRules.subscribe((r) => emitted.push(r))
    expect(emitted).toEqual([])
  })

  it('o usuário ainda pode desmarcar uma regra antes de aprovar', async () => {
    apiMock.aiGenerateRules.mockResolvedValue({ rules: [rule('r1'), rule('r2')], errors: [] })
    const c = fixture.componentInstance
    await c.generate()

    c.toggleSelected('r1', { target: { checked: false } } as unknown as Event)

    expect(c.selected().has('r1')).toBe(false)
    expect(c.selected().has('r2')).toBe(true)
  })

  it('aprovar só envia as regras que continuam marcadas', async () => {
    apiMock.aiGenerateRules.mockResolvedValue({ rules: [rule('r1'), rule('r2')], errors: [] })
    const c = fixture.componentInstance
    await c.generate()
    c.toggleSelected('r1', { target: { checked: false } } as unknown as Event)

    const emitted: Check[][] = []
    c.addRules.subscribe((r) => emitted.push(r))
    c.approve()

    expect(emitted).toEqual([[rule('r2')]])
  })
})
