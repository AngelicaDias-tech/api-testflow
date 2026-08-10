import type { ProbeResult } from '../types'

export default function ResponseViewer({ probe }: { probe: ProbeResult }) {
  const statusOk = (probe.status_code ?? 0) < 400
  return (
    <div className="card p-5">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <span className={`badge ${statusOk ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
          HTTP {probe.status_code ?? '—'}
        </span>
        <span className="badge-auto">{probe.json_valid ? 'JSON válido' : 'não é JSON'}</span>
        <span className="badge-auto">⏱ {probe.response_time_ms.toFixed(0)}ms</span>
        {probe.content_type && <span className="badge-auto mono">{probe.content_type}</span>}
      </div>
      {probe.error && <p className="mb-3 text-sm text-rose-600">Erro: {probe.error}</p>}
      <details open>
        <summary className="cursor-pointer text-sm font-medium text-slate-600">Response body</summary>
        <pre className="mono mt-2 max-h-80 overflow-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">
          {probe.json_valid ? JSON.stringify(probe.body_json, null, 2) : probe.body_raw}
        </pre>
      </details>
      <details className="mt-2">
        <summary className="cursor-pointer text-sm font-medium text-slate-600">Headers</summary>
        <pre className="mono mt-2 max-h-40 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
          {JSON.stringify(probe.headers, null, 2)}
        </pre>
      </details>
    </div>
  )
}
