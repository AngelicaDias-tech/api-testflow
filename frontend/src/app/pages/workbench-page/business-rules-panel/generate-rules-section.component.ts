import { Component, EventEmitter, Input, Output, effect, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ApiService } from '../../../core/services/api.service'
import type { Check, ProbeResult } from '../../../core/models'

/**
 * Função 1 ("Gerar regras") — sintaxe técnica explícita, uma regra por
 * linha, determinístico (POST /ai/generate-rules). Porta 1:1 de
 * GenerateRulesSection dentro de components/BusinessRulesPanel.tsx.
 */
@Component({
  selector: 'app-generate-rules-section',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="pt-4 first:pt-0">
      <h3 class="text-base font-semibold text-foreground">1. Gerar regras</h3>
      <p class="mb-2 text-sm text-foreground-muted">
        Escreva a sintaxe técnica diretamente — <strong>use o nome real do campo</strong>, não linguagem natural.
        Uma regra por linha.
      </p>
      <textarea
        class="input mono h-24 text-sm"
        placeholder="stargazers_count > 100
private == false
name == Hello-World"
        [ngModel]="text()"
        (ngModelChange)="text.set($event)"
      ></textarea>
      <button class="btn-primary mt-3" [disabled]="!text().trim() || pending()" (click)="generate()">
        {{ pending() ? 'Gerando...' : '⚙️ Gerar regras' }}
      </button>

      @if (errors().length > 0) {
        <ul class="mt-3 space-y-1 text-xs text-danger">
          @for (err of errors(); track err) {
            <li>⚠️ {{ err }}</li>
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
          <p class="mt-2 text-xs text-foreground-muted">
            A IA nunca adiciona regras sozinha nem decide PASS/FAIL — pytest continua sendo a autoridade. Você
            precisa aprovar aqui.
          </p>
        </div>
      }
    </div>
  `,
})
export class GenerateRulesSectionComponent {
  private api = inject(ApiService)

  @Input() probe: ProbeResult | null = null
  @Input() isAdding = false
  @Output() addRules = new EventEmitter<Check[]>()

  text = signal('')
  pending = signal(false)
  rules = signal<Check[]>([])
  errors = signal<string[]>([])
  selected = signal<Set<string>>(new Set())

  constructor() {
    // Cada nova geração de regras propostas vem com o checkbox MARCADO por
    // padrão — o usuário ainda pode desmarcar antes de aprovar (nunca
    // aprova nada sozinho).
    effect(
      () => {
        this.selected.set(new Set(this.rules().map((r) => r.id)))
      },
      { allowSignalWrites: true },
    )
  }

  async generate() {
    this.pending.set(true)
    try {
      const result = await this.api.aiGenerateRules(this.text(), this.probe ?? undefined)
      this.rules.set(result.rules)
      this.errors.set(result.errors)
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
