import { Component, inject, signal } from '@angular/core'
import { ActivatedRoute, RouterLink } from '@angular/router'
import { ApiService } from '../../core/services/api.service'
import { SourceBadgeComponent } from '../../shared/source-badge/source-badge.component'
import { RequestViewerComponent } from '../../shared/request-viewer/request-viewer.component'
import type { Execution, TestResult } from '../../core/models'

const OUTCOME_ICON: Record<string, string> = { passed: '🟢', failed: '🔴', skipped: '⚪', error: '🔴' }

@Component({
  selector: 'app-execution-page',
  standalone: true,
  imports: [RouterLink, SourceBadgeComponent, RequestViewerComponent],
  template: `
    @if (isLoading() || !execution()) {
      <p class="text-foreground-muted">Carregando...</p>
    } @else {
      <div class="space-y-6">
        <div>
          <a [routerLink]="['/projects', projectId, 'requests', requestId]" class="text-sm text-foreground-muted hover:text-foreground">
            ← Voltar para a API
          </a>
          <h1 class="mt-1 text-2xl font-bold text-foreground">Resultado da execução</h1>
          @if (execution()!.variables_used) {
            <p class="mt-1 text-xs text-foreground-muted">
              🧩 Executado com variáveis: <code class="mono">{{ variablesPreview() }}</code>
            </p>
          }
        </div>

        @if (execution()!.sent_request) {
          <details>
            <summary class="cursor-pointer text-sm font-medium text-foreground-muted">📤 Ver request enviado nesta execução</summary>
            <div class="mt-2">
              <app-request-viewer [sent]="execution()!.sent_request!" />
            </div>
          </details>
        }

        <div class="card grid grid-cols-2 gap-4 p-6 sm:grid-cols-5">
          <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">TOTAL TESTS</p>
            <p class="text-2xl font-bold text-foreground">{{ execution()!.total }}</p>
          </div>
          <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">🟢 PASSED</p>
            <p class="text-2xl font-bold text-success">{{ execution()!.passed }}</p>
          </div>
          <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">🔴 FAILED</p>
            <p class="text-2xl font-bold text-danger">{{ execution()!.failed }}</p>
          </div>
          <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">⚪ SKIPPED</p>
            <p class="text-2xl font-bold text-foreground-muted">{{ execution()!.skipped }}</p>
          </div>
          <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-foreground-muted">DURATION</p>
            <p class="text-2xl font-bold text-foreground">{{ ((execution()!.duration_ms ?? 0) / 1000).toFixed(2) }}s</p>
          </div>
        </div>

        <div class="grid gap-6 lg:grid-cols-2">
          <section class="card p-5">
            <h2 class="mb-3 text-lg font-semibold text-foreground">Testes</h2>
            <ul class="space-y-1">
              @for (r of execution()!.results; track r.id) {
                <li>
                  <button
                    class="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition-colors hover:bg-card-hover {{ selected()?.id === r.id ? 'field-selected' : 'border-transparent' }}"
                    (click)="select(r)"
                  >
                    <span class="flex items-center gap-2 truncate">
                      <span>{{ icon(r.outcome) }}</span>
                      <span class="truncate text-foreground">{{ r.name }}</span>
                    </span>
                    <app-source-badge [source]="r.source" />
                  </button>
                </li>
              }
            </ul>
          </section>

          <section class="card p-5">
            @if (!selected()) {
              <p class="text-sm text-foreground-muted">Clique em um teste à esquerda para ver os detalhes.</p>
            } @else {
              <div>
                <h2 class="mb-1 text-lg font-semibold text-foreground">{{ icon(selected()!.outcome) }} {{ selected()!.name }}</h2>
                <p class="mb-4 text-xs font-semibold uppercase tracking-wide text-foreground-muted">
                  {{ selected()!.outcome === 'passed' ? 'PASSED' : selected()!.outcome.toUpperCase() }}
                </p>

                @if (selected()!.field) {
                  <p class="mono mb-3 text-sm text-foreground-muted">Campo: {{ selected()!.field }}</p>
                }

                <div class="mb-4 grid grid-cols-2 gap-3">
                  <div class="rounded-lg border border-border bg-card-hover p-3">
                    <p class="label mb-1">Expected</p>
                    <p class="mono text-sm text-foreground">{{ selected()!.expected ?? '—' }}</p>
                  </div>
                  <div class="rounded-lg border p-3 {{ selected()!.outcome === 'passed' ? 'border-success/30 bg-success/10' : 'border-danger/30 bg-danger/10' }}">
                    <p class="label mb-1">Actual</p>
                    <p class="mono text-sm text-foreground">
                      {{ selected()!.actual ?? '—' }} {{ selected()!.outcome !== 'passed' ? '❌' : '' }}{{
                        selected()!.outcome === 'passed' ? '✅' : ''
                      }}
                    </p>
                  </div>
                </div>

                @if (selected()!.message) {
                  <details class="mb-4">
                    <summary class="cursor-pointer text-sm font-medium text-foreground-muted">Mensagem do pytest</summary>
                    <pre class="mono mt-2 max-h-40 overflow-auto rounded-lg border border-border bg-canvas p-3 text-xs text-foreground">{{
                      selected()!.message
                    }}</pre>
                  </details>
                }

                @if (selected()!.outcome === 'failed') {
                  <div class="rounded-lg border border-ai/30 bg-ai/10 p-4">
                    <p class="mb-2 text-sm font-semibold text-ai">🤖 AI ANALYSIS</p>
                    @if (!explanation()) {
                      <button class="btn-secondary" [disabled]="explainPending()" (click)="explainFailure()">
                        {{ explainPending() ? 'Analisando...' : 'Explicar esta falha' }}
                      </button>
                    } @else {
                      <pre class="whitespace-pre-wrap text-sm text-foreground">{{ explanation() }}</pre>
                    }
                  </div>
                }
              </div>
            }
          </section>
        </div>
      </div>
    }
  `,
})
export class ExecutionPageComponent {
  private api = inject(ApiService)
  private route = inject(ActivatedRoute)

  projectId = this.route.snapshot.paramMap.get('projectId')!
  requestId = this.route.snapshot.paramMap.get('requestId')!
  executionId = this.route.snapshot.paramMap.get('executionId')!

  execution = signal<Execution | null>(null)
  isLoading = signal(true)
  selected = signal<TestResult | null>(null)
  explainPending = signal(false)
  explanation = signal<string | null>(null)

  constructor() {
    this.api
      .getExecution(this.executionId)
      .then((execution) => this.execution.set(execution))
      .finally(() => this.isLoading.set(false))
  }

  icon(outcome: string): string {
    return OUTCOME_ICON[outcome] ?? ''
  }

  variablesPreview(): string {
    return JSON.stringify(this.execution()?.variables_used ?? {})
  }

  select(r: TestResult) {
    this.selected.set(r)
    this.explanation.set(null)
  }

  async explainFailure() {
    const selected = this.selected()
    if (!selected) return
    this.explainPending.set(true)
    try {
      const result = await this.api.aiExplainFailure(selected.id)
      this.explanation.set(result.explanation)
    } finally {
      this.explainPending.set(false)
    }
  }
}
