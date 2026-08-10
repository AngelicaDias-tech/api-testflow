export function flattenFields(obj: unknown, prefix = '', depth = 0, out: string[] = []): string[] {
  if (depth > 2 || out.length > 60) return out
  if (obj !== null && typeof obj === 'object' && !Array.isArray(obj)) {
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      const path = prefix ? `${prefix}.${key}` : key
      out.push(path)
      flattenFields(value, path, depth + 1, out)
    }
  } else if (Array.isArray(obj) && obj.length > 0) {
    flattenFields(obj[0], prefix ? `${prefix}.0` : '0', depth + 1, out)
  }
  return out
}

export const SPECIAL_FIELDS = [
  { value: '$.status_code', label: 'HTTP status code' },
  { value: '$.content_type', label: 'Content-Type' },
  { value: '$.response_time_ms', label: 'Tempo de resposta (ms)' },
]

/** Resolve um dot-path (com índices de array) contra o JSON real da resposta
 * — mesma semântica de app.engine.evaluator.get_by_path no backend, para
 * que "valor atual" mostrado na UI seja sempre o valor de verdade. */
export function getByPath(obj: unknown, path: string): unknown {
  if (!path) return obj
  let current: unknown = obj
  for (const part of path.split('.')) {
    if (current === null || current === undefined) return undefined
    if (Array.isArray(current)) {
      const idx = Number(part)
      if (!Number.isInteger(idx) || idx < 0 || idx >= current.length) return undefined
      current = current[idx]
    } else if (typeof current === 'object') {
      if (!(part in (current as Record<string, unknown>))) return undefined
      current = (current as Record<string, unknown>)[part]
    } else {
      return undefined
    }
  }
  return current
}
