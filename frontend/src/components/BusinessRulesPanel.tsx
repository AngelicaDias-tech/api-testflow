import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { aiGenerateRules, aiSuggestScenarios } from '../lib/api'
import type { Check, ProbeResult, Rule, Scenario } from '../types'

/**
 * Assistente de IA — não é obrigatório para o fluxo principal (esse é o
 * construtor manual "🎯 Regras de Negócio", que funciona 100% sem IA — ver
 * ManualBusinessRules.tsx, que este componente NUNCA altera nem depende).
 *
 * Escopo deliberadamente limitado a 2 funções — a IA nunca decide PASS/FAIL,
 * nunca executa testes, nunca substitui o pytest, e nunca cria uma regra
 * sozinha sem revisão explícita do usuário:
 *
 * 1. Gerar regras — sintaxe técnica explícita (campo operador valor), uma
 *    regra por linha. Determinístico: campo que não existe na resposta
 *    real vira erro, nunca é adivinhado.
 * 2. Sugerir cenários — a partir de uma regra já estruturada, sugere 2-3
 *    valores de exemplo com o resultado esperado (PASS/FAIL). Só
 *    informativo — pytest é quem decide de fato quando/se o usuário optar
 *    por rodar um desses valores.
 */
export default function BusinessRulesPanel({
  probe,
  rules,
  onAddRules,
  isAdding,
}: {
  probe: ProbeResult | null
  rules?: Rule[]
  onAddRules: (rules: Check[]) => void
  isAdding?: boolean
}) {
  return (
    <section className="card border-violet-200 p-6">
      <h2 className="text-xl font-bold text-slate-900">🤖 Assistente de IA</h2>
      <p className="mb-4 text-sm text-slate-500">
        2 funções isoladas do fluxo manual — a IA nunca decide PASS/FAIL, nunca executa testes e nunca cria uma
        regra sem você aprovar explicitamente.
      </p>
      <div className="space-y-6 divide-y divide-slate-100">
        <GenerateRulesSection probe={probe} onAddRules={onAddRules} isAdding={isAdding} />
        <SuggestScenariosSection rules={rules} />
      </div>
    </section>
  )
}

function ApprovalList({
  rules,
  extraNote,
  onAddRules,
  isAdding,
}: {
  rules: Check[]
  extraNote?: string
  onAddRules: (rules: Check[]) => void
  isAdding?: boolean
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set(rules.map((r) => r.id)))

  // Cada nova geração de regras propostas deve vir com o checkbox MARCADO
  // por padrão (o usuário ainda pode desmarcar manualmente antes de
  // aprovar) — isto NÃO aprova nada sozinho, só define o estado inicial
  // dos checkboxes; o botão "Aprovar" continua sendo obrigatório.
  useEffect(() => {
    setSelected(new Set(rules.map((r) => r.id)))
  }, [rules])

  if (rules.length === 0) return null

  return (
    <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50 p-4">
      <p className="mb-2 text-sm font-medium text-violet-800">Regras propostas — revise antes de aprovar:</p>
      <ul className="mb-3 space-y-2">
        {rules.map((r, i) => (
          <li key={r.id} className="flex items-start gap-2 text-sm text-slate-700">
            <input
              className="mt-0.5"
              type="checkbox"
              checked={selected.has(r.id)}
              onChange={(e) => {
                const next = new Set(selected)
                if (e.target.checked) next.add(r.id)
                else next.delete(r.id)
                setSelected(next)
              }}
            />
            <span>
              <span className="text-slate-400">{i + 1}.</span> {r.description}
              {r.array_path && <span className="badge-ai ml-2">condicional sobre lista</span>}
            </span>
          </li>
        ))}
      </ul>
      {extraNote && <p className="mb-3 text-xs text-amber-700">{extraNote}</p>}
      <button
        className="btn-primary"
        disabled={selected.size === 0 || isAdding}
        onClick={() => onAddRules(rules.filter((r) => selected.has(r.id)))}
      >
        Aprovar {selected.size > 0 ? `(${selected.size})` : 'todas'}
      </button>
      <p className="mt-2 text-xs text-slate-400">
        A IA nunca adiciona regras sozinha nem decide PASS/FAIL — pytest continua sendo a autoridade. Você precisa
        aprovar aqui.
      </p>
    </div>
  )
}

