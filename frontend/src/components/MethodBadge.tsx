const COLORS: Record<string, string> = {
  GET: 'bg-emerald-100 text-emerald-700',
  POST: 'bg-amber-100 text-amber-700',
  PUT: 'bg-sky-100 text-sky-700',
  PATCH: 'bg-sky-100 text-sky-700',
  DELETE: 'bg-rose-100 text-rose-700',
}

export default function MethodBadge({ method }: { method: string }) {
  const cls = COLORS[method.toUpperCase()] ?? 'bg-slate-100 text-slate-600'
  return <span className={`badge ${cls} mono font-semibold`}>{method.toUpperCase()}</span>
}
