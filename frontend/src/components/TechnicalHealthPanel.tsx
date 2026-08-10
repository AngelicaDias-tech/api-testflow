import { useMemo, useState } from 'react'
import type { Check, ProbeResult } from '../types'

/**
 * Camada TECNICA automatica (status HTTP, JSON valido, Content-Type, tempo
 * de resposta, campos/tipos descobertos). O usuario NAO precisa selecionar
 * dezenas de checkboxes uma a uma: por padrao mostramos um resumo de saude
 * compacto com um unico botao "Aceitar diagnóstico técnico" que aprova tudo
 * de uma vez. Quem quiser refinar item a item ainda pode expandir os
 * detalhes - a capacidade de descoberta automatica (app/engine/discovery.py)
 * continua exatamente a mesma, só a apresentação muda.
 */
export default function TechnicalHealthPanel({
  probe,
  selected,
  onToggle,
  onAcceptAll,
  onAcceptSelected,
  isAdding,
  addedCount,
}: {
  probe: ProbeResult
  selected: Set<string>
  onToggle: (id: string, checked: boolean) => void
  onAcceptAll: (checks: Check[]) => void
  onAcceptSelected: (checks: Check[]) => void
  isAdding?: boolean
  addedCount: number
}) {
  const [expanded, setExpanded] = useState(false)

  const summary = useMemo(() => {
    const checks = probe.discovered_checks
    const byCategory: Record<string, number> = {}
    for (const c of checks) byCategory[c.category] = (byCategory[c.category] ?? 0) + 1
    const fieldCount = byCategory.field ?? 0
    return { total: checks.length, fieldCount, byCategory }
  }, [probe.discovered_checks])

  const healthy = (probe.status_code ?? 0) < 400 && probe.json_valid
  const allAdded = addedCount >= summary.total && summary.total > 0

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={`text-2xl ${healthy ? '' : 'grayscale'}`}>{healthy ? '✅' : '⚠️'}</span>
          <div>
            <h2 className="text-base font-semibold text-slate-800">Diagnóstico técnico</h2>
            <p className="text-sm text-slate-500">
              {summary.total} verificações técnicas prontas — HTTP {probe.status_code}, JSON{' '}
              {probe.json_valid ? 'válido' : 'inválido'}, {summary.fieldCount} campos mapeados,{' '}
              {probe.response_time_ms.toFixed(0)}ms de resposta.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {allAdded ? (
            <span className="badge-pass">✓ diagnóstico aceito ({addedCount})</span>
          ) : (
            <button
              className="btn-primary"
              disabled={isAdding}
              onClick={() => onAcceptAll(probe.discovered_checks)}
            >
              {isAdding ? 'Adicionando...' : `Aceitar diagnóstico técnico (${summary.total})`}
            </button>
          )}
          <button className="btn-secondary" onClick={() => setExpanded((v) => !v)}>
            {expanded ? '− Ocultar' : '+ Ver'} detalhes
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <p className="mb-2 text-xs text-slate-400">
            Características técnicas observadas (existência, tipo, formato) — não inclui suposições de
            negócio (ver seção "🎯 O que você quer garantir?" abaixo para isso). Desmarque o que não fizer
            sentido para sua API.
          </p>
          <ul className="mb-3 max-h-64 space-y-1.5 overflow-auto">
            {probe.discovered_checks.map((c) => (
              <li key={c.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selected.has(c.id)}
                  onChange={(e) => onToggle(c.id, e.target.checked)}
                />
                <span className="text-emerald-600">✓</span>
                <span className="text-slate-700">{c.description}</span>
              </li>
            ))}
          </ul>
          <button
            className="btn-secondary"
            disabled={selected.size === 0 || isAdding}
            onClick={() => onAcceptSelected(probe.discovered_checks.filter((c) => selected.has(c.id)))}
          >
            Adicionar selecionadas ({selected.size})
          </button>
        </div>
      )}
    </section>
  )
}