function GenerateRulesSection({
  probe,
  onAddRules,
  isAdding,
}: {
  probe: ProbeResult | null
  onAddRules: (rules: Check[]) => void
  isAdding?: boolean
}) {
  const [text, setText] = useState('')

  const mutation = useMutation({
    mutationFn: () => aiGenerateRules(text, probe ?? undefined),
    onSuccess: (result) => {
      if (result.rules.length > 0) setText('')
    },
  })

  const rules = mutation.data?.rules ?? []
  const errors = mutation.data?.errors ?? []

  return (
    <div className="pt-4 first:pt-0">
      <h3 className="text-base font-semibold text-slate-800">1. Gerar regras</h3>
      <p className="mb-2 text-sm text-slate-500">
        Escreva a sintaxe técnica diretamente — <strong>use o nome real do campo</strong>, não linguagem natural.
        Uma regra por linha.
      </p>
      <textarea
        className="input mono h-24 text-sm"
        placeholder={'stargazers_count > 100\nprivate == false\nname == Hello-World'}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button
        className="btn-primary mt-3"
        disabled={!text.trim() || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? 'Gerando...' : '⚙️ Gerar regras'}
      </button>

      {errors.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-red-700">
          {errors.map((err, i) => (
            <li key={i}>⚠️ {err}</li>
          ))}
        </ul>
      )}
      <ApprovalList rules={rules} onAddRules={onAddRules} isAdding={isAdding} />
    </div>
  )
}

function SuggestScenariosSection({ rules }: { rules?: Rule[] }) {
  const candidateRules = (rules ?? []).filter((r) => r.field && r.operator)
  const [selectedRuleId, setSelectedRuleId] = useState('')

  const mutation = useMutation({
    mutationFn: (rule: Rule) =>
      aiSuggestScenarios({ field: rule.field ?? undefined, operator: rule.operator, expected: rule.expected }),
  })

  const scenarios: Scenario[] = mutation.data?.scenarios ?? []
  const selectedRule = candidateRules.find((r) => r.id === selectedRuleId)

  return (
    <div className="pt-4">
      <h3 className="text-base font-semibold text-slate-800">2. Sugerir cenários</h3>
      <p className="mb-2 text-sm text-slate-500">
        Escolha uma regra já aprovada — a IA sugere valores de exemplo com o resultado esperado (PASS/FAIL). Só
        informativo: a IA nunca executa nada, o pytest é quem decide de verdade.
      </p>
      {candidateRules.length === 0 ? (
        <p className="text-sm text-slate-400">Aprove pelo menos uma regra de campo primeiro.</p>
      ) : (
        <div className="flex flex-wrap items-end gap-2">
          <select className="input" value={selectedRuleId} onChange={(e) => setSelectedRuleId(e.target.value)}>
            <option value="">Selecione uma regra...</option>
            {candidateRules.map((r) => (
              <option key={r.id} value={r.id}>
                {r.description}
              </option>
            ))}
          </select>
          <button
            className="btn-primary"
            disabled={!selectedRule || mutation.isPending}
            onClick={() => selectedRule && mutation.mutate(selectedRule)}
          >
            {mutation.isPending ? 'Sugerindo...' : '🎲 Sugerir cenários'}
          </button>
        </div>
      )}

      {scenarios.length > 0 && (
        <ul className="mt-3 space-y-1 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm text-slate-700">
          {scenarios.map((s, i) => (
            <li key={i}>
              <span className={s.expected_outcome === 'PASS' ? 'text-green-700' : 'text-red-700'}>
                {s.expected_outcome}
              </span>{' '}
              — {s.description}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
