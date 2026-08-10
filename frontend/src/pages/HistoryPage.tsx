import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { listExecutions } from '../lib/api'

export default function HistoryPage() {
  const { projectId, requestId } = useParams<{ projectId: string; requestId: string }>()

  const { data: executions, isLoading } = useQuery({
    queryKey: ['executions', requestId],
    queryFn: () => listExecutions(requestId!),
    enabled: !!requestId,
  })

  return (
    <div>
      <Link to={`/projects/${projectId}/requests/${requestId}`} className="text-sm text-slate-400 hover:text-slate-600">
        ← Voltar
      </Link>
      <h1 className="mb-6 mt-1 text-2xl font-bold text-slate-900">Histórico de execuções</h1>

      {isLoading && <p className="text-slate-400">Carregando...</p>}
      {!isLoading && executions?.length === 0 && (
        <div className="card p-8 text-center text-slate-400">Nenhuma execução ainda para esta API.</div>
      )}

      {executions && executions.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Data</th>
                <th className="px-4 py-3">🟢 Passed</th>
                <th className="px-4 py-3">🔴 Failed</th>
                <th className="px-4 py-3">⚪ Skipped</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {executions.map((e) => (
                <tr key={e.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">{new Date(e.started_at).toLocaleString('pt-BR')}</td>
                  <td className="px-4 py-3 text-emerald-600">{e.passed}</td>
                  <td className="px-4 py-3 text-rose-600">{e.failed}</td>
                  <td className="px-4 py-3 text-slate-500">{e.skipped}</td>
                  <td className="px-4 py-3">{((e.duration_ms ?? 0) / 1000).toFixed(2)}s</td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/projects/${projectId}/requests/${requestId}/executions/${e.id}`}
                      className="text-indigo-600 hover:underline"
                    >
                      ver detalhes →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
