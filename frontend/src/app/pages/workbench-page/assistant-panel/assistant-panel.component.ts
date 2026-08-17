import { Component, EventEmitter, Input, Output, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ApiService } from '../../../core/services/api.service'
import { ApiError } from '../../../core/services/api-error'
import { GenerateRulesSectionComponent } from '../business-rules-panel/generate-rules-section.component'
import { NlRulesSectionComponent } from '../business-rules-panel/nl-rules-section.component'
import { SuggestScenariosSectionComponent } from '../business-rules-panel/suggest-scenarios-section.component'
import { NegativeCasesPanelComponent } from '../negative-cases-panel/negative-cases-panel.component'
import type { Check, ProbeResult, RequestDef, Rule } from '../../../core/models'

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
}

const QUICK_ACTIONS = [
  { label: '💬 Explique essa API', message: 'Explique essa API.' },
  { label: '🔎 Quais campos validar?', message: 'Quais campos dessa response deveriam ser validados?' },
  { label: '⚠️ Explique o erro', message: 'Explique esse erro.', requiresError: true },
]

type Tab = 'conversar' | 'regras' | 'cenarios' | 'massa'

const TABS: { id: Tab; label: string }[] = [
  { id: 'conversar', label: '💬 Conversar' },
  { id: 'regras', label: '📋 Regras' },
  { id: 'cenarios', label: '🧪 Cenários' },
  { id: 'massa', label: '📊 Massa' },
]

/**
 * Bloco ÚNICO do Assistente de IA (limpeza/consolidação — antes havia dois
 * blocos separados: "Assistente de IA" para chat e "Assistente de IA —
 * regras e cenários" para as demais funções, além de sugestões de IA
 * espalhadas em outros cantos da tela). Organiza as 4 funções de IA da
 * plataforma em abas:
 *
 *  - Conversar: chat contextual de propósito geral (POST /ai/chat);
 *  - Regras: gerar regras por sintaxe técnica + analisar requisito em
 *    linguagem natural (GenerateRulesSectionComponent/NlRulesSectionComponent);
 *  - Cenários: sugerir cenários de valor para uma regra já aprovada +
 *    sugerir cenários negativos (SuggestScenariosSectionComponent/
 *    NegativeCasesPanelComponent);
 *  - Massa: gerar candidatos de massa de teste com IA para revisão (a
 *    aprovação final e a execução continuam na seção "Massas de Teste",
 *    que também cobre a importação de CSV — motor de testes não muda).
 *
 * Em toda aba, a IA só sugere: quem aprova é o usuário, e quem decide
 * PASS/FAIL é sempre o pytest (nunca esta tela).
 */
