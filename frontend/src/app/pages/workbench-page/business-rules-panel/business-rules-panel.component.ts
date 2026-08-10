import { Component, EventEmitter, Input, Output } from '@angular/core'
import { GenerateRulesSectionComponent } from './generate-rules-section.component'
import { SuggestScenariosSectionComponent } from './suggest-scenarios-section.component'
import type { Check, ProbeResult, Rule } from '../../../core/models'

/**
 * Assistente de IA — não é obrigatório para o fluxo principal (esse é o
 * construtor manual "🎯 Regras de Negócio", que funciona 100% sem IA — ver
 * ManualBusinessRulesComponent, que este componente NUNCA altera nem
 * depende).
 *
 * Escopo deliberadamente limitado a 2 funções — a IA nunca decide PASS/FAIL,
 * nunca executa testes, nunca substitui o pytest, e nunca cria uma regra
 * sozinha sem revisão explícita do usuário. Porta 1:1 de
 * components/BusinessRulesPanel.tsx (versão final, só 2 funções).
 */
@Component({
  selector: 'app-business-rules-panel',
  standalone: true,
  imports: [GenerateRulesSectionComponent, SuggestScenariosSectionComponent],
  template: `
    <section class="card border-ai/30 p-6">
      <h2 class="text-xl font-bold text-foreground">🤖 Assistente de IA</h2>
      <p class="mb-4 text-sm text-foreground-muted">
        2 funções isoladas do fluxo manual — a IA nunca decide PASS/FAIL, nunca executa testes e nunca cria uma
        regra sem você aprovar explicitamente.
      </p>
      <div class="space-y-6 divide-y divide-border">
        <app-generate-rules-section [probe]="probe" [isAdding]="isAdding" (addRules)="addRules.emit($event)" />
        <app-suggest-scenarios-section [rules]="rules ?? []" />
      </div>
    </section>
  `,
})
export class BusinessRulesPanelComponent {
  @Input() probe: ProbeResult | null = null
  @Input() rules: Rule[] | undefined
  @Input() isAdding = false
  @Output() addRules = new EventEmitter<Check[]>()
}
