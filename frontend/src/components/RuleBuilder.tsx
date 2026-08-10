import { useState } from 'react'
import { OPERATORS } from '../types'
import { SPECIAL_FIELDS } from '../lib/flatten'

export default function RuleBuilder({
  fieldOptions,
  onAdd,
  isAdding,
}: {
  fieldOptions: string[]
  onAdd: (rule: { field: string; operator: string; expected: string; description: string }) => void
  isAdding?: boolean
}) {
  const [field, setField] = useState('')
  const [customField, setCustomField] = useState('')
  const [operator, setOperator] = useState('equals')
  const [value, setValue] = useState('')

  const needsValue = !['exists', 'not_exists', 'is_email_format'].includes(operator)
  const effectiveField = field === '__custom__' ? customField : field

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
      <div>
        <label className="label">Campo</label>
        <select className="input" value={field} onChange={(e) => setField(e.target.value)}>
          <option value="">Selecione...</option>
          {SPECIAL_FIELDS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
          {fieldOptions.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
          <option value="__custom__">Outro (digitar)...</option>
        </select>
        {field === '__custom__' && (
          <input
            className="input mono mt-2"
            placeholder="ex: data.items.0.status"
            value={customField}
            onChange={(e) => setCustomField(e.target.value)}
          />
        )}
      </div>
      <div>
        <label className="label">Operador</label>
        <select className="input" value={operator} onChange={(e) => setOperator(e.target.value)}>
          {OPERATORS.map((op) => (
            <option key={op.value} value={op.value}>
              {op.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="label">Valor</label>
        <input
          className="input"
          disabled={!needsValue}
          placeholder={needsValue ? 'ACTIVE' : '(não se aplica)'}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </div>
      <button
        className="btn-primary"
        disabled={!effectiveField || isAdding}
        onClick={() => {
          onAdd({
            field: effectiveField,
            operator,
            expected: value,
            description: `${effectiveField} ${operator} ${needsValue ? value : ''}`.trim(),
          })
          setValue('')
        }}
      >
        + Adicionar teste
      </button>
    </div>
  )
}
