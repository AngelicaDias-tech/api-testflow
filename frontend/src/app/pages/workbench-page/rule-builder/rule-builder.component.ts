import { Component, EventEmitter, Input, Output, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { OPERATORS } from '../../../core/models'
import { SPECIAL_FIELDS } from '../../../core/utils/flatten'

const NO_VALUE_OPS = new Set(['exists', 'not_exists', 'is_email_format'])

@Component({
  selector: 'app-rule-builder',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
      <div>
        <label class="label">Campo</label>
        <select class="input" [ngModel]="field()" (ngModelChange)="field.set($event)">
          <option value="">Selecione...</option>
          @for (f of specialFields; track f.value) {
            <option [value]="f.value">{{ f.label }}</option>
          }
          @for (f of fieldOptions; track f) {
            <option [value]="f">{{ f }}</option>
          }
          <option value="__custom__">Outro (digitar)...</option>
        </select>
        @if (field() === '__custom__') {
          <input
            class="input mono mt-2"
            placeholder="ex: data.items.0.status"
            [ngModel]="customField()"
            (ngModelChange)="customField.set($event)"
          />
        }
      </div>
      <div>
        <label class="label">Operador</label>
        <select class="input" [ngModel]="operator()" (ngModelChange)="operator.set($event)">
          @for (op of operators; track op.value) {
            <option [value]="op.value">{{ op.label }}</option>
          }
        </select>
      </div>
      <div>
        <label class="label">Valor</label>
        <input
          class="input"
          [disabled]="!needsValue()"
          [placeholder]="needsValue() ? 'ACTIVE' : '(não se aplica)'"
          [ngModel]="value()"
          (ngModelChange)="value.set($event)"
        />
      </div>
      <button class="btn-primary" [disabled]="!effectiveField() || isAdding" (click)="onAddClick()">
        + Adicionar teste
      </button>
    </div>
  `,
})
export class RuleBuilderComponent {
  @Input({ required: true }) fieldOptions: string[] = []
  @Input() isAdding = false
  @Output() add = new EventEmitter<{ field: string; operator: string; expected: string; description: string }>()

  specialFields = SPECIAL_FIELDS
  operators = OPERATORS

  field = signal('')
  customField = signal('')
  operator = signal('equals')
  value = signal('')

  needsValue(): boolean {
    return !NO_VALUE_OPS.has(this.operator())
  }

  effectiveField(): string {
    return this.field() === '__custom__' ? this.customField() : this.field()
  }

  onAddClick() {
    const effectiveField = this.effectiveField()
    const needsValue = this.needsValue()
    this.add.emit({
      field: effectiveField,
      operator: this.operator(),
      expected: this.value(),
      description: `${effectiveField} ${this.operator()} ${needsValue ? this.value() : ''}`.trim(),
    })
    this.value.set('')
  }
}
