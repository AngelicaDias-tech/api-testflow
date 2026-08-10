import { Component, inject, signal } from '@angular/core'
import { ActivatedRoute, RouterLink } from '@angular/router'
import { ApiService } from '../../core/services/api.service'
import type { ExecutionSummary } from '../../core/models'

@Component({
  selector: 'app-history-page',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div>
      <a [routerLink]="['/projects', projectId, 'requests', requestId]" class="text-sm text-foreground-muted hover:text-foreground">
        ← Voltar
      </a>
      <h1 class="mb-6 mt-1 text-2xl font-bold text-foreground">Histórico de execuções</h1>

      @if (isLoading()) {
        <p class="text-foreground-muted">Carregando...</p>
      }
      @if (!isLoading() && executions().length === 0) {
        <div class="card p-8 text-center text-foreground-muted">Nenhuma execução ainda para esta API.</div>
      }

      @if (executions().length > 0) {
        <div class="card overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-card-hover text-left text-xs font-semibold uppercase tracking-wide text-foreground-muted">
              <tr>
                <th class="px-4 py-3">Data</th>
                <th class="px-4 py-3">🟢 Passed</th>
                <th class="px-4 py-3">🔴 Failed</th>
                <th class="px-4 py-3">⚪ Skipped</th>
                <th class="px-4 py-3">Duration</th>
                <th class="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              @for (e of executions(); track e.id) {
                <tr class="border-t border-border text-foreground transition-colors hover:bg-card-hover">
                  <td class="px-4 py-3">{{ formatDate(e.started_at) }}</td>
                  <td class="px-4 py-3 text-success">{{ e.passed }}</td>
                  <td class="px-4 py-3 text-danger">{{ e.failed }}</td>
                  <td class="px-4 py-3 text-foreground-muted">{{ e.skipped }}</td>
                  <td class="px-4 py-3">{{ ((e.duration_ms ?? 0) / 1000).toFixed(2) }}s</td>
                  <td class="px-4 py-3 text-right">
                    <a
                      [routerLink]="['/projects', projectId, 'requests', requestId, 'executions', e.id]"
                      class="link"
                    >
                      ver detalhes →
                    </a>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      }
    </div>
  `,
})
export class HistoryPageComponent {
  private api = inject(ApiService)
  private route = inject(ActivatedRoute)

  projectId = this.route.snapshot.paramMap.get('projectId')!
  requestId = this.route.snapshot.paramMap.get('requestId')!

  executions = signal<ExecutionSummary[]>([])
  isLoading = signal(true)

  constructor() {
    this.api
      .listExecutions(this.requestId)
      .then((executions) => this.executions.set(executions))
      .finally(() => this.isLoading.set(false))
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleString('pt-BR')
  }
}
