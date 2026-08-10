import { Component, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ActivatedRoute, Router, RouterLink } from '@angular/router'
import { ApiService } from '../../core/services/api.service'
import { KeyValueEditorComponent } from '../../shared/key-value-editor/key-value-editor.component'
import { AuthEditorComponent } from '../../shared/auth-editor/auth-editor.component'
import { pairsToRecord, recordToPairs, type Pair } from '../../core/utils/pairs'
import type { AuthDef, ImportPreview } from '../../core/models'

type Tab = 'manual' | 'curl' | 'bruno'

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

@Component({
  selector: 'app-new-request-page',
  standalone: true,
  imports: [FormsModule, RouterLink, KeyValueEditorComponent, AuthEditorComponent],
  template: `
    <div class="mx-auto max-w-2xl">
      <a [routerLink]="['/projects', projectId]" class="text-sm text-foreground-muted hover:text-foreground">← Voltar</a>
      <h1 class="mb-6 mt-1 text-2xl font-bold text-foreground">Testar sua API</h1>

      <div class="mb-5 flex gap-1 rounded-lg bg-card-hover p-1 text-sm font-medium">
        @for (t of tabs; track t.value) {
          <button
            class="flex-1 rounded-md py-2 {{ tab() === t.value ? 'bg-card text-foreground shadow-sm' : 'text-foreground-muted' }}"
            (click)="tab.set(t.value)"
          >
            {{ t.label }}
          </button>
        }
      </div>

      @if (tab() === 'curl') {
        <div class="card mb-5 p-4">
          <label class="label">Comando cURL</label>
          <textarea
            class="input mono h-32"
            placeholder="curl --location 'https://api.exemplo.com/clientes/123' \\
--header 'Authorization: Bearer TOKEN'"
            [ngModel]="curlText()"
            (ngModelChange)="curlText.set($event)"
          ></textarea>
          <button class="btn-secondary mt-3" [disabled]="!curlText().trim() || curlPending()" (click)="doImportCurl()">
            {{ curlPending() ? 'Importando...' : 'Converter cURL' }}
          </button>
          @if (curlError()) {
            <p class="mt-2 text-sm text-danger">{{ curlError() }}</p>
          }
        </div>
      }

      @if (tab() === 'bruno') {
        <div class="card mb-5 p-4">
          <label class="label">Conteúdo do arquivo .bru (requisição única do Bruno)</label>
          <textarea
            class="input mono h-40"
            placeholder="get {
  url: https://api.exemplo.com/users/1
  body: none
  auth: none
}"
            [ngModel]="brunoText()"
            (ngModelChange)="brunoText.set($event)"
          ></textarea>
          <button class="btn-secondary mt-3" [disabled]="!brunoText().trim() || brunoPending()" (click)="doImportBruno()">
            {{ brunoPending() ? 'Importando...' : 'Converter .bru' }}
          </button>
          @if (brunoError()) {
            <p class="mt-2 text-sm text-danger">{{ brunoError() }}</p>
          }
          <p class="mt-2 text-xs text-foreground-muted">
            Suporta uma requisição por vez (formato real de arquivo .bru do Bruno). Importação de collections
            completas com environments ainda não é suportada — veja os docs para detalhes.
          </p>
        </div>
      }

      @if (warnings().length > 0) {
        <div class="banner-warning mb-4 text-sm">
          @for (w of warnings(); track w) {
            <p>⚠️ {{ w }}</p>
          }
        </div>
      }

      <div class="card p-5">
        <div class="mb-4">
          <label class="label">Nome deste teste</label>
          <input
            class="input"
            placeholder="Ex: Consultar cliente por ID"
            [ngModel]="name()"
            (ngModelChange)="name.set($event)"
          />
        </div>

        <div class="mb-4 flex gap-3">
          <div class="w-32">
            <label class="label">Método</label>
            <select class="input" [ngModel]="method()" (ngModelChange)="method.set($event)">
              @for (m of methods; track m) {
                <option [value]="m">{{ m }}</option>
              }
            </select>
          </div>
          <div class="flex-1">
            <label class="label">URL</label>
            <input
              class="input mono"
              placeholder="https://api.exemplo.com/clientes/123"
              [ngModel]="url()"
              (ngModelChange)="url.set($event)"
            />
          </div>
        </div>

        @if (isMutating()) {
          <p class="mb-4 rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning">
            ⚠️ {{ method() }} pode alterar dados reais. A primeira execução vai pedir confirmação explícita antes
            de disparar a requisição.
          </p>
        }

        <button class="link text-sm" type="button" (click)="showAdvanced.set(!showAdvanced())">
          {{ showAdvanced() ? '− Ocultar' : '+ Mostrar' }} headers, query params, body e autenticação
        </button>

        @if (showAdvanced()) {
          <div class="mt-4 space-y-5 border-t border-border pt-4">
            <div>
              <label class="label">Headers</label>
              <app-key-value-editor
                [pairs]="headerPairs()"
                (pairsChange)="headerPairs.set($event)"
                keyPlaceholder="Header"
                valuePlaceholder="valor"
              />
            </div>
            <div>
              <label class="label">Query parameters</label>
              <app-key-value-editor
                [pairs]="queryPairs()"
                (pairsChange)="queryPairs.set($event)"
                keyPlaceholder="param"
                valuePlaceholder="valor"
              />
            </div>
            <div>
              <label class="label">Body</label>
              <select class="input mb-2 w-40" [ngModel]="bodyType()" (ngModelChange)="bodyType.set($event)">
                <option value="none">Sem body</option>
                <option value="json">JSON</option>
                <option value="text">Texto</option>
              </select>
              @if (bodyType() !== 'none') {
                <textarea class="input mono h-28" [ngModel]="body()" (ngModelChange)="body.set($event)"></textarea>
              }
            </div>
            <div>
              <label class="label">Autenticação</label>
              <app-auth-editor [auth]="auth()" (authChange)="auth.set($event)" />
            </div>
          </div>
        }

        <button class="btn-primary mt-5 w-full" [disabled]="!canSubmit() || submitPending()" (click)="onSubmit()">
          {{ submitPending() ? 'Executando...' : '🚀 TESTAR API' }}
        </button>
        @if (submitError()) {
          <p class="mt-2 text-sm text-danger">{{ submitError() }}</p>
        }
      </div>
    </div>
  `,
})
export class NewRequestPageComponent {
  private api = inject(ApiService)
  private route = inject(ActivatedRoute)
  private router = inject(Router)

