import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { createProject, deleteProject, listProjects } from '../lib/api'

export default function ProjectsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [showForm, setShowForm] = useState(false)

  const { data: projects, isLoading } = useQuery({ queryKey: ['projects'], queryFn: listProjects })

  const createMutation = useMutation({
    mutationFn: () => createProject(name, description || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setName('')
      setDescription('')
      setShowForm(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteProject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  })

  return (
    <div className="mx-auto max-w-2xl">
      <div className="dashboard-shell mb-10 text-center">
        <div className="dashboard-glow" />
        <div className="relative">
          <div className="dashboard-hero-icon">🧪</div>
          <h1 className="dashboard-title">
            API <span className="dashboard-title-accent">TestFlow</span>
          </h1>
          <p className="dashboard-subtitle">Plataforma universal de testes automatizados de APIs</p>
        </div>
      </div>

      <div className="mb-5 flex items-center justify-between">
        <h2 className="dashboard-section-title">Projetos</h2>
        <button className="btn-primary dashboard-btn-primary" onClick={() => setShowForm((v) => !v)}>
          + Criar projeto
        </button>
      </div>

      {showForm && (
        <form
          className="dashboard-form-card mb-6"
          onSubmit={(e) => {
            e.preventDefault()
            if (name.trim()) createMutation.mutate()
          }}
        >
          <div className="mb-3">
            <label className="label">Nome do projeto / squad</label>
            <input
              className="input"
              placeholder="Ex: Vivo, Porto, Claro..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>
          <div className="mb-4">
            <label className="label">Descrição (opcional)</label>
            <input
              className="input"
              placeholder="Ex: APIs do time de pagamentos"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <button className="btn-primary dashboard-btn-primary" type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? 'Criando...' : 'Criar projeto'}
          </button>
        </form>
      )}

      {isLoading && <p className="text-slate-400">Carregando...</p>}

      {!isLoading && projects?.length === 0 && (
        <div className="dashboard-empty">
          <div className="dashboard-empty-icon">📁</div>
          Nenhum projeto ainda. Crie o primeiro para começar a testar suas APIs.
        </div>
      )}

      <ul className="dashboard-list">
        {projects?.map((p) => (
          <li key={p.id} className="dashboard-card group">
            <Link to={`/projects/${p.id}`} className="flex flex-1 items-center gap-3 overflow-hidden">
              <span className="dashboard-card-avatar">{p.name.charAt(0).toUpperCase()}</span>
              <span className="min-w-0">
                <p className="dashboard-card-name truncate">{p.name}</p>
                {p.description && <p className="dashboard-card-desc truncate">{p.description}</p>}
              </span>
            </Link>
            <button
              className="dashboard-delete-btn"
              onClick={() => {
                if (confirm(`Excluir o projeto "${p.name}"? Isso remove também suas requisições e testes.`)) {
                  deleteMutation.mutate(p.id)
                }
              }}
            >
              excluir
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
