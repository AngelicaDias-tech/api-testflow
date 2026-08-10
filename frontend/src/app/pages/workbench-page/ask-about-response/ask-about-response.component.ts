import { Component, Input, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ApiService } from '../../../core/services/api.service'
import { ApiError } from '../../../core/services/api-error'
import type { ProbeResult } from '../../../core/models'

/**
 * Consulta/análise em linguagem natural sobre a resposta real (ex: "qual o
 * valor do campo elevation?"). Deliberadamente distinto do assistente de
 * regras de negócio: aqui a IA só responde uma pergunta de leitura sobre o
 * JSON observado — nunca cria uma Rule, nunca influencia PASS/FAIL. Porta
 * 1:1 de components/AskAboutResponse.tsx.
 */
@Component({
  selector: 'app-ask-about-response',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="mt-3 border-t border-border pt-3">
      <p class="mb-2 text-sm font-medium text-foreground-muted">🤖 Pergunte sobre esta resposta</p>
      @if (history().length > 0) {
        <ul class="mb-3 space-y-2">
          @for (h of history(); track $index) {
            <li class="text-sm">
              <p class="font-medium text-foreground">Você: {{ h.q }}</p>
              <p class="text-foreground-muted">{{ h.a }}</p>
            </li>
          }
        </ul>
      }
      <form class="flex gap-2" (submit)="onSubmit($event)">
        <input
          class="input"
          placeholder="Ex: &quot;qual o valor do campo elevation?&quot;"
          [ngModel]="question()"
          (ngModelChange)="question.set($event)"
          name="question"
        />
        <button class="btn-secondary" [disabled]="!question().trim() || pending()" type="submit">
          {{ pending() ? '...' : 'Perguntar' }}
        </button>
      </form>
      @if (error()) {
        <p class="mt-1 text-xs text-danger">{{ error() }}</p>
      }
    </div>
  `,
})
export class AskAboutResponseComponent {
  private api = inject(ApiService)

  @Input({ required: true }) probe!: ProbeResult

  question = signal('')
  pending = signal(false)
  error = signal<string | null>(null)
  history = signal<{ q: string; a: string }[]>([])

  async onSubmit(e: Event) {
    e.preventDefault()
    const q = this.question().trim()
    if (!q) return
    this.pending.set(true)
    this.error.set(null)
    try {
      const result = await this.api.aiAnswerQuestion(q, this.probe)
      this.history.set([...this.history(), { q, a: result.answer }])
      this.question.set('')
    } catch (err) {
      this.error.set(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      this.pending.set(false)
    }
  }
}
