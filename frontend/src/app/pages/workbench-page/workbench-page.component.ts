import { Component, computed, inject, signal } from '@angular/core'
import { ActivatedRoute, Router, RouterLink } from '@angular/router'
import { ApiService } from '../../core/services/api.service'
import { ApiError } from '../../core/services/api-error'
import { ProbeStoreService } from '../../core/services/probe-store.service'
import { flattenFields } from '../../core/utils/flatten'
import { MethodBadgeComponent } from '../../shared/method-badge/method-badge.component'
import { SourceBadgeComponent } from '../../shared/source-badge/source-badge.component'
import { ResponseViewerComponent } from '../../shared/response-viewer/response-viewer.component'
import { RequestViewerComponent } from '../../shared/request-viewer/request-viewer.component'
import { TechnicalHealthPanelComponent } from './technical-health-panel/technical-health-panel.component'
import { ManualBusinessRulesComponent } from './manual-business-rules/manual-business-rules.component'
import { RuleBuilderComponent } from './rule-builder/rule-builder.component'
import { EditRequestModalComponent } from './edit-request-modal/edit-request-modal.component'
import { ScenariosPanelComponent } from './scenarios-panel/scenarios-panel.component'
import { DatasetsPanelComponent } from './datasets-panel/datasets-panel.component'
import { AssistantPanelComponent } from './assistant-panel/assistant-panel.component'
import type { Check, RequestDef, Rule } from '../../core/models'

