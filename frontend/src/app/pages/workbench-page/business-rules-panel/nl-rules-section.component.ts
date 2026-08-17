import { Component, EventEmitter, Input, Output, effect, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ApiService } from '../../../core/services/api.service'
import type { Check, ProbeResult } from '../../../core/models'

/**
 * Função "Analisar requisito" — linguagem natural DE VERDADE (ex: "Clientes
 * PREMIUM devem estar ativos e ter limite maior que 1000"), ao contrário de
 * GenerateRulesSectionComponent (sintaxe técnica explícita, determinística).
 * Usa POST /ai/nl-to-rules, que aciona o provider de IA configurado
 * (heurístico por padrão, ou um LLM real via OpenAI — ver
 * app/ai/openai_provider.py) para interpretar a frase contra a resposta
 * REAL já testada. Como toda sugestão de IA, precisa de aprovação explícita
 * antes de virar uma regra de verdade.
 */
@Component({
  selector: 'app-nl-rules-section',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="pt-4">
      <h3 class="text-base font-semibold text-foreground">Analisar requisito (linguagem natural)</h3>
      <p class="mb-2 text-sm text-foreground-muted">
        Descreva em português o que a resposta deveria garantir — a IA tenta identificar os campos reais.
      </p>
      <textarea
        class="input h-20 text-sm"
        placeholder="Ex: Quero garantir que o status seja ACTIVE e que o id seja um número."
        [ngModel]="text()"
        (ngModelChange)="text.set($event)"
      ></textarea>
      <button class="btn-primary mt-3" [disabled]="!text().trim() || pending()" (click)="analyze()">
        {{ pending() ? 'Analisando...' : '🧠 Analisar requisito' }}
      </button>

      @if (unparsed().length > 0) {
        <ul class="mt-3 space-y-1 text-xs text-warning">
          @for (u of unparsed(); track u) {
            <li>⚠️ {{ u }}</li>
          }
        </ul>
      }

      @if (rules().length > 0) {
        <div class="mt-3 rounded-lg border border-ai/30 bg-ai/10 p-4">
          <p class="mb-2 text-sm font-medium text-ai">Regras propostas — revise antes de aprovar:</p>
          <ul class="mb-3 space-y-2">
            @for (r of rules(); track r.id; let i = $index) {
              <li class="flex items-start gap-2 text-sm text-foreground">
                <input
                  class="mt-0.5"
                  type="checkbox"
                  [checked]="selected().has(r.id)"
                  (change)="toggleSelected(r.id, $event)"
                />
                <span>
                  <span class="text-foreground-muted">{{ i + 1 }}.</span> {{ r.description }}
                  @if (r.array_path) {
                    <span class="badge-ai ml-2">condicional sobre lista</span>
                  }
                </span>
              </li>
            }
          </ul>
          <button class="btn-primary" [disabled]="selected().size === 0 || isAdding" (click)="approve()">
            Aprovar {{ selected().size > 0 ? '(' + selected().size + ')' : 'todas' }}
          </button>
        </div>
      }
    </div>
  `,
})
export class NlRulesSectionComponent {
  private api = inject(ApiService)

  @Input() probe: ProbeResult | null = null
  @Input() isAdding = false
  @Output() addRules = new EventEmitter<Check[]>()

  text = signal('')
  pending = signal(false)
  rules = signal<Check[]>([])
  unparsed = signal<string[]>([])
  selected = signal<Set<string>>(new Set())

  constructor() {
    effect(
      () => {
        this.selected.set(new Set(this.rules().map((r) => r.id)))
      },
      { allowSignalWrites: true },
    )
  }

  async analyze() {
    this.pending.set(true)
    try {
      const result = await this.api.aiNlToRules(this.text(), this.probe ?? undefined)
      this.rules.set(result.rules)
      this.unparsed.set(result.unparsed ?? [])
      if (result.rules.length > 0) this.text.set('')
    } finally {
      this.pending.set(false)
    }
  }

  toggleSelected(id: string, e: Event) {
    const next = new Set(this.selected())
    if ((e.target as HTMLInputElement).checked) next.add(id)
    else next.delete(id)
    this.selected.set(next)
  }

  approve() {
    this.addRules.emit(this.rules().filter((r) => this.selected().has(r.id)))
  }
}
