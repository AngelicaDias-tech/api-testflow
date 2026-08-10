import { useMemo, useState } from 'react'
import type { Check, ProbeResult } from '../types'
import { OPERATORS } from '../types'
import { flattenFields, getByPath } from '../lib/flatten'

/**
 * Fluxo PRINCIPAL de regras de negócio (não depende de IA): a squad escolhe,
 * entre os campos descobertos na resposta real, quais quer validar — vê o
 * valor atual, escolhe o operador (filtrado pelo tipo do campo, reaproveitando
 * os MESMOS operadores já suportados pelo backend/pytest — nenhum novo) e
 * informa o valor esperado. "Valor atual" é sempre lido do JSON real da
 * última chamada; "valor esperado" é a expectativa da squad — pytest é quem
 * de fato compara os dois e decide PASS/FAIL, nunca o frontend.
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

export default function ManualBusinessRules({
  probe,
  onAddRules,
  isAdding,
}: {
  probe: ProbeResult
  onAddRules: (rules: Partial<Check>[]) => void
  isAdding?: boolean
}) {
  const fields = useMemo(() => flattenFields(probe.body_json), [probe])
  const [drafts, setDrafts] = useState<Record<string, FieldRuleDraft>>({})
  const [search, setSearch] = useState('')

  // Filtro puramente visual: nunca altera `fields` (os campos reais
  // descobertos) nem `drafts` (a seleção) - limpar a busca volta a mostrar
  // tudo, e um campo já marcado continua marcado mesmo que saia do filtro.
  const normalizedSearch = search.trim().toLowerCase()
  const visibleFields = normalizedSearch
    ? fields.filter((f) => f.toLowerCase().includes(normalizedSearch))
    : fields

  const toggle = (field: string, checked: boolean) => {
    setDrafts((prev) => {
      const next = { ...prev }
      if (checked) {
        const type = inferType(getByPath(probe.body_json, field))
        next[field] = { operator: OPERATORS_BY_TYPE[type][0], expected: '' }
      } else {
        delete next[field]
      }
      return next
    })
  }

  const updateDraft = (field: string, patch: Partial<FieldRuleDraft>) => {
    setDrafts((prev) => ({ ...prev, [field]: { ...prev[field], ...patch } }))
  }

  const entries = Object.entries(drafts)
  const readyEntries = entries.filter(([, d]) => NO_VALUE_OPERATORS.has(d.operator) || d.expected.trim() !== '')

  const handleAdd = () => {
    const rules: Partial<Check>[] = entries
      .filter(([, d]) => NO_VALUE_OPERATORS.has(d.operator) || d.expected.trim() !== '')
      .map(([field, d]) => {
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
    onAddRules(rules)
    setDrafts({})
  }

  return (
    <section className="card border-indigo-200 p-6">
      <h2 className="text-xl font-bold text-slate-900">🎯 Regras de Negócio</h2>
      <p className="mb-3 text-sm text-slate-500">
        "O valor real retornado pela API atende à condição que a squad espera?" Selecione os campos que quer
        validar — funciona sem IA. O valor atual vem direto da resposta real desta chamada.
      </p>

      <div className="relative mb-2">
        <span
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 leading-none text-slate-400"
        >
          🔎
        </span>
        <input
          className="input"
          // Padding inline (não via classe utilitária pl-9): o `.input` já
          // define px-3 em index.css e, dependendo da ordem das camadas do
          // Tailwind, essa regra pode vencer a utilitária pl-9 no CSS
          // gerado — mesmo com pl-9 aparecendo depois no className, isso
          // NÃO garante precedência no stylesheet final. Estilo inline tem
          // prioridade garantida, então o ícone nunca mais fica embaixo do
          // texto digitado, independente da ordem gerada pelo Tailwind.
          style={{ paddingLeft: '2.25rem' }}
          placeholder="Pesquisar campo... (ex: stargazers, owner, customer.credit_limit)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      {normalizedSearch && (
        <p className="mb-2 text-xs text-slate-400">
          {visibleFields.length} de {fields.length} campo{fields.length === 1 ? '' : 's'} — filtro apenas visual,
          a seleção é preservada.
        </p>
      )}

      <div className="max-h-96 space-y-1 overflow-auto rounded-lg border border-slate-100 p-2">
        {visibleFields.map((field) => {
          const currentValue = getByPath(probe.body_json, field)
          const type = inferType(currentValue)
          const draft = drafts[field]
          const checked = !!draft
          const needsValue = draft && !NO_VALUE_OPERATORS.has(draft.operator)
          return (
            <div key={field} className={`rounded-lg p-2 ${checked ? 'bg-indigo-50' : ''}`}>
              <label className="flex flex-wrap items-center gap-2 text-sm">
                <input type="checkbox" checked={checked} onChange={(e) => toggle(field, e.target.checked)} />
                <span className="mono font-medium text-slate-700">{field}</span>
                <span className="mono text-xs text-slate-400">valor atual: {formatCurrentValue(currentValue)}</span>
              </label>
              {checked && (
                <div className="mt-2 grid grid-cols-1 gap-2 pl-6 sm:grid-cols-2">
                  <div>
                    <label className="label">Operador</label>
                    <select
                      className="input"
                      value={draft.operator}
                      onChange={(e) => updateDraft(field, { operator: e.target.value })}
                    >
                      {OPERATORS_BY_TYPE[type].map((op) => (
                        <option key={op} value={op}>
                          {OPERATOR_LABELS[op] ?? op}
                        </option>
                      ))}
                    </select>
                  </div>
                  {needsValue && (
                    <div>
                      <label className="label">Valor esperado</label>
                      {type === 'boolean' ? (
                        <select
                          className="input"
                          value={draft.expected}
                          onChange={(e) => updateDraft(field, { expected: e.target.value })}
                        >
                          <option value="">Selecione...</option>
                          <option value="true">true</option>
                          <option value="false">false</option>
                        </select>
                      ) : (
                        <input
                          className="input"
                          type={type === 'number' ? 'number' : 'text'}
                          placeholder={type === 'number' ? '100' : 'ACTIVE'}
                          value={draft.expected}
                          onChange={(e) => updateDraft(field, { expected: e.target.value })}
                        />
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
        {fields.length === 0 && <p className="p-2 text-sm text-slate-400">Nenhum campo encontrado na resposta.</p>}
        {fields.length > 0 && visibleFields.length === 0 && (
          <p className="p-2 text-sm text-slate-400">Nenhum campo bate com "{search}".</p>
        )}
      </div>

      <button className="btn-primary mt-4" disabled={readyEntries.length === 0 || isAdding} onClick={handleAdd}>
        {isAdding
          ? 'Adicionando...'
          : `+ Adicionar ${readyEntries.length > 0 ? `(${readyEntries.length}) ` : ''}regra${readyEntries.length === 1 ? '' : 's'} de negócio`}
      </button>
    </section>
  )
}
