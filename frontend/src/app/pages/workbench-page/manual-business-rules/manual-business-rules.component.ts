import { Component, EventEmitter, Input, Output, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { OPERATORS, type Check, type ProbeResult } from '../../../core/models'
import { flattenFields, getByPath } from '../../../core/utils/flatten'

/**
 * Fluxo PRINCIPAL de regras de negócio (não depende de IA): a squad escolhe,
 * entre os campos descobertos na resposta real, quais quer validar — vê o
 * valor atual, escolhe o operador (filtrado pelo tipo do campo, reaproveitando
 * os MESMOS operadores já suportados pelo backend/pytest — nenhum novo) e
 * informa o valor esperado. Porta 1:1 de components/ManualBusinessRules.tsx
 * — este é o fluxo âncora que a migração NÃO PODE alterar em comportamento.
 */

type FieldType = 'number' | 'boolean' | 'string' | 'object' | 'array' | 'null' | 'missing'

const NO_VALUE_OPERATORS = new Set(['exists', 'not_exists'])

const OPERATORS_BY_TYPE: Record<FieldType, string[]> = {
  number: [
    'equals',
    'not_equals',
    'greater_than',
    'greater_than_or_equal',
    'less_than',
    'less_than_or_equal',
    'exists',
    'not_exists',
  ],
  boolean: ['equals', 'not_equals', 'exists', 'not_exists'],
  string: [
    'equals',
    'not_equals',
    'contains',
    'not_contains',
    'starts_with',
    'ends_with',
    'matches_regex',
    'is_email_format',
    'exists',
    'not_exists',
  ],
  array: ['exists', 'not_exists', 'type_is', 'contains'],
  object: ['exists', 'not_exists', 'type_is'],
  null: ['exists', 'not_exists', 'type_is'],
  missing: ['exists', 'not_exists'],
}

const OPERATOR_LABELS: Record<string, string> = Object.fromEntries(OPERATORS.map((o) => [o.value, o.label]))

function inferType(value: unknown): FieldType {
  if (value === undefined) return 'missing'
  if (value === null) return 'null'
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') return 'number'
  if (typeof value === 'string') return 'string'
  if (Array.isArray(value)) return 'array'
  return 'object'
}

function formatCurrentValue(value: unknown): string {
  if (value === undefined) return '(campo ausente)'
  if (value === null) return 'null'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

interface FieldRuleDraft {
  operator: string
  expected: string
}

@Component({
  selector: 'app-manual-business-rules',
  standalone: true,
  imports: [FormsModule],
  template: `
    <section class="card border-border p-6">
      <h2 class="text-xl font-bold text-foreground">🎯 Regras de Negócio</h2>
      <p class="mb-3 text-sm text-foreground-muted">
        "O valor real retornado pela API atende à condição que a squad espera?" Selecione os campos que quer
        validar — funciona sem IA. O valor atual vem direto da resposta real desta chamada.
      </p>

      <div class="relative mb-2">
        <span aria-hidden class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 leading-none text-foreground-muted">
          🔎
        </span>
        <input
          class="input"
          style="padding-left: 2.25rem"
          placeholder="Pesquisar campo... (ex: stargazers, owner, customer.credit_limit)"
          [ngModel]="search()"
          (ngModelChange)="search.set($event)"
        />
      </div>
      @if (normalizedSearch()) {
        <p class="mb-2 text-xs text-foreground-muted">
          {{ visibleFields().length }} de {{ fields().length }} campo{{ fields().length === 1 ? '' : 's' }} —
          filtro apenas visual, a seleção é preservada.
        </p>
      }

      <div class="max-h-96 space-y-1 overflow-auto rounded-lg border border-border p-2">
        @for (field of visibleFields(); track field) {
          <div class="rounded-lg border p-2 {{ isChecked(field) ? 'field-selected' : 'border-transparent' }}">
            <label class="flex flex-wrap items-center gap-2 text-sm">
              <input type="checkbox" [checked]="isChecked(field)" (change)="onToggle(field, $event)" />
              <span class="mono font-medium text-foreground">{{ field }}</span>
              <span class="mono text-xs text-foreground-muted">valor atual: {{ formatValue(field) }}</span>
            </label>
            @if (isChecked(field)) {
              <div class="mt-2 grid grid-cols-1 gap-2 pl-6 sm:grid-cols-2">
                <div>
                  <label class="label">Operador</label>
                  <select class="input" [ngModel]="draftOf(field)!.operator" (ngModelChange)="updateOperator(field, $event)">
                    @for (op of operatorsFor(field); track op) {
                      <option [value]="op">{{ operatorLabel(op) }}</option>
                    }
                  </select>
                </div>
                @if (needsValue(field)) {
                  <div>
                    <label class="label">Valor esperado</label>
                    @if (typeOf(field) === 'boolean') {
                      <select class="input" [ngModel]="draftOf(field)!.expected" (ngModelChange)="updateExpected(field, $event)">
                        <option value="">Selecione...</option>
                        <option value="true">true</option>
                        <option value="false">false</option>
                      </select>
                    } @else {
                      <input
                        class="input"
                        [type]="typeOf(field) === 'number' ? 'number' : 'text'"
                        [placeholder]="typeOf(field) === 'number' ? '100' : 'ACTIVE'"
                        [ngModel]="draftOf(field)!.expected"
                        (ngModelChange)="updateExpected(field, $event)"
                      />
                    }
                  </div>
                }
              </div>
            }
          </div>
        }
        @if (fields().length === 0) {
          <p class="p-2 text-sm text-foreground-muted">Nenhum campo encontrado na resposta.</p>
        }
        @if (fields().length > 0 && visibleFields().length === 0) {
          <p class="p-2 text-sm text-foreground-muted">Nenhum campo bate com "{{ search() }}".</p>
        }
      </div>

      <button class="btn-primary mt-4" [disabled]="readyCount() === 0 || isAdding" (click)="handleAdd()">
        {{
          isAdding
            ? 'Adicionando...'
            : '+ Adicionar ' + (readyCount() > 0 ? '(' + readyCount() + ') ' : '') + 'regra' + (readyCount() === 1 ? '' : 's') + ' de negócio'
        }}
      </button>
    </section>
  `,
})
export class ManualBusinessRulesComponent {
  @Input({ required: true }) probe!: ProbeResult
  @Input() isAdding = false
  @Output() addRules = new EventEmitter<Partial<Check>[]>()

  search = signal('')
  drafts = signal<Record<string, FieldRuleDraft>>({})

  fields(): string[] {
    return flattenFields(this.probe.body_json)
  }

  normalizedSearch(): string {
    return this.search().trim().toLowerCase()
  }

  visibleFields(): string[] {
    const n = this.normalizedSearch()
    const fields = this.fields()
    return n ? fields.filter((f) => f.toLowerCase().includes(n)) : fields
  }

  currentValueOf(field: string): unknown {
    return getByPath(this.probe.body_json, field)
  }

  typeOf(field: string): FieldType {
    return inferType(this.currentValueOf(field))
  }

  formatValue(field: string): string {
    return formatCurrentValue(this.currentValueOf(field))
  }

  operatorsFor(field: string): string[] {
    return OPERATORS_BY_TYPE[this.typeOf(field)]
  }

  operatorLabel(op: string): string {
    return OPERATOR_LABELS[op] ?? op
  }

  isChecked(field: string): boolean {
    return !!this.drafts()[field]
  }

  draftOf(field: string): FieldRuleDraft | undefined {
    return this.drafts()[field]
  }

  needsValue(field: string): boolean {
    const draft = this.draftOf(field)
    return !!draft && !NO_VALUE_OPERATORS.has(draft.operator)
  }

  onToggle(field: string, e: Event) {
    const checked = (e.target as HTMLInputElement).checked
    const next = { ...this.drafts() }
    if (checked) {
      const type = inferType(this.currentValueOf(field))
      next[field] = { operator: OPERATORS_BY_TYPE[type][0], expected: '' }
    } else {
      delete next[field]
    }
    this.drafts.set(next)
  }

  updateOperator(field: string, operator: string) {
    const prev = this.drafts()
    this.drafts.set({ ...prev, [field]: { ...prev[field], operator } })
  }

  updateExpected(field: string, expected: string) {
    const prev = this.drafts()
    this.drafts.set({ ...prev, [field]: { ...prev[field], expected } })
  }

  private readyEntries(): [string, FieldRuleDraft][] {
    return Object.entries(this.drafts()).filter(
      ([, d]) => NO_VALUE_OPERATORS.has(d.operator) || d.expected.trim() !== '',
    )
  }

  readyCount(): number {
    return this.readyEntries().length
  }

  handleAdd() {
    const rules: Partial<Check>[] = this.readyEntries().map(([field, d]) => {
      const needsValue = !NO_VALUE_OPERATORS.has(d.operator)
      return {
        source: 'custom',
        category: 'field',
        field,
        operator: d.operator,
        expected: needsValue ? d.expected : null,
        description: `${field} ${d.operator} ${needsValue ? d.expected : ''}`.trim(),
        enabled: true,
      }
    })
    if (rules.length === 0) return
    this.addRules.emit(rules)
    this.drafts.set({})
  }
}