@Component({
  selector: 'app-assistant-panel',
  standalone: true,
  imports: [
    FormsModule,
    GenerateRulesSectionComponent,
    NlRulesSectionComponent,
    SuggestScenariosSectionComponent,
    NegativeCasesPanelComponent,
  ],
  template: `
    <section class="card border-ai/30 p-6">
      <h2 class="text-xl font-bold text-foreground">🤖 Assistente de IA</h2>
      <p class="mb-4 text-sm text-foreground-muted">
        A IA analisa e sugere. Você aprova. O pytest executa e determina PASS/FAIL.
      </p>

      <div class="mb-4 flex flex-wrap gap-2 border-b border-border pb-3">
        @for (tab of tabs; track tab.id) {
          <button
            class="rounded-lg px-3 py-1.5 text-sm font-medium {{
              activeTab() === tab.id ? 'bg-ai/15 text-ai' : 'text-foreground-muted hover:text-foreground'
            }}"
            (click)="activeTab.set(tab.id)"
          >
            {{ tab.label }}
          </button>
        }
      </div>

      @switch (activeTab()) {
        @case ('conversar') {
          <div>
            <div class="mb-3 flex flex-wrap gap-2">
              @for (action of quickActions(); track action.label) {
                <button class="btn-secondary px-3 py-1 text-xs" [disabled]="pending()" (click)="send(action.message)">
                  {{ action.label }}
                </button>
              }
            </div>

            @if (messages().length > 0) {
              <div class="mb-3 max-h-80 space-y-3 overflow-auto rounded-lg border border-border bg-canvas p-3">
                @for (m of messages(); track $index) {
                  <div class="{{ m.role === 'user' ? 'text-right' : 'text-left' }}">
                    <span
                      class="inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm {{
                        m.role === 'user' ? 'bg-accent/15 text-foreground' : 'bg-ai/10 text-foreground'
                      }}"
                    >
                      {{ m.text }}
                    </span>
                  </div>
                }
              </div>
            }
            @if (pending()) {
              <p class="mb-3 text-sm text-foreground-muted">Pensando...</p>
            }
            @if (error()) {
              <p class="mb-3 text-sm text-danger">{{ error() }}</p>
            }

            <div class="flex gap-2">
              <input
                class="input flex-1"
                placeholder="Ex: o que foi enviado no request? por que esse teste falhou?"
                [ngModel]="text()"
                (ngModelChange)="text.set($event)"
                (keydown.enter)="onEnter()"
              />
              <button class="btn-primary" [disabled]="!text().trim() || pending()" (click)="send(text())">
                Enviar
              </button>
            </div>
          </div>
        }
        @case ('regras') {
          <div class="space-y-6 divide-y divide-border">
            <app-generate-rules-section [probe]="probe" [isAdding]="isAdding" (addRules)="addRules.emit($event)" />
            <app-nl-rules-section [probe]="probe" [isAdding]="isAdding" (addRules)="addRules.emit($event)" />
          </div>
        }
        @case ('cenarios') {
          <div class="space-y-6 divide-y divide-border">
            <app-suggest-scenarios-section [rules]="rules" />
            <div class="pt-4">
              <h3 class="mb-2 text-base font-semibold text-foreground">Cenários negativos sugeridos</h3>
              @if (requestId) {
                <app-negative-cases-panel [requestId]="requestId" />
              }
            </div>
          </div>
        }
        @case ('massa') {
          <div>
            <p class="mb-3 text-sm text-foreground-muted">
              A IA gera candidatos de massa a partir das variáveis <code class="mono">{{ '{{var}}' }}</code> já
              usadas por esta API e pelas regras aprovadas. Revise abaixo e aprove para salvar — a execução
              acontece na seção "Massas de Teste".
            </p>
            <div class="mb-3 flex items-center gap-2">
              <input class="input w-24" type="number" min="1" max="200" [ngModel]="count()" (ngModelChange)="count.set($event)" />
              <button class="btn-secondary" [disabled]="!requestId || massaPending()" (click)="generateMassa()">
                {{ massaPending() ? 'Gerando...' : '🎲 Gerar massa com IA' }}
              </button>
            </div>
            @if (massaError()) {
              <p class="mb-3 text-sm text-danger">{{ massaError() }}</p>
            }
            @if (massaPreview(); as p) {
              <div>
                <p class="mb-2 text-sm text-foreground-muted">
                  Prévia — {{ p.rows.length }} caso(s) · <span class="mono">{{ p.columns.join(', ') }}</span>
                </p>
                <div class="mb-3 overflow-auto rounded-lg border border-border">
                  <table class="mono w-full text-xs">
                    <thead class="bg-card-hover">
                      <tr>
                        @for (col of p.columns; track col) {
                          <th class="px-2 py-1 text-left">{{ col }}</th>
                        }
                      </tr>
                    </thead>
                    <tbody>
                      @for (row of p.rows; track $index) {
                        <tr class="border-t border-border">
                          @for (col of p.columns; track col) {
                            <td class="px-2 py-1">{{ row[col] }}</td>
                          }
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
                <div class="flex items-end gap-2">
                  <div class="flex-1">
                    <label class="label">Nome da massa</label>
                    <input
                      class="input"
                      placeholder="Ex: casos gerados por IA"
                      [ngModel]="massaName()"
                      (ngModelChange)="massaName.set($event)"
                    />
                  </div>
                  <button class="btn-primary" [disabled]="!massaName().trim() || massaSaving()" (click)="approveMassa()">
                    {{ massaSaving() ? 'Salvando...' : '✓ Aprovar e salvar massa' }}
                  </button>
                </div>
              </div>
            }
          </div>
        }
      }
    </section>
  `,
})
export class AssistantPanelComponent {
  private api = inject(ApiService)

