import { Component, Input, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { Router } from '@angular/router'
import { ApiService } from '../../../core/services/api.service'
import { ApiError } from '../../../core/services/api-error'
import { KeyValueEditorComponent } from '../../../shared/key-value-editor/key-value-editor.component'
import { pairsToRecord, type Pair } from '../../../core/utils/pairs'
import type { TestScenario } from '../../../core/models'

/**
 * "Cenários de Teste": um conjunto nomeado de variáveis (ex: cpf/idade/
 * valor) que preenche os placeholders {{var}} do body/URL/headers da API
 * só na hora de executar — nunca altera a configuração original salva
 * (POST /requests/{id}/scenarios/{id}/execute). PASS/FAIL de cada execução
 * continua vindo do pytest (mesma tela de execução já existente).
 */
@Component({
  selector: 'app-scenarios-panel',
  standalone: true,
  imports: [FormsModule, KeyValueEditorComponent],
  template: `
    <div class="card p-5">
      <div class="mb-1 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-foreground">🧩 Cenários de Teste</h2>
      </div>
      <p class="mb-4 text-sm text-foreground-muted">
        Defina conjuntos de dados de entrada (ex: <code class="mono">cpf</code>, <code class="mono">idade</code>,
        <code class="mono">valor</code>) para alimentar placeholders <code class="mono">{{ '{{var}}' }}</code>
        na URL/headers/body desta API. Executar um cenário nunca altera a configuração original salva.
      </p>

      @if (scenarios().length > 0) {
        <ul class="mb-4 space-y-2">
          @for (s of scenarios(); track s.id) {
            <li class="rounded-lg border border-border p-3 text-sm">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="font-medium text-foreground">{{ s.name }}</span>
                <div class="flex items-center gap-2">
                  <button
                    class="btn-primary px-3 py-1 text-xs"
                    [disabled]="runningId() === s.id"
                    (click)="run(s)"
                  >
                    {{ runningId() === s.id ? 'Executando...' : '▶ Executar cenário' }}
                  </button>
                  <button class="text-xs text-foreground-muted hover:text-danger" (click)="remove(s)">remover</button>
                </div>
              </div>
              <pre class="mono mt-2 max-h-24 overflow-auto rounded-lg border border-border bg-canvas p-2 text-xs text-foreground-muted">{{
                variablesPreview(s)
              }}</pre>
              @if (pendingConfirmId() === s.id) {
                <div class="banner-warning mt-2">
                  <p class="text-xs font-medium">⚠️ Este cenário chama um método que pode alterar dados reais.</p>
                  <button class="btn-danger mt-2 px-3 py-1 text-xs" (click)="run(s, true)">
                    Confirmar e executar mesmo assim
                  </button>
                </div>
              }
              @if (errorById()[s.id]) {
                <p class="mt-2 text-xs text-danger">{{ errorById()[s.id] }}</p>
              }
            </li>
          }
        </ul>
      }

      <details>
        <summary class="cursor-pointer text-sm font-medium text-foreground-muted">+ Novo cenário</summary>
        <div class="mt-3 space-y-3 border-t border-border pt-3">
          <div>
            <label class="label">Nome do cenário</label>
            <input class="input" placeholder="Ex: Cliente aprovado" [ngModel]="name()" (ngModelChange)="name.set($event)" />
          </div>
          <div>
            <label class="label">Variáveis (nome → valor)</label>
            <app-key-value-editor
              [pairs]="pairs()"
              (pairsChange)="pairs.set($event)"
              keyPlaceholder="ex: cpf"
              valuePlaceholder="ex: 12345678900"
            />
          </div>
          <button class="btn-secondary" [disabled]="!name().trim() || creating()" (click)="create()">
            {{ creating() ? 'Salvando...' : '+ Salvar cenário' }}
          </button>
        </div>
      </details>
    </div>
  `,
})
export class ScenariosPanelComponent {
  private api = inject(ApiService)
  private router = inject(Router)

  @Input({ required: true }) requestId!: string
  @Input({ required: true }) projectId!: string

  scenarios = signal<TestScenario[]>([])
  name = signal('')
  pairs = signal<Pair[]>([{ key: '', value: '' }])
  creating = signal(false)
  runningId = signal<string | null>(null)
  pendingConfirmId = signal<string | null>(null)
  errorById = signal<Record<string, string>>({})

  constructor() {
    this.reload()
  }

  private reload() {
    this.api.listScenarios(this.requestId).then((s) => this.scenarios.set(s))
  }

  variablesPreview(s: TestScenario): string {
    return JSON.stringify(s.variables, null, 2)
  }

  async create() {
    this.creating.set(true)
    try {
      await this.api.createScenario(this.requestId, this.name(), pairsToRecord(this.pairs()))
      this.name.set('')
      this.pairs.set([{ key: '', value: '' }])
      this.reload()
    } finally {
      this.creating.set(false)
    }
  }

  async remove(s: TestScenario) {
    await this.api.deleteScenario(this.requestId, s.id)
    this.reload()
  }

  async run(s: TestScenario, confirm = false) {
    this.runningId.set(s.id)
    this.errorById.set({ ...this.errorById(), [s.id]: '' })
    try {
      const execution = await this.api.executeScenario(this.requestId, s.id, confirm)
      this.pendingConfirmId.set(null)
      this.router.navigate(['/projects', this.projectId, 'requests', this.requestId, 'executions', execution.id])
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        this.pendingConfirmId.set(s.id)
      } else {
        const message = err instanceof ApiError ? err.message : (err as Error).message
        this.errorById.set({ ...this.errorById(), [s.id]: message })
      }
    } finally {
      this.runningId.set(null)
    }
  }
}
