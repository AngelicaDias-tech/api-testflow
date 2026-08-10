import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { aiAnswerQuestion } from '../lib/api'
import type { ProbeResult } from '../types'

/**
 * Consulta/análise em linguagem natural sobre a resposta real (ex: "qual o
 * valor do campo elevation?"). Isto é deliberadamente distinto do
 * assistente de regras de negócio: aqui a IA só responde uma pergunta de
 * leitura sobre o JSON observado — nunca cria uma Rule, nunca influencia
 * PASS/FAIL.
 */
export default function AskAboutResponse({ probe }: { probe: ProbeResult }) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<{ q: string; a: string }[]>([])

  const mutation = useMutation({
    mutationFn: (q: string) => aiAnswerQuestion(q, probe),
    onSuccess: (result, q) => {
      setHistory((h) => [...h, { q, a: result.answer }])
      setQuestion('')
    },
  })

  return (
    <div className="mt-3 border-t border-slate-100 pt-3">
      <p className="mb-2 text-sm font-medium text-slate-600">🤖 Pergunte sobre esta resposta</p>
      {history.length > 0 && (
        <ul className="mb-3 space-y-2">
          {history.map((h, i) => (
            <li key={i} className="text-sm">
              <p className="font-medium text-slate-700">Você: {h.q}</p>
              <p className="text-slate-500">{h.a}</p>
            </li>
          ))}
        </ul>
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (question.trim()) mutation.mutate(question.trim())
        }}
      >
        <input
          className="input"
          placeholder='Ex: "qual o valor do campo elevation?"'
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="btn-secondary" disabled={!question.trim() || mutation.isPending} type="submit">
          {mutation.isPending ? '...' : 'Perguntar'}
        </button>
      </form>
      {mutation.isError && <p className="mt-1 text-xs text-rose-600">{(mutation.error as Error).message}</p>}
    </div>
  )
}
