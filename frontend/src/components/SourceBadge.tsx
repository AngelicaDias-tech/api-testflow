export default function SourceBadge({ source }: { source: string }) {
  if (source === 'auto') return <span className="badge-auto">automático</span>
  if (source === 'ai_suggested') return <span className="badge-ai">🤖 IA</span>
  return <span className="badge-custom">manual</span>
}
