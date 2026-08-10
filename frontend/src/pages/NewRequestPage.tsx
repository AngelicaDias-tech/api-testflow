import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { createRequest, importBruno, importCurl, probeRequest } from '../lib/api'
import type { AuthDef } from '../types'
import KeyValueEditor, { pairsToRecord, recordToPairs } from '../components/KeyValueEditor'
import AuthEditor from '../components/AuthEditor'

type Tab = 'manual' | 'curl' | 'bruno'

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export default function NewRequestPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('manual')

  const [name, setName] = useState('')
  const [method, setMethod] = useState('GET')
  const [url, setUrl] = useState('')
  const [headerPairs, setHeaderPairs] = useState<{ key: string; value: string }[]>([])
  const [queryPairs, setQueryPairs] = useState<{ key: string; value: string }[]>([])
  const [body, setBody] = useState('')
  const [bodyType, setBodyType] = useState<'none' | 'json' | 'text'>('none')
  const [auth, setAuth] = useState<AuthDef>({ type: 'none' })
  const [warnings, setWarnings] = useState<string[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)

  const [curlText, setCurlText] = useState('')
  const [brunoText, setBrunoText] = useState('')

  const curlMutation = useMutation({
    mutationFn: () => importCurl(curlText),
    onSuccess: (preview) => applyPreview(preview),
  })
  const brunoMutation = useMutation({
    mutationFn: () => importBruno(brunoText),
    onSuccess: (preview) => applyPreview(preview),
  })

  function applyPreview(preview: {
    name?: string | null
    method: string
    url: string
    headers: Record<string, string>
    query_params: Record<string, string>
    body: string | null
    body_type: string
    auth: AuthDef
    warnings: string[]
  }) {
    setName(preview.name ?? name)
    setMethod(preview.method)
    setUrl(preview.url)
    setHeaderPairs(recordToPairs(preview.headers))
    setQueryPairs(recordToPairs(preview.query_params))
    setBody(preview.body ?? '')
    setBodyType((preview.body_type as 'none' | 'json' | 'text') ?? 'none')
    setAuth(preview.auth)
    setWarnings(preview.warnings)
    setShowAdvanced(true)
  }

  const submitMutation = useMutation({
    mutationFn: async () => {
      const req = await createRequest({
        project_id: projectId!,
        name: name || url,
        method,
        url,
        headers: pairsToRecord(headerPairs),
        query_params: pairsToRecord(queryPairs),
        body: bodyType === 'none' ? null : body,
        body_type: bodyType,
        auth,
      })
      if (!MUTATING.has(method)) {
        try {
          await probeRequest(req.id, false)
        } catch {
          /* probe failure is shown later on the workbench page, not fatal here */
        }
      }
      return req
    },
    onSuccess: (req) => navigate(`/projects/${projectId}/requests/${req.id}`),
  })

  const canSubmit = url.trim().length > 0

  return (
    <div className="mx-auto max-w-2xl">
      <Link to={`/projects/${projectId}`} className="text-sm text-slate-400 hover:text-slate-600">
        ← Voltar
      </Link>
      <h1 className="mb-6 mt-1 text-2xl font-bold text-slate-900">Testar sua API</h1>

      <div className="mb-5 flex gap-1 rounded-lg bg-slate-100 p-1 text-sm font-medium">
        {(
          [
            ['manual', 'URL manual'],
            ['curl', '📥 Importar cURL'],
            ['bruno', '📥 Importar Bruno'],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            className={`flex-1 rounded-md py-2 ${tab === value ? 'bg-white shadow-sm text-slate-900' : 'text-slate-500'}`}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'curl' && (
        <div className="card mb-5 p-4">
          <label className="label">Comando cURL</label>
          <textarea
            className="input mono h-32"
            placeholder={"curl --location 'https://api.exemplo.com/clientes/123' \\\n--header 'Authorization: Bearer TOKEN'"}
            value={curlText}
            onChange={(e) => setCurlText(e.target.value)}
          />
          <button
            className="btn-secondary mt-3"
            disabled={!curlText.trim() || curlMutation.isPending}
            onClick={() => curlMutation.mutate()}
          >
            {curlMutation.isPending ? 'Importando...' : 'Converter cURL'}
          </button>
          {curlMutation.isError && (
            <p className="mt-2 text-sm text-rose-600">{(curlMutation.error as Error).message}</p>
          )}
        </div>
      )}

      {tab === 'bruno' && (
        <div className="card mb-5 p-4">
          <label className="label">Conteúdo do arquivo .bru (requisição única do Bruno)</label>
          <textarea
            className="input mono h-40"
            placeholder={'get {\n  url: https://api.exemplo.com/users/1\n  body: none\n  auth: none\n}'}
            value={brunoText}
            onChange={(e) => setBrunoText(e.target.value)}
          />
          <button
            className="btn-secondary mt-3"
            disabled={!brunoText.trim() || brunoMutation.isPending}
            onClick={() => brunoMutation.mutate()}
          >
            {brunoMutation.isPending ? 'Importando...' : 'Converter .bru'}
          </button>
          {brunoMutation.isError && (
            <p className="mt-2 text-sm text-rose-600">{(brunoMutation.error as Error).message}</p>
          )}
          <p className="mt-2 text-xs text-slate-400">
            Suporta uma requisição por vez (formato real de arquivo .bru do Bruno). Importação de collections
            completas com environments ainda não é suportada — veja os docs para detalhes.
          </p>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {warnings.map((w, i) => (
            <p key={i}>⚠️ {w}</p>
          ))}
        </div>
      )}

      <div className="card p-5">
        <div className="mb-4">
          <label className="label">Nome deste teste</label>
          <input className="input" placeholder="Ex: Consultar cliente por ID" value={name} onChange={(e) => setName(e.target.value)} />
        </div>

        <div className="mb-4 flex gap-3">
          <div className="w-32">
            <label className="label">Método</label>
            <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
              {METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="label">URL</label>
            <input
              className="input mono"
              placeholder="https://api.exemplo.com/clientes/123"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
        </div>

        {MUTATING.has(method) && (
          <p className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
            ⚠️ {method} pode alterar dados reais. A primeira execução vai pedir confirmação explícita antes de
            disparar a requisição.
          </p>
        )}

        <button className="text-sm text-indigo-600 hover:underline" onClick={() => setShowAdvanced((v) => !v)} type="button">
          {showAdvanced ? '− Ocultar' : '+ Mostrar'} headers, query params, body e autenticação
        </button>

        {showAdvanced && (
          <div className="mt-4 space-y-5 border-t border-slate-100 pt-4">
            <div>
              <label className="label">Headers</label>
              <KeyValueEditor pairs={headerPairs} onChange={setHeaderPairs} keyPlaceholder="Header" valuePlaceholder="valor" />
            </div>
            <div>
              <label className="label">Query parameters</label>
              <KeyValueEditor pairs={queryPairs} onChange={setQueryPairs} keyPlaceholder="param" valuePlaceholder="valor" />
            </div>
            <div>
              <label className="label">Body</label>
              <select className="input mb-2 w-40" value={bodyType} onChange={(e) => setBodyType(e.target.value as never)}>
                <option value="none">Sem body</option>
                <option value="json">JSON</option>
                <option value="text">Texto</option>
              </select>
              {bodyType !== 'none' && (
                <textarea className="input mono h-28" value={body} onChange={(e) => setBody(e.target.value)} />
              )}
            </div>
            <div>
              <label className="label">Autenticação</label>
              <AuthEditor auth={auth} onChange={setAuth} />
            </div>
          </div>
        )}

        <button
          className="btn-primary mt-5 w-full"
          disabled={!canSubmit || submitMutation.isPending}
          onClick={() => submitMutation.mutate()}
        >
          {submitMutation.isPending ? 'Executando...' : '🚀 TESTAR API'}
        </button>
        {submitMutation.isError && (
          <p className="mt-2 text-sm text-rose-600">{(submitMutation.error as Error).message}</p>
        )}
      </div>
    </div>
  )
}
