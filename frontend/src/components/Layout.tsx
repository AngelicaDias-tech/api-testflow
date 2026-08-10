import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold text-slate-900">
            <span>🧪</span>
            <span>
              API <span className="text-indigo-600">TestFlow</span>
            </span>
          </Link>
          <p className="hidden text-sm text-slate-500 sm:block">
            Teste sua API de forma automática — sem escrever código
          </p>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
