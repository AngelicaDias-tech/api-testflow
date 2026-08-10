import { Component, EventEmitter, inject, Input, OnInit, Output, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ApiService } from '../../../core/services/api.service'
import { ApiError } from '../../../core/services/api-error'
import { KeyValueEditorComponent } from '../../../shared/key-value-editor/key-value-editor.component'
import { pairsToRecord, recordToPairs, type Pair } from '../../../core/utils/pairs'
import type { AuthDef, RequestDef } from '../../../core/models'

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

// Mesma lista de app/core/security.py (_SENSITIVE_HEADER_NAMES) - usada só
// para decidir quais valores de header começam em branco no formulário de
// edição (nunca reenviar um valor mascarado como se fosse o segredo real).
const SENSITIVE_HEADER_NAMES = new Set([
  'authorization',
  'cookie',
  'set-cookie',
  'x-api-key',
  'api-key',
  'x-auth-token',
  'proxy-authorization',
])

type SecretField = 'token' | 'password' | 'api_key'

/**
 * Modal de edição da configuração de uma API já cadastrada (nome, método,
 * URL, headers, query params e autenticação). Reutiliza a MESMA
 * ApiRequestDef/endpoint PUT /requests/{id} já usados pela criação - não
 * existe uma segunda estrutura de armazenamento.
 *
 * Campos sensíveis (token/senha/api_key) sempre começam EM BRANCO aqui,
 * mesmo que a API já tenha uma credencial configurada: o backend só
 * expõe valores mascarados (nunca o segredo real), então reenviar esse
 * valor mascarado seria gravá-lo por cima do segredo de verdade. Deixar o
 * campo em branco no "Salvar alterações" preserva a credencial atual
 * (ver carry_over_blank_secrets em app/core/security.py); preencher o
 * campo substitui a credencial.
 */
