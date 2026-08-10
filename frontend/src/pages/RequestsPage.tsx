import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { deleteRequest, listRequests } from '../lib/api'
import MethodBadge from '../components/MethodBadge'

export default function RequestsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: requests, isLoading } = useQuery({
    queryKey: ['requests', projectId],
    queryFn: () => listRequests(projectId!),
    enabled: !!projectId,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteRequest(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['requests', projectId] }),
  })

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link to="/" className="text-sm text-slate-400 hover:text-slate-600">
            ← Projetos
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">APIs testadas neste projeto</h1>
        </div>
        <button className="btn-primary" onClick={() => navigate(`/projects/${projectId}/new`)}>
          🚀 Testar nova API
        </button>
      </div>

      {isLoading && <p className="text-slate-400">Carregando...</p>}

      {!isLoading && requests?.length === 0 && (
        <div className="card p-10 text-center text-slate-400">Nenhuma API testada ainda neste projeto.</div>
      )}

      <ul className="space-y-2">
        {requests?.map((r) => (
          <li key={r.id} className="card flex items-center justify-between p-4 hover:border-indigo-300">
            <Link
              to={`/projects/${projectId}/requests/${r.id}`}
              className="flex flex-1 items-center gap-3 overflow-hidden"
            >
              <MethodBadge method={r.method} />
              <div className="min-w-0">
                <p className="truncate font-medium text-slate-900">{r.name}</p>
                <p className="truncate text-xs text-slate-500 mono">{r.url}</p>
              </div>
            </Link>
            <div className="flex items-center gap-3">
              {r.last_status_code && (
                <span
                  className={
                    r.last_status_code < 400
                      ? 'badge bg-emerald-100 text-emerald-700'
                      : 'badge bg-rose-100 text-rose-700'
                  }
                >
                  HTTP {r.last_status_code}
                </span>
              )}
              <button
                className="text-xs text-slate-400 hover:text-rose-600"
                onClick={() => {
                  if (confirm(`Excluir "${r.name}"?`)) deleteMutation.mutate(r.id)
                }}
              >
                excluir
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
