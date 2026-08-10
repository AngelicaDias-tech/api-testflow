import { Component, Input, inject, signal } from '@angular/core'
import { ApiService } from '../../../core/services/api.service'
import type { NegativeCase } from '../../../core/models'

@Component({
  selector: 'app-negative-cases-panel',
  standalone: true,
  template: `
    <div>
      <button class="btn-secondary" [disabled]="pending()" (click)="suggest()">
        {{ pending() ? 'Analisando...' : '🤖 Sugerir cenários negativos' }}
      </button>
      @if (loaded() && cases().length === 0) {
        <p class="mt-2 text-sm text-foreground-muted">Nenhum cenário negativo óbvio identificado para esta URL.</p>
      }
      @if (cases().length > 0) {
        <ul class="mt-3 space-y-2">
          @for (c of cases(); track c.id) {
            <li class="rounded-lg border border-border p-3 text-sm">
              <div class="mb-1 flex items-center gap-2">
                <span class="font-medium text-foreground">{{ c.title }}</span>
                @if (c.requires_confirmation) {
                  <span class="badge bg-warning/15 text-warning">requer confirmação — altera dados</span>
                } @else {
                  <span class="badge bg-success/15 text-success">seguro (somente leitura)</span>
                }
              </div>
              <p class="text-foreground-muted">{{ c.description }}</p>
            </li>
          }
        </ul>
      }
      <p class="mt-2 text-xs text-foreground-muted">
        Estas são sugestões de cenários — crie uma nova requisição de teste (com o ID/token indicado) para
        executá-las. Operações que alteram dados (POST/PUT/PATCH/DELETE) nunca disparam automaticamente.
      </p>
    </div>
  `,
})
export class NegativeCasesPanelComponent {
  private api = inject(ApiService)

  @Input({ required: true }) requestId!: string

  pending = signal(false)
  loaded = signal(false)
  cases = signal<NegativeCase[]>([])

  async suggest() {
    this.pending.set(true)
    try {
      const result = await this.api.aiSuggestNegativeCases(this.requestId)
      this.cases.set(result)
      this.loaded.set(true)
    } finally {
      this.pending.set(false)
    }
  }
}
