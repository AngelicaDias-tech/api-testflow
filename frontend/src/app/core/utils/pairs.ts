export interface Pair {
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
