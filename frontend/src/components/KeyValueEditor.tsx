interface Pair {
  key: string
  value: string
}

export function recordToPairs(record: Record<string, string>): Pair[] {
  return Object.entries(record).map(([key, value]) => ({ key, value }))
}

export function pairsToRecord(pairs: Pair[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const p of pairs) {
    if (p.key.trim()) out[p.key.trim()] = p.value
  }
  return out
}

export default function KeyValueEditor({
  pairs,
  onChange,
  keyPlaceholder = 'nome',
  valuePlaceholder = 'valor',
}: {
  pairs: Pair[]
  onChange: (pairs: Pair[]) => void
  keyPlaceholder?: string
  valuePlaceholder?: string
}) {
  const update = (i: number, field: 'key' | 'value', value: string) => {
    const next = [...pairs]
    next[i] = { ...next[i], [field]: value }
    onChange(next)
  }
  const remove = (i: number) => onChange(pairs.filter((_, idx) => idx !== i))
  const add = () => onChange([...pairs, { key: '', value: '' }])

  return (
    <div className="space-y-2">
      {pairs.map((p, i) => (
        <div key={i} className="flex gap-2">
          <input
            className="input mono flex-1"
            placeholder={keyPlaceholder}
            value={p.key}
            onChange={(e) => update(i, 'key', e.target.value)}
          />
          <input
            className="input mono flex-1"
            placeholder={valuePlaceholder}
            value={p.value}
            onChange={(e) => update(i, 'value', e.target.value)}
          />
          <button type="button" className="btn-secondary px-2" onClick={() => remove(i)}>
            ✕
          </button>
        </div>
      ))}
      <button type="button" className="text-sm text-indigo-600 hover:underline" onClick={add}>
        + adicionar
      </button>
    </div>
  )
}