  projectId = this.route.snapshot.paramMap.get('projectId')!
  methods = METHODS
  tabs: { value: Tab; label: string }[] = [
    { value: 'manual', label: 'URL manual' },
    { value: 'curl', label: '📥 Importar cURL' },
    { value: 'bruno', label: '📥 Importar Bruno' },
  ]

  tab = signal<Tab>('manual')
  name = signal('')
  method = signal('GET')
  url = signal('')
  headerPairs = signal<Pair[]>([])
  queryPairs = signal<Pair[]>([])
  body = signal('')
  bodyType = signal<'none' | 'json' | 'text'>('none')
  auth = signal<AuthDef>({ type: 'none' })
  warnings = signal<string[]>([])
  showAdvanced = signal(false)

  curlText = signal('')
  brunoText = signal('')
  curlPending = signal(false)
  brunoPending = signal(false)
  curlError = signal<string | null>(null)
  brunoError = signal<string | null>(null)
  submitPending = signal(false)
  submitError = signal<string | null>(null)

  isMutating(): boolean {
    return MUTATING.has(this.method())
  }

  canSubmit(): boolean {
    return this.url().trim().length > 0
  }

  private applyPreview(preview: ImportPreview) {
    this.name.set(preview.name ?? this.name())
    this.method.set(preview.method)
    this.url.set(preview.url)
    this.headerPairs.set(recordToPairs(preview.headers))
    this.queryPairs.set(recordToPairs(preview.query_params))
    this.body.set(preview.body ?? '')
    this.bodyType.set((preview.body_type as 'none' | 'json' | 'text') ?? 'none')
    this.auth.set(preview.auth)
    this.warnings.set(preview.warnings)
    this.showAdvanced.set(true)
  }

  async doImportCurl() {
    this.curlPending.set(true)
    this.curlError.set(null)
    try {
      const preview = await this.api.importCurl(this.curlText())
      this.applyPreview(preview)
    } catch (err) {
      this.curlError.set((err as Error).message)
    } finally {
      this.curlPending.set(false)
    }
  }

  async doImportBruno() {
    this.brunoPending.set(true)
    this.brunoError.set(null)
    try {
      const preview = await this.api.importBruno(this.brunoText())
      this.applyPreview(preview)
    } catch (err) {
      this.brunoError.set((err as Error).message)
    } finally {
      this.brunoPending.set(false)
    }
  }

  async onSubmit() {
    this.submitPending.set(true)
    this.submitError.set(null)
    try {
      const req = await this.api.createRequest({
        project_id: this.projectId,
        name: this.name() || this.url(),
        method: this.method(),
        url: this.url(),
        headers: pairsToRecord(this.headerPairs()),
        query_params: pairsToRecord(this.queryPairs()),
        body: this.bodyType() === 'none' ? null : this.body(),
        body_type: this.bodyType(),
        auth: this.auth(),
      })
      if (!MUTATING.has(this.method())) {
        try {
          await this.api.probeRequest(req.id, false)
        } catch {
          /* probe failure is shown later on the workbench page, not fatal here */
        }
      }
      this.router.navigate(['/projects', this.projectId, 'requests', req.id])
    } catch (err) {
      this.submitError.set((err as Error).message)
    } finally {
      this.submitPending.set(false)
    }
  }
}
