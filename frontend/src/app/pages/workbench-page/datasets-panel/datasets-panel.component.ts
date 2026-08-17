import { Component, Input, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { RouterLink } from '@angular/router'
import { ApiService } from '../../../core/services/api.service'
import { ApiError } from '../../../core/services/api-error'
import type { BatchExecution, CsvImportPreview, TestDataSet } from '../../../core/models'

const OUTCOME_ICON: Record<string, string> = { passed: '🟢', failed: '🔴', error: '🔴' }

/**
 * "Massas de Teste": importa um CSV (uma linha = um caso), mostra prévia
 * para revisão, e — depois de confirmado — executa TODOS os casos contra
 * as regras já aprovadas (POST /requests/{id}/datasets/{id}/execute).
 * Cada caso é um Execution normal (PASS/FAIL sempre do pytest); este
 * painel só agrega o resultado consolidado.
 */
@Component({
  selector: 'app-datasets-panel',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <div class="card p-5">
      <h2 class="mb-1 text-lg font-semibold text-foreground">📄 Massas de Teste (CSV)</h2>
      <p class="mb-4 text-sm text-foreground-muted">
        Importe um CSV onde cada linha é um caso de teste — as colunas alimentam os mesmos placeholders
        <code class="mono">{{ '{{var}}' }}</code> usados pelos Cenários de Teste, em lote.
      </p>

      @if (datasets().length > 0) {
        <ul class="mb-4 space-y-2">
          @for (ds of datasets(); track ds.id) {
            <li class="rounded-lg border border-border p-3 text-sm">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="font-medium text-foreground">{{ ds.name }} <span class="text-foreground-muted">({{ ds.rows.length }} casos)</span></span>
                <div class="flex items-center gap-2">
                  <button class="btn-primary px-3 py-1 text-xs" [disabled]="runningId() === ds.id" (click)="run(ds)">
                    {{ runningId() === ds.id ? 'Executando...' : '▶ Executar massa' }}
                  </button>
                  <button class="text-xs text-foreground-muted hover:text-danger" (click)="remove(ds)">remover</button>
                </div>
              </div>

              @if (pendingConfirmId() === ds.id) {
                <div class="banner-warning mt-2">
                  <p class="text-xs font-medium">
                    ⚠️ Esta API usa um método que pode alterar dados reais — executar disparará até
                    {{ ds.rows.length }} chamadas reais.
                  </p>
                  <button class="btn-danger mt-2 px-3 py-1 text-xs" (click)="run(ds, true)">
                    Confirmar e executar mesmo assim
                  </button>
                </div>
              }
              @if (errorById()[ds.id]) {
                <p class="mt-2 text-xs text-danger">{{ errorById()[ds.id] }}</p>
              }

              @if (resultById()[ds.id]; as batch) {
                <div class="mt-3 rounded-lg border border-border bg-canvas p-3">
                  <p class="mb-2 text-sm font-semibold text-foreground">
                    Total: {{ batch.total_cases }} · 🟢 Passou: {{ batch.passed_cases }} · 🔴 Falhou:
                    {{ batch.failed_cases }}
                  </p>
                  <ul class="space-y-1">
                    @for (row of batch.rows; track row.row_index) {
                      <li class="flex items-center justify-between text-xs">
                        <span>
                          {{ OUTCOME_ICON[row.outcome] }} Caso {{ row.row_index + 1 }} —
                          <span class="mono text-foreground-muted">{{ rowPreview(row.variables) }}</span>
                        </span>
                        @if (row.execution_id) {
                          <a
                            class="link"
                            [routerLink]="['/projects', projectId, 'requests', requestId, 'executions', row.execution_id]"
                          >
                            ver detalhe
                          </a>
                        }
                      </li>
                    }
                  </ul>
                </div>
              }
            </li>
          }
        </ul>
      }

      <details>
        <summary class="cursor-pointer text-sm font-medium text-foreground-muted">+ Importar CSV</summary>
        <div class="mt-3 space-y-3 border-t border-border pt-3">
          <div>
            <label class="label">Arquivo CSV</label>
            <input class="input" type="file" accept=".csv,text/csv" (change)="onFileSelected($event)" />
          </div>
          <div>
            <label class="label">...ou cole o CSV diretamente</label>
            <textarea
              class="input mono h-28"
              placeholder="cpf,idade,valor,resultado_esperado
12345678900,30,5000,aprovado
11111111111,17,1000,recusado"
              [ngModel]="csvText()"
              (ngModelChange)="csvText.set($event)"
            ></textarea>
          </div>
          <button class="btn-secondary" [disabled]="!csvText().trim() || previewPending()" (click)="doPreview()">
            {{ previewPending() ? 'Analisando...' : 'Analisar CSV' }}
          </button>
          @if (previewError()) {
            <p class="text-sm text-danger">{{ previewError() }}</p>
          }
          <p class="text-xs text-foreground-muted">
            Prefere que a IA gere os casos? Use a aba "📊 Massa" do Assistente de IA acima — a massa aprovada lá
            aparece aqui para executar.
          </p>

          @if (preview(); as p) {
            @if (p.errors.length > 0) {
              <div class="banner-warning">
                @for (e of p.errors; track e) {
                  <p class="text-xs">⚠️ {{ e }}</p>
                }
              </div>
            }
            @if (p.rows.length > 0) {
              <div>
                <p class="mb-2 text-sm text-foreground-muted">
                  Prévia — {{ p.rows.length }} caso(s) válido(s) de {{ p.columns.length }} coluna(s):
                  <span class="mono">{{ p.columns.join(', ') }}</span>
                </p>
                <div class="overflow-auto rounded-lg border border-border">
                  <table class="mono w-full text-xs">
                    <thead class="bg-card-hover">
                      <tr>
                        @for (col of p.columns; track col) {
                          <th class="px-2 py-1 text-left">{{ col }}</th>
                        }
                      </tr>
                    </thead>
                    <tbody>
                      @for (row of p.rows.slice(0, 20); track $index) {
                        <tr class="border-t border-border">
                          @for (col of p.columns; track col) {
                            <td class="px-2 py-1">{{ row[col] }}</td>
                          }
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
                @if (p.rows.length > 20) {
                  <p class="mt-1 text-xs text-foreground-muted">... e mais {{ p.rows.length - 20 }} caso(s).</p>
                }
                <div class="mt-3 flex items-end gap-2">
                  <div class="flex-1">
                    <label class="label">Nome da massa</label>
                    <input class="input" placeholder="Ex: casos de aprovação de crédito" [ngModel]="datasetName()" (ngModelChange)="datasetName.set($event)" />
                  </div>
                  <button class="btn-primary" [disabled]="!datasetName().trim() || confirming()" (click)="confirm()">
                    {{ confirming() ? 'Salvando...' : '✓ Confirmar e salvar massa' }}
                  </button>
                </div>
              </div>
            }
          }
        </div>
      </details>
    </div>
  `,
})
export class DatasetsPanelComponent {
  private api = inject(ApiService)

  @Input({ required: true }) requestId!: string
  @Input({ required: true }) projectId!: string
  private _refreshToken = 0
  @Input() set refreshToken(v: number) {
    if (v !== this._refreshToken) {
      this._refreshToken = v
      this.reload()
    }
  }

  readonly OUTCOME_ICON = OUTCOME_ICON

  datasets = signal<TestDataSet[]>([])
  csvText = signal('')
  previewPending = signal(false)
  previewError = signal<string | null>(null)
  preview = signal<CsvImportPreview | null>(null)
  datasetName = signal('')
  confirming = signal(false)

  runningId = signal<string | null>(null)
  pendingConfirmId = signal<string | null>(null)
  errorById = signal<Record<string, string>>({})
  resultById = signal<Record<string, BatchExecution>>({})

  constructor() {
    this.reload()
  }

  private reload() {
    this.api.listDatasets(this.requestId).then((d) => this.datasets.set(d))
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => this.csvText.set(String(reader.result ?? ''))
    reader.readAsText(file)
  }

  async doPreview() {
    this.previewPending.set(true)
    this.previewError.set(null)
    this.preview.set(null)
    try {
      const result = await this.api.previewCsv(this.requestId, this.csvText())
      this.preview.set(result)
    } catch (err) {
      this.previewError.set(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      this.previewPending.set(false)
    }
  }

  async confirm() {
    const p = this.preview()
    if (!p) return
    this.confirming.set(true)
    try {
      await this.api.createDataset(this.requestId, this.datasetName(), p.columns, p.rows)
      this.preview.set(null)
      this.csvText.set('')
      this.datasetName.set('')
      this.reload()
    } finally {
      this.confirming.set(false)
    }
  }

  async remove(ds: TestDataSet) {
    await this.api.deleteDataset(this.requestId, ds.id)
    this.reload()
  }

  rowPreview(variables: Record<string, unknown>): string {
    return Object.entries(variables)
      .map(([k, v]) => `${k}=${v}`)
      .join(', ')
  }

  async run(ds: TestDataSet, confirm = false) {
    this.runningId.set(ds.id)
    this.errorById.set({ ...this.errorById(), [ds.id]: '' })
    try {
      const batch = await this.api.executeDataset(this.requestId, ds.id, confirm)
      this.pendingConfirmId.set(null)
      this.resultById.set({ ...this.resultById(), [ds.id]: batch })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        this.pendingConfirmId.set(ds.id)
      } else {
        const message = err instanceof ApiError ? err.message : (err as Error).message
        this.errorById.set({ ...this.errorById(), [ds.id]: message })
      }
    } finally {
      this.runningId.set(null)
    }
  }
}
