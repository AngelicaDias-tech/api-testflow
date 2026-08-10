import { Component, Input } from '@angular/core'
import { JsonPipe } from '@angular/common'
import type { ProbeResult } from '../../core/models'

@Component({
  selector: 'app-response-viewer',
  standalone: true,
  imports: [JsonPipe],
  template: `
    <div class="card p-5">
      <div class="mb-3 flex flex-wrap items-center gap-3">
        <span class="badge {{ statusOk() ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger' }}">
          HTTP {{ probe.status_code ?? '—' }}
        </span>
        <span class="badge-auto">{{ probe.json_valid ? 'JSON válido' : 'não é JSON' }}</span>
        <span class="badge-auto">⏱ {{ probe.response_time_ms.toFixed(0) }}ms</span>
        @if (probe.content_type) {
          <span class="badge-auto mono">{{ probe.content_type }}</span>
        }
      </div>
      @if (probe.error) {
        <p class="mb-3 text-sm text-danger">Erro: {{ probe.error }}</p>
      }
      <details open>
        <summary class="cursor-pointer text-sm font-medium text-foreground-muted">Response body</summary>
        <pre class="mono mt-2 max-h-80 overflow-auto rounded-lg border border-border bg-canvas p-4 text-xs text-foreground">{{
          probe.json_valid ? (probe.body_json | json) : probe.body_raw
        }}</pre>
      </details>
      <details class="mt-2">
        <summary class="cursor-pointer text-sm font-medium text-foreground-muted">Headers</summary>
        <pre class="mono mt-2 max-h-40 overflow-auto rounded-lg border border-border bg-canvas p-3 text-xs text-foreground-muted">{{
          probe.headers | json
        }}</pre>
      </details>
    </div>
  `,
})
export class ResponseViewerComponent {
  @Input({ required: true }) probe!: ProbeResult

  statusOk(): boolean {
    return (this.probe.status_code ?? 0) < 400
  }
}