  @Input() req: RequestDef | null = null
  @Input() probe: ProbeResult | null = null
  @Input() rules: Rule[] = []
  @Input() requestId: string | null = null
  @Input() isAdding = false
  @Output() addRules = new EventEmitter<Check[]>()
  @Output() datasetCreated = new EventEmitter<void>()

  readonly tabs = TABS
  activeTab = signal<Tab>('conversar')

  // --- Conversar ------------------------------------------------------------
  messages = signal<ChatMessage[]>([])
  text = signal('')
  pending = signal(false)
  error = signal<string | null>(null)

  quickActions() {
    const hasError = !!this.probe?.error || (this.probe?.status_code ?? 0) >= 400
    return QUICK_ACTIONS.filter((a) => !a.requiresError || hasError)
  }

  onEnter() {
    if (this.text().trim()) this.send(this.text())
  }

  private buildContext(): Record<string, unknown> {
    const ctx: Record<string, unknown> = {}
    if (this.req) {
      ctx['method'] = this.req.method
      ctx['url'] = this.req.url
    }
    if (this.probe) {
      ctx['status_code'] = this.probe.status_code
      ctx['response_time_ms'] = this.probe.response_time_ms
      ctx['json_valid'] = this.probe.json_valid
      if (this.probe.json_valid) ctx['body_json'] = this.probe.body_json
      if (this.probe.error) ctx['error'] = this.probe.error
      ctx['headers'] = this.probe.headers
      // Request efetivamente enviado (já mascarado, ver build_sent_snapshot)
      // — permite o assistente responder sobre o que foi enviado, não só o
      // que voltou na resposta.
      const sent = this.probe.sent_request
      if (sent) {
        ctx['request_body'] = sent.body
        ctx['request_headers'] = sent.headers
        ctx['auth_type'] = sent.auth_type
      }
    }
    const enabledRules = this.rules.filter((r) => r.enabled)
    if (enabledRules.length > 0) {
      ctx['rules'] = enabledRules.map((r) => ({ field: r.field, operator: r.operator, expected: r.expected }))
    }
    return ctx
  }

  async send(message: string) {
    const trimmed = message.trim()
    if (!trimmed) return
    this.error.set(null)
    this.messages.set([...this.messages(), { role: 'user', text: trimmed }])
    this.text.set('')
    this.pending.set(true)
    try {
      const result = await this.api.aiChat(trimmed, this.buildContext())
      this.messages.set([...this.messages(), { role: 'assistant', text: result.answer }])
    } catch (err) {
      this.error.set(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      this.pending.set(false)
    }
  }

  // --- Massa ------------------------------------------------------------------
  count = signal(10)
  massaPending = signal(false)
  massaError = signal<string | null>(null)
  massaPreview = signal<{ columns: string[]; rows: Record<string, unknown>[] } | null>(null)
  massaName = signal('')
  massaSaving = signal(false)

  async generateMassa() {
    if (!this.requestId) return
    this.massaPending.set(true)
    this.massaError.set(null)
    try {
      const result = await this.api.aiSuggestTestData(this.requestId, this.count())
      this.massaPreview.set(result)
      if (!this.massaName().trim()) this.massaName.set('Massa gerada por IA')
    } catch (err) {
      this.massaError.set(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      this.massaPending.set(false)
    }
  }

  async approveMassa() {
    const p = this.massaPreview()
    if (!p || !this.requestId) return
    this.massaSaving.set(true)
    try {
      await this.api.createDataset(this.requestId, this.massaName(), p.columns, p.rows)
      this.massaPreview.set(null)
      this.massaName.set('')
      this.datasetCreated.emit()
    } catch (err) {
      this.massaError.set(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      this.massaSaving.set(false)
    }
  }
}
