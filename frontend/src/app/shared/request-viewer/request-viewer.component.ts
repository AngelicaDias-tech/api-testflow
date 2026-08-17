import { Component, Input } from '@angular/core'
import { JsonPipe } from '@angular/common'
import type { SentRequest } from '../../core/models'
import { MethodBadgeComponent } from '../method-badge/method-badge.component'

/**
 * "📤 Request enviado" (melhoria 2) — espelha exatamente o que
 * app.engine.http_executor.build_sent_snapshot devolveu: o request
 * EFETIVAMENTE montado (URL final, headers finais já com auth aplicada e
 * mascarada, body real), nunca o que está só salvo no formulário. Fica ao
 * lado do app-response-viewer ("📥 Response recebida") para responder,
 * lado a lado, "o que eu enviei?" e "o que a API devolveu?".
 */
@Component({
  selector: 'app-request-viewer',
  standalone: true,
  imports: [JsonPipe, MethodBadgeComponent],
  template: `
    <div class="card p-5">
      <div class="mb-3 flex flex-wrap items-center gap-3">
        <app-method-badge [method]="sent.method" />
        <span class="mono text-sm text-foreground">{{ sent.url }}</span>
      </div>
      @if (sent.auth_type !== 'none') {
        <span class="badge-auto mb-3 inline-block">🔐 autenticação: {{ sent.auth_type }}</span>
      }

      @if (queryEntries().length > 0) {
        <details open>
          <summary class="cursor-pointer text-sm font-medium text-foreground-muted">Query params</summary>
          <pre class="mono mt-2 max-h-32 overflow-auto rounded-lg border border-border bg-canvas p-3 text-xs text-foreground">{{
            sent.query_params | json
          }}</pre>
        </details>
      }

      @if (headerEntries().length > 0) {
        <details class="mt-2" open>
          <summary class="cursor-pointer text-sm font-medium text-foreground-muted">Headers enviados</summary>
          <pre class="mono mt-2 max-h-40 overflow-auto rounded-lg border border-border bg-canvas p-3 text-xs text-foreground-muted">{{
            sent.headers | json
          }}</pre>
        </details>
      }

      <details class="mt-2" open>
        <summary class="cursor-pointer text-sm font-medium text-foreground-muted">Body enviado</summary>
        @if (sent.body_type === 'none' || !sent.body) {
          <p class="mt-2 text-xs text-foreground-muted">Esta requisição não possui body.</p>
        } @else {
          <pre class="mono mt-2 max-h-80 overflow-auto rounded-lg border border-border bg-canvas p-4 text-xs text-foreground">{{
            sent.body
          }}</pre>
        }
      </details>
    </div>
  `,
})
export class RequestViewerComponent {
  @Input({ required: true }) sent!: SentRequest

  queryEntries(): [string, string][] {
    return Object.entries(this.sent.query_params ?? {})
  }

  headerEntries(): [string, string][] {
    return Object.entries(this.sent.headers ?? {})
  }
}
