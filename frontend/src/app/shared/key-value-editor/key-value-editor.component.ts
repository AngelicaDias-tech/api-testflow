import { Component, EventEmitter, Input, Output } from '@angular/core'
import { FormsModule } from '@angular/forms'
import type { Pair } from '../../core/utils/pairs'

@Component({
  selector: 'app-key-value-editor',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="space-y-2">
      @for (p of pairs; track $index) {
        <div class="flex gap-2">
          <input
            class="input mono flex-1"
            [placeholder]="keyPlaceholder"
            [ngModel]="p.key"
            (ngModelChange)="update($index, 'key', $event)"
          />
          <input
            class="input mono flex-1"
            [placeholder]="valuePlaceholder"
            [ngModel]="p.value"
            (ngModelChange)="update($index, 'value', $event)"
          />
          <button type="button" class="btn-secondary px-2" (click)="remove($index)">✕</button>
        </div>
      }
      <button type="button" class="link text-sm" (click)="add()">+ adicionar</button>
    </div>
  `,
})
export class KeyValueEditorComponent {
  @Input({ required: true }) pairs: Pair[] = []
  @Input() keyPlaceholder = 'nome'
  @Input() valuePlaceholder = 'valor'
  @Output() pairsChange = new EventEmitter<Pair[]>()

  update(i: number, field: 'key' | 'value', value: string) {
    const next = [...this.pairs]
    next[i] = { ...next[i], [field]: value }
    this.pairsChange.emit(next)
  }

  remove(i: number) {
    this.pairsChange.emit(this.pairs.filter((_, idx) => idx !== i))
  }

  add() {
    this.pairsChange.emit([...this.pairs, { key: '', value: '' }])
  }
}
