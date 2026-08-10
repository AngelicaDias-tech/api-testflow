import { Component, EventEmitter, Input, Output } from '@angular/core'
import { FormsModule } from '@angular/forms'
import type { AuthDef } from '../../core/models'

@Component({
  selector: 'app-auth-editor',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="space-y-3">
      <div>
        <label class="label">Tipo de autenticação</label>
        <select class="input" [ngModel]="auth.type" (ngModelChange)="setType($event)">
          <option value="none">Nenhuma</option>
          <option value="bearer">Bearer Token</option>
          <option value="basic">Basic Auth</option>
          <option value="api_key">API Key</option>
          <option value="custom">Personalizada</option>
        </select>
      </div>

      @if (auth.type === 'bearer') {
        <div>
          <label class="label">Token</label>
          <input
            class="input mono"
            type="password"
            placeholder="eyJhbGciOi..."
            [ngModel]="auth.token ?? ''"
            (ngModelChange)="setField('token', $event)"
          />
        </div>
      }

      @if (auth.type === 'basic') {
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="label">Usuário</label>
            <input class="input" [ngModel]="auth.username ?? ''" (ngModelChange)="setField('username', $event)" />
          </div>
          <div>
            <label class="label">Senha</label>
            <input
              class="input"
              type="password"
              [ngModel]="auth.password ?? ''"
              (ngModelChange)="setField('password', $event)"
            />
          </div>
        </div>
      }

      @if (auth.type === 'api_key') {
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="label">Nome do header/param</label>
            <input
              class="input mono"
              placeholder="X-API-Key"
              [ngModel]="auth.key_name ?? ''"
              (ngModelChange)="setField('key_name', $event)"
            />
          </div>
          <div>
            <label class="label">Valor</label>
            <input
              class="input mono"
              type="password"
              [ngModel]="auth.api_key ?? ''"
              (ngModelChange)="setField('api_key', $event)"
            />
          </div>
          <div class="col-span-2">
            <label class="label">Onde enviar</label>
            <select class="input" [ngModel]="auth.location ?? 'header'" (ngModelChange)="setField('location', $event)">
              <option value="header">Header</option>
              <option value="query">Query parameter</option>
            </select>
          </div>
        </div>
      }

      @if (auth.type === 'custom') {
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="label">Nome do Header</label>
            <input
              class="input mono"
              placeholder="X-Access-Token"
              [ngModel]="auth.key_name ?? ''"
              (ngModelChange)="setField('key_name', $event)"
            />
          </div>
          <div>
            <label class="label">Valor</label>
            <input
              class="input mono"
              type="password"
              placeholder="abc123"
              [ngModel]="auth.api_key ?? ''"
              (ngModelChange)="setField('api_key', $event)"
            />
          </div>
        </div>
      }

      <p class="text-xs text-foreground-muted">
        🔒 Segredos são criptografados no armazenamento e mascarados na interface — nunca aparecem em texto puro.
      </p>
    </div>
  `,
})
export class AuthEditorComponent {
  @Input({ required: true }) auth: AuthDef = { type: 'none' }
  @Output() authChange = new EventEmitter<AuthDef>()

  setType(type: AuthDef['type']) {
    this.authChange.emit({ type })
  }

  setField<K extends keyof AuthDef>(key: K, value: AuthDef[K]) {
    this.authChange.emit({ ...this.auth, [key]: value })
  }
}
