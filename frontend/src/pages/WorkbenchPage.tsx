import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  createRule,
  createRulesBulk,
  deleteRule,
  executeTests,
  getRequest,
  listRules,
  probeRequest,
} from '../lib/api'
import type { Check, ProbeResult } from '../types'
import MethodBadge from '../components/MethodBadge'
import SourceBadge from '../components/SourceBadge'
import ResponseViewer from '../components/ResponseViewer'
import RuleBuilder from '../components/RuleBuilder'
import ManualBusinessRules from '../components/ManualBusinessRules'
import BusinessRulesPanel from '../components/BusinessRulesPanel'
import TechnicalHealthPanel from '../components/TechnicalHealthPanel'
import AskAboutResponse from '../components/AskAboutResponse'
import NegativeCasesPanel from '../components/NegativeCasesPanel'
import { flattenFields } from '../lib/flatten'
import { ApiError } from '../lib/api'

export default function WorkbenchPage() {
  const { projectId, requestId } = useParams<{ projectId: string; requestId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [selectedAuto, setSelectedAuto] = useState<Set<string>>(new Set())
  const [pendingConfirm, setPendingConfirm] = useState<'probe' | 'execute' | null>(null)

  const { data: req } = useQuery({
    queryKey: ['request', requestId],
    queryFn: () => getRequest(requestId!),
    enabled: !!requestId,
  })

  const { data: rules } = useQuery({
    queryKey: ['rules', requestId],
    queryFn: () => listRules(requestId!),
    enabled: !!requestId,
  })

  // A última resposta da API fica no cache do React Query (chave por
  // requestId), não em useState local — useState reseta para null sempre
  // que WorkbenchPage desmonta (ex: ao navegar para a tela de resultado e
  // voltar). `enabled: false` garante que isto NUNCA dispara uma chamada
  // HTTP sozinho; o único jeito de popular este cache é o próprio usuário
  // clicar em "Testar API" (probeMutation abaixo, via setQueryData).
  const { data: probe = null } = useQuery<ProbeResult | null>({
    queryKey: ['probe', requestId],
    queryFn: () => Promise.resolve(null),
    enabled: false,
    staleTime: Infinity,
  })

  const probeMutation = useMutation({
    mutationFn: (confirm: boolean) => probeRequest(requestId!, confirm),
    onSuccess: (result) => {
      queryClient.setQueryData(['probe', requestId], result)
      setSelectedAuto(new Set(result.discovered_checks.map((c) => c.id)))
      setPendingConfirm(null)
      queryClient.invalidateQueries({ queryKey: ['request', requestId] })
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) setPendingConfirm('probe')
    },
  })

  const addAutoMutation = useMutation({
    mutationFn: (checks: Check[]) =>
      createRulesBulk(
        requestId!,
        checks.map((c) => ({ ...c, enabled: true })),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules', requestId] }),
  })

  const addOneMutation = useMutation({
    mutationFn: (rule: { field: string; operator: string; expected: string; description: string }) =>
      createRule(requestId!, { ...rule, source: 'custom', category: 'field', enabled: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules', requestId] }),
  })

  const addManualMutation = useMutation({
    mutationFn: (checks: Partial<Check>[]) => createRulesBulk(requestId!, checks),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules', requestId] }),
  })

  const addAiMutation = useMutation({
    mutationFn: (checks: Check[]) =>
      createRulesBulk(
        requestId!,
        checks.map((c) => ({ ...c, source: 'ai_suggested', enabled: true })),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules', requestId] }),
  })

  const deleteRuleMutation = useMutation({
    mutationFn: (ruleId: string) => deleteRule(requestId!, ruleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules', requestId] }),
  })

  const executeMutation = useMutation({
    mutationFn: (confirm: boolean) => executeTests(requestId!, confirm),
    onSuccess: (execution) => {
      setPendingConfirm(null)
      navigate(`/projects/${projectId}/requests/${requestId}/executions/${execution.id}`)
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) setPendingConfirm('execute')
    },
  })

  const fieldOptions = useMemo(() => (probe ? flattenFields(probe.body_json) : []), [probe])

  if (!req) return <p className="text-slate-400">Carregando...</p>

  const enabledRules = rules?.filter((r) => r.enabled) ?? []
  const autoRulesCount = rules?.filter((r) => r.source === 'auto').length ?? 0

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/projects/${projectId}`} className="text-sm text-slate-400 hover:text-slate-600">
          ← Voltar
        </Link>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <MethodBadge method={req.method} />
            <div>
              <h1 className="text-xl font-bold text-slate-900">{req.name}</h1>
              <p className="mono text-sm text-slate-500">{req.url}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Link to={`/projects/${projectId}/requests/${requestId}/history`} className="btn-secondary">
              📜 Histórico
            </Link>
            <button className="btn-secondary" onClick={() => probeMutation.mutate(false)} disabled={probeMutation.isPending}>
              {probeMutation.isPending ? 'Testando...' : '🚀 Testar API'}
            </button>
          </div>
        </div>
      </div>

      {pendingConfirm && (
        <div className="card border-amber-300 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-800">
            ⚠️ {req.method} pode alterar dados reais. Confirme para{' '}
            {pendingConfirm === 'probe' ? 'chamar a API agora' : 'executar os testes de verdade'}.
          </p>
          <button
            className="btn-danger mt-3"
            onClick={() =>
              pendingConfirm === 'probe' ? probeMutation.mutate(true) : executeMutation.mutate(true)
            }
          >
            Confirmar e {pendingConfirm === 'probe' ? 'chamar a API' : 'executar'} mesmo assim
          </button>
        </div>
      )}

      {probeMutation.isError && pendingConfirm !== 'probe' && (
        <div className="card border-rose-300 bg-rose-50 p-4 text-sm text-rose-700">
          Falha ao chamar a API: {(probeMutation.error as Error).message}
        </div>
      )}

      {!probe && (
        <div className="card p-8 text-center text-slate-400">
          Clique em "🚀 Testar API" para chamar a API de verdade — a resposta completa fica disponível
          aqui para consulta, e a IA usa esses dados reais para propor regras de negócio.
        </div>
      )}

      {probe && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800">Response</h2>
          </div>
          <ResponseViewer probe={probe} />
          <div className="card mt-3 p-4">
            <AskAboutResponse probe={probe} />
          </div>
        </section>
      )}

      {probe && (
        <TechnicalHealthPanel
          probe={probe}
          selected={selectedAuto}
          onToggle={(id, checked) => {
            const next = new Set(selectedAuto)
            if (checked) next.add(id)
            else next.delete(id)
            setSelectedAuto(next)
          }}
          onAcceptAll={(checks) => addAutoMutation.mutate(checks)}
          onAcceptSelected={(checks) => addAutoMutation.mutate(checks)}
          isAdding={addAutoMutation.isPending}
          addedCount={autoRulesCount}
        />
      )}

      {probe && (
        <ManualBusinessRules
          probe={probe}
          onAddRules={(checks) => addManualMutation.mutate(checks)}
          isAdding={addManualMutation.isPending}
        />
      )}

      <BusinessRulesPanel
        probe={probe}
        rules={rules}
        onAddRules={(rules) => addAiMutation.mutate(rules)}
        isAdding={addAiMutation.isPending}
      />

      <details className="card p-5">
        <summary className="cursor-pointer text-sm font-medium text-slate-600">
          Regras avançadas (construtor manual) e cenários negativos sugeridos
        </summary>
        <div className="mt-4 space-y-6 border-t border-slate-100 pt-4">
          <div>
            <h3 className="mb-1 text-base font-semibold text-slate-800">➕ Adicionar expectativa manualmente</h3>
            <p className="mb-3 text-sm text-slate-500">
              Regras de negócio — o que VOCÊ define como correto para esta API (ex: status deve ser ACTIVE).
            </p>
            <RuleBuilder
              fieldOptions={fieldOptions}
              onAdd={(r) => addOneMutation.mutate(r)}
              isAdding={addOneMutation.isPending}
            />
          </div>
          <div>
            <h3 className="mb-3 text-base font-semibold text-slate-800">🤖 Cenários negativos sugeridos pela IA</h3>
            {requestId && <NegativeCasesPanel requestId={requestId} />}
          </div>
        </div>
      </details>

      <section className="card p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">Regras aprovadas ({enabledRules.length})</h2>
        </div>
        {enabledRules.length === 0 && (
          <p className="text-sm text-slate-400">Nenhuma regra aprovada ainda. Adicione validações acima.</p>
        )}
        <ul className="space-y-1.5">
          {enabledRules.map((r) => (
            <li key={r.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-sm">
              <div className="flex items-center gap-2">
                <SourceBadge source={r.source} />
                <span className="text-slate-700">{r.description || `${r.field ?? '(global)'} ${r.operator} ${r.expected ?? ''}`}</span>
              </div>
              <button className="text-xs text-slate-400 hover:text-rose-600" onClick={() => deleteRuleMutation.mutate(r.id)}>
                remover
              </button>
            </li>
          ))}
        </ul>

        <button
          className="btn-primary mt-5 w-full text-base"
          disabled={enabledRules.length === 0 || executeMutation.isPending}
          onClick={() => executeMutation.mutate(false)}
        >
          {executeMutation.isPending ? 'Executando pytest...' : '▶ Executar testes'}
        </button>
      </section>
    </div>
  )
}