@Component({
  selector: 'app-edit-request-modal',
  standalone: true,
  imports: [FormsModule, KeyValueEditorComponent],
  template: `
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" (click)="onBackdropClick($event)">
      <div class="card max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6">
        <div class="mb-5 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-foreground">✏️ Editar API</h2>
          <button type="button" class="text-foreground-muted hover:text-foreground" (click)="closed.emit()">✕</button>
        </div>

        <div class="space-y-5">
          <div>
            <label class="label">Nome da API</label>
            <input class="input" [ngModel]="name()" (ngModelChange)="name.set($event)" />
          </div>

          <div class="flex gap-3">
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
              <input class="input mono" [ngModel]="url()" (ngModelChange)="url.set($event)" />
            </div>
          </div>

          <div>
            <label class="label">Headers</label>
            <app-key-value-editor
              [pairs]="headerPairs()"
              (pairsChange)="headerPairs.set($event)"
              keyPlaceholder="Header"
              valuePlaceholder="valor"
            />
            <p class="mt-1.5 text-xs text-foreground-muted">
              🔒 Headers sensíveis (Authorization, Cookie, X-Api-Key...) aparecem em branco por segurança. Deixe em
              branco para manter o valor atual, ou preencha para substituí-lo.
            </p>
          </div>

          <div>
            <label class="label">Query Params</label>
            <app-key-value-editor
              [pairs]="queryPairs()"
              (pairsChange)="queryPairs.set($event)"
              keyPlaceholder="param"
              valuePlaceholder="valor"
            />
          </div>

          <div>
            <label class="label">Autenticação</label>
            <select class="input" [ngModel]="auth().type" (ngModelChange)="setAuthType($event)">
              <option value="none">Nenhuma</option>
              <option value="bearer">Bearer Token</option>
              <option value="basic">Basic Auth</option>
              <option value="api_key">API Key</option>
              <option value="custom">Personalizada</option>
            </select>

            @if (auth().type === 'bearer') {
              <div class="mt-3">
                <label class="label">Token</label>
                <div class="relative">
                  <input
                    class="input mono pr-9"
                    [type]="isVisible('token') ? 'text' : 'password'"
                    [placeholder]="hasExistingSecret('token') ? 'Já configurado — deixe em branco para manter' : 'eyJhbGciOi...'"
                    [ngModel]="auth().token ?? ''"
                    (ngModelChange)="setAuthField('token', $event)"
                  />
                  <button
                    type="button"
                    class="absolute right-2 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground"
                    (click)="toggleVisible('token')"
                    [attr.aria-label]="isVisible('token') ? 'Esconder token' : 'Mostrar token'"
                  >
                    {{ isVisible('token') ? '🙈' : '👁️' }}
                  </button>
                </div>
              </div>
            }

            @if (auth().type === 'basic') {
              <div class="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label class="label">Usuário</label>
                  <input class="input" [ngModel]="auth().username ?? ''" (ngModelChange)="setAuthField('username', $event)" />
                </div>
                <div>
                  <label class="label">Senha</label>
                  <div class="relative">
                    <input
                      class="input pr-9"
                      [type]="isVisible('password') ? 'text' : 'password'"
                      [placeholder]="hasExistingSecret('password') ? 'Já configurada — manter' : 'senha'"
                      [ngModel]="auth().password ?? ''"
                      (ngModelChange)="setAuthField('password', $event)"
                    />
                    <button
                      type="button"
                      class="absolute right-2 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground"
                      (click)="toggleVisible('password')"
                      [attr.aria-label]="isVisible('password') ? 'Esconder senha' : 'Mostrar senha'"
                    >
                      {{ isVisible('password') ? '🙈' : '👁️' }}
                    </button>
                  </div>
                </div>
              </div>
            }

            @if (auth().type === 'api_key') {
              <div class="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label class="label">Nome do header/param</label>
                  <input
                    class="input mono"
                    placeholder="X-API-Key"
                    [ngModel]="auth().key_name ?? ''"
                    (ngModelChange)="setAuthField('key_name', $event)"
                  />
                </div>
                <div>
                  <label class="label">Valor</label>
                  <div class="relative">
                    <input
                      class="input mono pr-9"
                      [type]="isVisible('api_key') ? 'text' : 'password'"
                      [placeholder]="hasExistingSecret('api_key') ? 'Já configurado — manter' : 'valor da chave'"
                      [ngModel]="auth().api_key ?? ''"
                      (ngModelChange)="setAuthField('api_key', $event)"
                    />
                    <button
                      type="button"
                      class="absolute right-2 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground"
                      (click)="toggleVisible('api_key')"
                      [attr.aria-label]="isVisible('api_key') ? 'Esconder valor' : 'Mostrar valor'"
                    >
                      {{ isVisible('api_key') ? '🙈' : '👁️' }}
                    </button>
                  </div>
                </div>
                <div class="col-span-2">
                  <label class="label">Onde enviar</label>
                  <select class="input" [ngModel]="auth().location ?? 'header'" (ngModelChange)="setAuthField('location', $event)">
                    <option value="header">Header</option>
                    <option value="query">Query parameter</option>
                  </select>
                </div>
              </div>
            }

            @if (auth().type === 'custom') {
              <div class="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label class="label">Nome do Header</label>
                  <input
                    class="input mono"
                    placeholder="X-Access-Token"
                    [ngModel]="auth().key_name ?? ''"
                    (ngModelChange)="setAuthField('key_name', $event)"
                  />
                </div>
                <div>
                  <label class="label">Valor</label>
                  <div class="relative">
                    <input
                      class="input mono pr-9"
                      [type]="isVisible('api_key') ? 'text' : 'password'"
                      [placeholder]="hasExistingSecret('api_key') ? 'Já configurado — manter' : 'abc123'"
                      [ngModel]="auth().api_key ?? ''"
                      (ngModelChange)="setAuthField('api_key', $event)"
                    />
                    <button
                      type="button"
                      class="absolute right-2 top-1/2 -translate-y-1/2 text-foreground-muted hover:text-foreground"
                      (click)="toggleVisible('api_key')"
                      [attr.aria-label]="isVisible('api_key') ? 'Esconder valor' : 'Mostrar valor'"
                    >
                      {{ isVisible('api_key') ? '🙈' : '👁️' }}
                    </button>
                  </div>
                </div>
              </div>
            }

            @if (auth().type !== 'none') {
              <p class="mt-2 text-xs text-foreground-muted">
                🔒 Segredos são criptografados no armazenamento. Deixe os campos em branco para manter os valores
                atuais sem alterá-los.
              </p>
            }
          </div>
        </div>

        @if (saveError()) {
          <div class="banner-danger mt-4 text-sm">{{ saveError() }}</div>
        }

        <div class="mt-6 flex justify-end gap-2">
          <button type="button" class="btn-secondary" [disabled]="savePending()" (click)="closed.emit()">Cancelar</button>
          <button type="button" class="btn-primary" [disabled]="!canSave() || savePending()" (click)="onSave()">
            {{ savePending() ? 'Salvando...' : 'Salvar alterações' }}
          </button>
        </div>
      </div>
    </div>
  `,
})
export class EditRequestModalComponent implements OnInit {
  @Input({ required: true }) req!: RequestDef
  @Output() closed = new EventEmitter<void>()
  @Output() saved = new EventEmitter<RequestDef>()