@Component({
  selector: 'app-workbench-page',
  standalone: true,
  imports: [
    RouterLink,
    MethodBadgeComponent,
    SourceBadgeComponent,
    ResponseViewerComponent,
    RequestViewerComponent,
    TechnicalHealthPanelComponent,
    ManualBusinessRulesComponent,
    RuleBuilderComponent,
    EditRequestModalComponent,
    ScenariosPanelComponent,
    DatasetsPanelComponent,
    AssistantPanelComponent,
  ],
  template: `
    @if (!req()) {
      <p class="text-foreground-muted">Carregando...</p>
    } @else {
      <div class="space-y-6">
        <div>
          <a [routerLink]="['/projects', projectId]" class="text-sm text-foreground-muted hover:text-foreground">← Voltar</a>
          <div class="mt-1 flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <app-method-badge [method]="req()!.method" />
              <div>
                <h1 class="text-xl font-bold text-foreground">{{ req()!.name }}</h1>
                <p class="mono text-sm text-foreground-muted">{{ req()!.url }}</p>
              </div>
            </div>
            <div class="flex gap-2">
              <a [routerLink]="['/projects', projectId, 'requests', requestId, 'history']" class="btn-secondary">
                📜 Histórico
              </a>
              <button class="btn-secondary cursor-pointer" (click)="showEditModal.set(true)">✏️ Editar API</button>
              <button class="btn-secondary cursor-pointer" [disabled]="probePending()" (click)="testarApi(false)">
                {{ probePending() ? 'Testando...' : '🚀 Testar API' }}
              </button>
            </div>
          </div>
        </div>

        @if (editSavedFlash()) {
          <div class="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
            ✅ Configuração da API atualizada com sucesso.
          </div>
        }

        @if (showEditModal()) {
          <app-edit-request-modal [req]="req()!" (closed)="showEditModal.set(false)" (saved)="onRequestSaved($event)" />
        }

        @if (pendingConfirm() === 'probe') {
          <div class="banner-warning">
            <p class="text-sm font-medium">
              ⚠️ {{ req()!.method }} pode alterar dados reais. Confirme para chamar a API agora.
            </p>
            <button class="btn-danger mt-3" (click)="confirmPending()">
              Confirmar e chamar a API mesmo assim
            </button>
          </div>
        }

        @if (probeError() && pendingConfirm() !== 'probe') {
          <div class="banner-danger text-sm">Falha ao chamar a API: {{ probeError() }}</div>
        }

        @if (!probe()) {
          <div class="card p-8 text-center text-foreground-muted">
            Clique em "🚀 Testar API" para chamar a API de verdade — a resposta completa fica disponível aqui
            para consulta, e a IA usa esses dados reais para propor regras de negócio.
          </div>
        }

        @if (probe()) {
          <section class="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <h2 class="mb-3 text-lg font-semibold text-foreground">📤 Request enviado</h2>
              @if (probe()!.sent_request) {
                <app-request-viewer [sent]="probe()!.sent_request!" />
              }
            </div>
            <div>
              <h2 class="mb-3 text-lg font-semibold text-foreground">📥 Response recebida</h2>
              <app-response-viewer [probe]="probe()!" />
            </div>
          </section>
        }

        @if (probe()) {
          <app-technical-health-panel
            [probe]="probe()!"
            [selected]="selectedAuto()"
            [isAdding]="addAutoPending()"
            [addedCount]="autoRulesCount()"
            (toggle)="onToggleAuto($event)"
            (acceptAll)="addAuto($event)"
            (acceptSelected)="addAuto($event)"
          />
        }

        @if (probe()) {
          <app-manual-business-rules [probe]="probe()!" [isAdding]="addManualPending()" (addRules)="addManual($event)" />
        }

        <details class="card p-5">
          <summary class="cursor-pointer text-sm font-medium text-foreground-muted">
            ➕ Construtor manual de regra (avançado)
          </summary>
          <div class="mt-4 border-t border-border pt-4">
            <p class="mb-3 text-sm text-foreground-muted">
              Regras de negócio — o que VOCÊ define como correto para esta API (ex: status deve ser ACTIVE).
            </p>
            <app-rule-builder [fieldOptions]="fieldOptions()" [isAdding]="addOnePending()" (add)="addOne($event)" />
          </div>
        </details>

        <app-assistant-panel
          [req]="req()"
          [probe]="probe()"
          [rules]="rules()"
          [requestId]="requestId"
          [isAdding]="addAiPending()"
          (addRules)="addAi($event)"
          (datasetCreated)="onDatasetCreated()"
        />

        <app-scenarios-panel [requestId]="requestId" [projectId]="projectId" />

        <app-datasets-panel [requestId]="requestId" [projectId]="projectId" [refreshToken]="datasetsRefreshToken()" />

        <section class="card p-5">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-foreground">Regras aprovadas ({{ enabledRules().length }})</h2>
          </div>
          @if (enabledRules().length === 0) {
            <p class="text-sm text-foreground-muted">Nenhuma regra aprovada ainda. Adicione validações acima.</p>
          }
          <ul class="space-y-1.5">
            @for (r of enabledRules(); track r.id) {
              <li class="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
                <div class="flex items-center gap-2">
                  <app-source-badge [source]="r.source" />
                  <span class="text-foreground">{{ r.description || (r.field ?? '(global)') + ' ' + r.operator + ' ' + (r.expected ?? '') }}</span>
                </div>
                <button class="text-xs text-foreground-muted hover:text-danger" (click)="deleteRule(r)">remover</button>
              </li>
            }
          </ul>

          <div class="mt-5">
            @if (pendingConfirm() === 'execute') {
              <div class="banner-warning">
                <p class="text-sm font-medium">⚠️ Esta API pode alterar dados reais.</p>
                <div class="mt-3 flex gap-2">
                  <button class="btn-secondary" [disabled]="executePending()" (click)="cancelExecuteConfirm()">
                    Cancelar
                  </button>
                  <button class="btn-danger" [disabled]="executePending()" (click)="confirmPending()">
                    {{ executePending() ? 'Executando pytest...' : 'Confirmar e executar Pytest' }}
                  </button>
                </div>
              </div>
            } @else {
              <button
                class="btn-primary w-full text-base"
                [disabled]="enabledRules().length === 0 || executePending()"
                (click)="executeTests(false)"
              >
                {{ executePending() ? 'Executando pytest...' : '▶️ Executar Pytest' }}
              </button>
            }
          </div>
        </section>
      </div>
    }
  `,
})
export class WorkbenchPageComponent {
  private api = inject(ApiService)
  private route = inject(ActivatedRoute)
  private router = inject(Router)
  private probeStore = inject(ProbeStoreService)

  projectId = this.route.snapshot.paramMap.get('projectId')!
  requestId = this.route.snapshot.paramMap.get('requestId')!

  // Persistência entre navegações: ver ProbeStoreService. NUNCA dispara
  // uma chamada HTTP sozinho — só testarApi() (abaixo) grava aqui.
  probe = this.probeStore.signalFor(this.requestId)

