import type { AuthDef } from '../types'

export default function AuthEditor({ auth, onChange }: { auth: AuthDef; onChange: (auth: AuthDef) => void }) {
  return (
    <div className="space-y-3">
      <div>
        <label className="label">Tipo de autenticação</label>
        <select
          className="input"
          value={auth.type}
          onChange={(e) => onChange({ type: e.target.value as AuthDef['type'] })}
        >
          <option value="none">Nenhuma</option>
          <option value="bearer">Bearer Token</option>
          <option value="basic">Basic Auth</option>
          <option value="api_key">API Key</option>
        </select>
      </div>

      {auth.type === 'bearer' && (
        <div>
          <label className="label">Token</label>
          <input
            className="input mono"
            type="password"
            placeholder="eyJhbGciOi..."
            value={auth.token ?? ''}
            onChange={(e) => onChange({ ...auth, token: e.target.value })}
          />
        </div>
      )}

      {auth.type === 'basic' && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Usuário</label>
            <input
              className="input"
              value={auth.username ?? ''}
              onChange={(e) => onChange({ ...auth, username: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Senha</label>
            <input
              className="input"
              type="password"
              value={auth.password ?? ''}
              onChange={(e) => onChange({ ...auth, password: e.target.value })}
            />
          </div>
        </div>
      )}

      {auth.type === 'api_key' && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Nome do header/param</label>
            <input
              className="input mono"
              placeholder="X-API-Key"
              value={auth.key_name ?? ''}
              onChange={(e) => onChange({ ...auth, key_name: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Valor</label>
            <input
              className="input mono"
              type="password"
              value={auth.api_key ?? ''}
              onChange={(e) => onChange({ ...auth, api_key: e.target.value })}
            />
          </div>
          <div className="col-span-2">
            <label className="label">Onde enviar</label>
            <select
              className="input"
              value={auth.location ?? 'header'}
              onChange={(e) => onChange({ ...auth, location: e.target.value as 'header' | 'query' })}
            >
              <option value="header">Header</option>
              <option value="query">Query parameter</option>
            </select>
          </div>
        </div>
      )}

      <p className="text-xs text-slate-400">
        🔒 Segredos são criptografados no armazenamento e mascarados na interface — nunca aparecem em texto puro.
      </p>
    </div>
  )
}