  private api = inject(ApiService)

  methods = METHODS

  name = signal('')
  method = signal('GET')
  url = signal('')
  headerPairs = signal<Pair[]>([])
  queryPairs = signal<Pair[]>([])
  auth = signal<AuthDef>({ type: 'none' })

  private originalAuth: AuthDef = { type: 'none' }
  private visibleFields = signal<Set<SecretField>>(new Set())

  savePending = signal(false)
  saveError = signal<string | null>(null)

  ngOnInit() {
    this.name.set(this.req.name)
    this.method.set(this.req.method)
    this.url.set(this.req.url)
    this.headerPairs.set(this.buildHeaderPairsForEdit(this.req.headers))
    this.queryPairs.set(recordToPairs(this.req.query_params))
    this.originalAuth = this.req.auth
    this.auth.set(this.blankSensitiveAuthFields(this.req.auth))
  }

  private buildHeaderPairsForEdit(headers: Record<string, string>): Pair[] {
    return Object.entries(headers).map(([key, value]) => ({
      key,
      value: SENSITIVE_HEADER_NAMES.has(key.trim().toLowerCase()) ? '' : value,
    }))
  }

  private blankSensitiveAuthFields(auth: AuthDef): AuthDef {
    const { token: _token, password: _password, api_key: _apiKey, ...rest } = auth
    return { ...rest, type: auth.type }
  }

  isVisible(field: SecretField): boolean {
    return this.visibleFields().has(field)
  }

  toggleVisible(field: SecretField) {
    const next = new Set(this.visibleFields())
    if (next.has(field)) next.delete(field)
    else next.add(field)
    this.visibleFields.set(next)
  }

  hasExistingSecret(field: SecretField): boolean {
    return this.originalAuth.type === this.auth().type && !!this.originalAuth[field]
  }

  setAuthType(type: AuthDef['type']) {
    this.auth.set({ type })
  }

  setAuthField<K extends keyof AuthDef>(key: K, value: AuthDef[K]) {
    this.auth.set({ ...this.auth(), [key]: value })
  }

  canSave(): boolean {
    return this.name().trim().length > 0 && this.url().trim().length > 0
  }

  private validate(): string | null {
    if (!this.name().trim()) return 'Informe o nome da API.'
    if (!this.url().trim()) return 'Informe a URL da API.'
    const a = this.auth()
    if (a.type === 'bearer' && !a.token && !this.hasExistingSecret('token')) {
      return 'Informe o token de autenticação (Bearer).'
    }
    if (a.type === 'basic') {
      if (!a.username?.trim()) return 'Informe o usuário (Basic Auth).'
      if (!a.password && !this.hasExistingSecret('password')) return 'Informe a senha (Basic Auth).'
    }
    if (a.type === 'api_key' || a.type === 'custom') {
      if (!a.key_name?.trim()) {
        return a.type === 'api_key' ? 'Informe o nome do header/param.' : 'Informe o nome do header.'
      }
      if (!a.api_key && !this.hasExistingSecret('api_key')) return 'Informe o valor da chave/token.'
    }
    return null
  }

  onBackdropClick(event: MouseEvent) {
    if (event.target === event.currentTarget) this.closed.emit()
  }

  async onSave() {
    const validationError = this.validate()
    if (validationError) {
      this.saveError.set(validationError)
      return
    }
    this.saveError.set(null)
    this.savePending.set(true)
    try {
      const updated = await this.api.updateRequest(this.req.id, {
        name: this.name().trim(),
        method: this.method(),
        url: this.url().trim(),
        headers: pairsToRecord(this.headerPairs()),
        query_params: pairsToRecord(this.queryPairs()),
        auth: this.auth(),
      })
      this.saved.emit(updated)
    } catch (err) {
      this.saveError.set(err instanceof ApiError ? err.message : 'Falha ao salvar as alterações.')
    } finally {
      this.savePending.set(false)
    }
  }
}
