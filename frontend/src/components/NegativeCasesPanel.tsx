import { useMutation } from '@tanstack/react-query'
import { aiSuggestNegativeCases } from '../lib/api'

export default function NegativeCasesPanel({ requestId }: { requestId: string }) {
  const mutation = useMutation({ mutationFn: () => aiSuggestNegativeCases(requestId) })

  return (
    <div>
      <button className="btn-secondary" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        {mutation.isPending ? 'Analisando...' : '🤖 Sugerir cenários negativos'}
      </button>
      {mutation.data && mutation.data.length === 0 && (
        <p className="mt-2 text-sm text-slate-400">Nenhum cenário negativo óbvio identificado para esta URL.</p>
      )}
      {mutation.data && mutation.data.length > 0 && (
        <ul className="mt-3 space-y-2">
          {mutation.data.map((c) => (
            <li key={c.id} className="rounded-lg border border-slate-200 p-3 text-sm">
              <div className="mb-1 flex items-center gap-2">
                <span className="font-medium text-slate-800">{c.title}</span>
                {c.requires_confirmation ? (
                  <span className="badge bg-amber-100 text-amber-700">requer confirmação — altera dados</span>
                ) : (
                  <span className="badge bg-emerald-100 text-emerald-700">seguro (somente leitura)</span>
                )}
              </div>
              <p className="text-slate-500">{c.description}</p>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-slate-400">
        Estas são sugestões de cenários — crie uma nova requisição de teste (com o ID/token indicado) para
        executá-las. Operações que alteram dados (POST/PUT/PATCH/DELETE) nunca disparam automaticamente.
      </p>
    </div>
  )
}
