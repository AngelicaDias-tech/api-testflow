import { Component, EventEmitter, Input, Output, signal } from '@angular/core'
import type { Check, ProbeResult } from '../../../core/models'

/**
 * Camada TECNICA automatica (status HTTP, JSON valido, Content-Type, tempo
 * de resposta, campos/tipos descobertos). Porta 1:1 de
 * components/TechnicalHealthPanel.tsx.
 */
@Component({
  selector: 'app-technical-health-panel',
  standalone: true,
  template: `
    <section class="card p-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <span class="text-2xl {{ healthy() ? '' : 'grayscale' }}">{{ healthy() ? '✅' : '⚠️' }}</span>
          <div>
            <h2 class="text-base font-semibold text-foreground">Diagnóstico técnico</h2>
            <p class="text-sm text-foreground-muted">
              {{ total() }} verificações técnicas prontas — HTTP {{ probe.status_code }}, JSON
              {{ probe.json_valid ? 'válido' : 'inválido' }}, {{ fieldCount() }} campos mapeados,
              {{ probe.response_time_ms.toFixed(0) }}ms de resposta.
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          @if (allAdded()) {
            <span class="badge-pass">✓ diagnóstico aceito ({{ addedCount }})</span>
          } @else {
            <button class="btn-primary" [disabled]="isAdding" (click)="acceptAll.emit(probe.discovered_checks)">
              {{ isAdding ? 'Adicionando...' : 'Aceitar diagnóstico técnico (' + total() + ')' }}
            </button>
          }
          <button class="btn-secondary" (click)="expanded.set(!expanded())">
            {{ expanded() ? '− Ocultar' : '+ Ver' }} detalhes
          </button>
        </div>
      </div>

      @if (expanded()) {
        <div class="mt-4 border-t border-border pt-4">
          <p class="mb-2 text-xs text-foreground-muted">
            Características técnicas observadas (existência, tipo, formato) — não inclui suposições de negócio
            (ver seção "🎯 O que você quer garantir?" abaixo para isso). Desmarque o que não fizer sentido para
            sua API.
          </p>
          <ul class="mb-3 max-h-64 space-y-1.5 overflow-auto">
            @for (c of probe.discovered_checks; track c.id) {
              <li class="flex items-center gap-2 text-sm">
                <input type="checkbox" [checked]="selected.has(c.id)" (change)="onToggleChange(c.id, $event)" />
                <span class="text-success">✓</span>
                <span class="text-foreground">{{ c.description }}</span>
              </li>
            }
          </ul>
          <button
            class="btn-secondary"
            [disabled]="selected.size === 0 || isAdding"
            (click)="acceptSelected.emit(selectedChecks())"
          >
            Adicionar selecionadas ({{ selected.size }})
          </button>
        </div>
      }
    </section>
  `,
})
export class TechnicalHealthPanelComponent {
  @Input({ required: true }) probe!: ProbeResult
  @Input({ required: true }) selected!: Set<string>
  @Input() isAdding = false
  @Input({ required: true }) addedCount = 0

  @Output() toggle = new EventEmitter<{ id: string; checked: boolean }>()
  @Output() acceptAll = new EventEmitter<Check[]>()
  @Output() acceptSelected = new EventEmitter<Check[]>()

  expanded = signal(false)

  total(): number {
    return this.probe.discovered_checks.length
  }

  fieldCount(): number {
    return this.probe.discovered_checks.filter((c) => c.category === 'field').length
  }

  healthy(): boolean {
    return (this.probe.status_code ?? 0) < 400 && this.probe.json_valid
  }

  allAdded(): boolean {
    return this.addedCount >= this.total() && this.total() > 0
  }

  selectedChecks(): Check[] {
    return this.probe.discovered_checks.filter((c) => this.selected.has(c.id))
  }

  onToggleChange(id: string, e: Event) {
    this.toggle.emit({ id, checked: (e.target as HTMLInputElement).checked })
  }
}