  req = signal<RequestDef | null>(null)
  rules = signal<Rule[]>([])
  selectedAuto = signal<Set<string>>(new Set())
  pendingConfirm = signal<'probe' | 'execute' | null>(null)
  showEditModal = signal(false)
  editSavedFlash = signal(false)

  probePending = signal(false)
  probeError = signal<string | null>(null)
  addAutoPending = signal(false)
  addOnePending = signal(false)
  addManualPending = signal(false)
  addAiPending = signal(false)
  executePending = signal(false)
  datasetsRefreshToken = signal(0)

  enabledRules = computed(() => this.rules().filter((r) => r.enabled))
  autoRulesCount = computed(() => this.rules().filter((r) => r.source === 'auto').length)
  fieldOptions = computed(() => {
    const probe = this.probe()
    return probe ? flattenFields(probe.body_json) : []
  })

  constructor() {
    this.reloadRequest()
    this.reloadRules()
  }

  private reloadRequest() {
    this.api.getRequest(this.requestId).then((r) => this.req.set(r))
  }

  private reloadRules() {
    this.api.listRules(this.requestId).then((r) => this.rules.set(r))
  }

  onRequestSaved(updated: RequestDef) {
    this.req.set(updated)
    this.showEditModal.set(false)
    this.editSavedFlash.set(true)
    setTimeout(() => this.editSavedFlash.set(false), 3000)
  }

  async testarApi(confirm: boolean) {
    this.probePending.set(true)
    this.probeError.set(null)
    try {
      const result = await this.api.probeRequest(this.requestId, confirm)
      this.probe.set(result)
      this.selectedAuto.set(new Set(result.discovered_checks.map((c) => c.id)))
      this.pendingConfirm.set(null)
      this.reloadRequest()
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) this.pendingConfirm.set('probe')
        this.probeError.set(err.message)
      } else {
        this.probeError.set((err as Error).message)
      }
    } finally {
      this.probePending.set(false)
    }
  }

  async executeTests(confirm: boolean) {
    this.executePending.set(true)
    try {
      const execution = await this.api.executeTests(this.requestId, confirm)
      this.pendingConfirm.set(null)
      this.router.navigate(['/projects', this.projectId, 'requests', this.requestId, 'executions', execution.id])
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) this.pendingConfirm.set('execute')
    } finally {
      this.executePending.set(false)
    }
  }

  confirmPending() {
    if (this.pendingConfirm() === 'probe') this.testarApi(true)
    else this.executeTests(true)
  }

  cancelExecuteConfirm() {
    this.pendingConfirm.set(null)
  }

  onToggleAuto(e: { id: string; checked: boolean }) {
    const next = new Set(this.selectedAuto())
    if (e.checked) next.add(e.id)
    else next.delete(e.id)
    this.selectedAuto.set(next)
  }

  async addAuto(checks: Check[]) {
    this.addAutoPending.set(true)
    try {
      await this.api.createRulesBulk(
        this.requestId,
        checks.map((c) => ({ ...c, enabled: true })),
      )
      this.reloadRules()
    } finally {
      this.addAutoPending.set(false)
    }
  }

  async addOne(rule: { field: string; operator: string; expected: string; description: string }) {
    this.addOnePending.set(true)
    try {
      await this.api.createRule(this.requestId, { ...rule, source: 'custom', category: 'field', enabled: true })
      this.reloadRules()
    } finally {
      this.addOnePending.set(false)
    }
  }

  async addManual(checks: Partial<Check>[]) {
    this.addManualPending.set(true)
    try {
      await this.api.createRulesBulk(this.requestId, checks)
      this.reloadRules()
    } finally {
      this.addManualPending.set(false)
    }
  }

  async addAi(checks: Check[]) {
    this.addAiPending.set(true)
    try {
      await this.api.createRulesBulk(
        this.requestId,
        checks.map((c) => ({ ...c, source: 'ai_suggested', enabled: true })),
      )
      this.reloadRules()
    } finally {
      this.addAiPending.set(false)
    }
  }

  async deleteRule(r: Rule) {
    await this.api.deleteRule(this.requestId, r.id)
    this.reloadRules()
  }

  onDatasetCreated() {
    this.datasetsRefreshToken.set(this.datasetsRefreshToken() + 1)
  }
}
