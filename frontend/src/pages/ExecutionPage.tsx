import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { aiExplainFailure, getExecution } from '../lib/api'
import type { TestResult } from '../types'
import SourceBadge from '../components/SourceBadge'

const OUTCOME_ICON: Record<string, string> = { passed: '🟢', failed: '🔴', skipped: '⚪', error: '🔴' }

export default function ExecutionPage() {
  const { projectId, requestId, executionId } = useParams<{
    projectId: string
    requestId: string
    executionId: string
  }>()
  const [selected, setSelected] = useState<TestResult | null>(null)

  const { data: execution, isLoading } = useQuery({
    queryKey: ['execution', executionId],
    queryFn: () => getExecution(executionId!),
    enabled: !!executionId,
  })

  const explainMutation = useMutation({ mutationFn: (resultId: string) => aiExplainFailure(resultId) })

  if (isLoading || !execution) return <p className="text-slate-400">Carregando...</p>

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/projects/${projectId}/requests/${requestId}`} className="text-sm text-slate-400 hover:text-slate-600">
          ← Voltar para a API
        </Link>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">Resultado da execução</h1>
      </div>

      <div className="card grid grid-cols-2 gap-4 p-6 sm:grid-cols-5">
        <Stat label="TOTAL TESTS" value={execution.total} />
        <Stat label="🟢 PASSED" value={execution.passed} className="text-emerald-600" />
        <Stat label="🔴 FAILED" value={execution.failed} className="text-rose-600" />
        <Stat label="⚪ SKIPPED" value={execution.skipped} className="text-slate-500" />
        <Stat label="DURATION" value={`${((execution.duration_ms ?? 0) / 1000).toFixed(2)}s`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Testes</h2>
          <ul className="space-y-1">
            {execution.results.map((r) => (
              <li key={r.id}>
                <button
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                    selected?.id === r.id ? 'bg-indigo-50' : ''
                  }`}
                  onClick={() => {
                    setSelected(r)
                    explainMutation.reset()
                  }}
                >
                  <span className="flex items-center gap-2 truncate">
                    <span>{OUTCOME_ICON[r.outcome]}</span>
                    <span className="truncate text-slate-700">{r.name}</span>
                  </span>
                  <SourceBadge source={r.source} />
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="card p-5">
          {!selected && <p className="text-sm text-slate-400">Clique em um teste à esquerda para ver os detalhes.</p>}
          {selected && (
            <div>
              <h2 className="mb-1 text-lg font-semibold text-slate-800">
                {OUTCOME_ICON[selected.outcome]} {selected.name}
              </h2>
              <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
                {selected.outcome === 'passed' ? 'PASSED' : selected.outcome.toUpperCase()}
              </p>

              {selected.field && (
                <p className="mono mb-3 text-sm text-slate-500">Campo: {selected.field}</p>
              )}

              <div className="mb-4 grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="label mb-1">Expected</p>
                  <p className="mono text-sm text-slate-800">{selected.expected ?? '—'}</p>
                </div>
                <div className={`rounded-lg p-3 ${selected.outcome === 'passed' ? 'bg-emerald-50' : 'bg-rose-50'}`}>
                  <p className="label mb-1">Actual</p>
                  <p className="mono text-sm text-slate-800">
                    {selected.actual ?? '—'} {selected.outcome !== 'passed' && '❌'}
                    {selected.outcome === 'passed' && '✅'}
                  </p>
                </div>
              </div>

              {selected.message && (
                <details className="mb-4">
                  <summary className="cursor-pointer text-sm font-medium text-slate-600">Mensagem do pytest</summary>
                  <pre className="mono mt-2 max-h-40 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                    {selected.message}
                  </pre>
                </details>
              )}

              {selected.outcome === 'failed' && (
                <div className="rounded-lg border border-violet-200 bg-violet-50 p-4">
                  <p className="mb-2 text-sm font-semibold text-violet-800">🤖 AI ANALYSIS</p>
                  {!explainMutation.data && (
                    <button
                      className="btn-secondary"
                      disabled={explainMutation.isPending}
                      onClick={() => explainMutation.mutate(selected.id)}
                    >
                      {explainMutation.isPending ? 'Analisando...' : 'Explicar esta falha'}
                    </button>
                  )}
                  {explainMutation.data && (
                    <pre className="whitespace-pre-wrap text-sm text-slate-700">{explainMutation.data.explanation}</pre>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Stat({ label, value, className = '' }: { label: string; value: string | number; className?: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`text-2xl font-bold text-slate-900 ${className}`}>{value}</p>
    </div>
  )
}
