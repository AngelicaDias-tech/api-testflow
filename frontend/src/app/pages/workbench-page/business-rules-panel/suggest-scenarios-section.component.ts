import { Component, Input, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ApiService } from '../../../core/services/api.service'
import type { Rule, Scenario } from '../../../core/models'

/**
 * Função 2 ("Sugerir cenários") — a partir de uma regra JÁ aprovada, sugere
 * 2-3 valores de exemplo com o resultado esperado (PASS/FAIL). Só
 * informativo: a IA nunca executa nada, pytest é quem decide de verdade.
 * Porta 1:1 de SuggestScenariosSection dentro de
 * components/BusinessRulesPanel.tsx.
 */
@Component({
  selector: 'app-suggest-scenarios-section',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="pt-4">
      <h3 class="text-base font-semibold text-foreground">Sugerir cenários</h3>
      <p class="mb-2 text-sm text-foreground-muted">
        Escolha uma regra já aprovada — a IA sugere valores de exemplo com o resultado esperado (PASS/FAIL).
      </p>

      @if (candidateRules().length === 0) {
        <p class="text-sm text-foreground-muted">Aprove pelo menos uma regra de campo primeiro.</p>
      } @else {
        <div class="flex flex-wrap items-end gap-2">
          <select class="input" [ngModel]="selectedRuleId()" (ngModelChange)="selectedRuleId.set($event)">
            <option value="">Selecione uma regra...</option>
            @for (r of candidateRules(); track r.id) {
              <option [value]="r.id">{{ r.description }}</option>
            }
          </select>
          <button class="btn-primary" [disabled]="!selectedRuleId() || pending()" (click)="suggest()">
            {{ pending() ? 'Sugerindo...' : '🎲 Sugerir cenários' }}
          </button>
        </div>
      }

      @if (scenarios().length > 0) {
        <ul class="mt-3 space-y-1 rounded-lg border border-ai/30 bg-ai/10 p-3 text-sm text-foreground">
          @for (s of scenarios(); track $index) {
            <li>
              <span class="{{ s.expected_outcome === 'PASS' ? 'text-success' : 'text-danger' }}">{{
                s.expected_outcome
              }}</span>
              — {{ s.description }}
            </li>
          }
        </ul>
      }
    </div>
  `,
})
export class SuggestScenariosSectionComponent {
  private api = inject(ApiService)

  @Input() rules: Rule[] = []

  selectedRuleId = signal('')
  pending = signal(false)
  scenarios = signal<Scenario[]>([])

  candidateRules(): Rule[] {
    return (this.rules ?? []).filter((r) => r.field && r.operator)
  }

  async suggest() {
    const rule = this.candidateRules().find((r) => r.id === this.selectedRuleId())
    if (!rule) return
    this.pending.set(true)
    try {
      const result = await this.api.aiSuggestScenarios({
        field: rule.field ?? undefined,
        operator: rule.operator,
        expected: rule.expected,
      })
      this.scenarios.set(result.scenarios)
    } finally {
      this.pending.set(false)
    }
  }
}
